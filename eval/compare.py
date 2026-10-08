#!/usr/bin/env python3
"""Matched tools-disabled Ollama response comparisons; human grading pending."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from eval.run import DEV_ONLY_LABEL, _percentile, envelope_for, load_cases, validate_reviewed_set
from patristic_ethics.assess import assess
from patristic_ethics.controlled import ControlledClient, HostOutput
from patristic_ethics.interpreter import FakeInterpreter, OllamaInterpreter
from patristic_ethics.policy import load_policy

CONDITIONS = ("raw", "constitution_guided", "full_pea")


class OllamaGenerator:
    def __init__(self, model, host, timeout_s, options, think=None):
        import ollama
        self.client = ollama.Client(host=host, timeout=timeout_s)
        self.model, self.options = model, options
        self.think = think
        self.last_usage = None

    def __call__(self, messages):
        self.last_usage = None
        try:
            response = self.client.chat(model=self.model, messages=messages,
                                        options=self.options, stream=False,
                                        **({} if getattr(self, "think", None) is None else {"think": self.think}))
            self.last_usage = dict(prompt_tokens=response.prompt_eval_count,
                                   completion_tokens=response.eval_count)
            if not isinstance(response.message.content, str) or not response.message.content.strip():
                return HostOutput(failure="generator returned empty content")
            return HostOutput(text=response.message.content)
        except Exception as exc:
            return HostOutput(failure=f"generation failed: {type(exc).__name__}")


def validate_comparison_cases(cases):
    if not cases:
        raise ValueError("comparison requires at least one scenario")
    for case in cases:
        turns = case.get("turns") if isinstance(case, dict) else None
        if (not isinstance(turns, list) or not turns or not isinstance(case.get("id"), str)
                or any(not isinstance(t, dict) or t.get("role") not in {"user", "assistant"}
                       or not isinstance(t.get("text"), str) for t in turns)
                or turns[-1]["role"] != "user"):
            raise ValueError("comparison cases require an id and user/assistant turns ending in a user request")


def run_comparison(cases, generator, interpreter, policy_doc, db_path,
                   constitution, *, repeats=1, corpus_version="0.1.0-draft"):
    """Use identical fixture turns/settings; grade outputs separately later."""
    if repeats < 1 or not constitution.strip():
        raise ValueError("positive repeats and nonempty constitution required")
    validate_comparison_cases(cases)
    records = []
    for repeat in range(1, repeats + 1):
        for case in cases:
            base = envelope_for(case, policy_doc.get("policy_version", ""), corpus_version)
            base.request = case["turns"][-1]["text"]
            base.messages = base.messages[:-1]
            base.earlier_excerpts = []
            base.history.complete = True
            for condition in CONDITIONS:
                messages = [dict(role=t["role"], content=t["text"]) for t in case["turns"]]
                if condition == "constitution_guided":
                    messages.insert(0, dict(role="system", content=constitution))
                generation_usage, assessment_usage, assessments = [], [], []

                def generate(*_, **__):
                    output = generator([dict(m) for m in messages])
                    generation_usage.append(getattr(generator, "last_usage", None))
                    return output

                def assessor(envelope):
                    context = base.model_copy(deep=True)
                    context.stage = envelope.stage
                    context.candidate_response = envelope.candidate_response
                    result = assess(context, interpreter=interpreter, policy_doc=policy_doc,
                                    db_path=db_path, corpus_version=corpus_version)
                    assessment_usage.append(getattr(interpreter, "last_usage", None))
                    assessments.append(dict(stage=envelope.stage, action=result.action,
                                            disposition=result.decision.disposition if result.decision else None,
                                            failure_kind=result.failure.kind if result.failure else None,
                                            failure_reason=result.failure.reason if result.failure else None))
                    return result

                start = time.perf_counter()
                if condition == "full_pea":
                    client = ControlledClient(runner=generate, assessor=assessor,
                                              policy_version=policy_doc.get("policy_version", ""),
                                              corpus_version=corpus_version)
                    result = client.run(base.request, session_id=f"comparison-{case['id']}-{repeat}")
                    response, candidate = result.released_text, result.buffered
                    failure, action, invoked = result.failure, result.action, result.model_invoked
                else:
                    try:
                        output = generate()
                    except Exception as exc:
                        output = HostOutput(failure=f"generation failed: {type(exc).__name__}")
                    response = "" if output.failure else output.text
                    candidate, failure, action, invoked = output.text, output.failure, None, True
                records.append(dict(id=case["id"], repeat=repeat, condition=condition,
                                    expected=case.get("expected_disposition"),
                                    response=response, candidate=candidate, failure=failure,
                                    pea_action=action, model_invoked=invoked,
                                    latency_ms=round((time.perf_counter()-start)*1000, 2),
                                    generation_usage=generation_usage, assessment_usage=assessment_usage,
                                    assessments=assessments, human_grades=None))
    summaries = {}
    for condition in CONDITIONS:
        group = [r for r in records if r["condition"] == condition]
        summaries[condition] = dict(
            trials=len(group), generation_calls=sum(r["model_invoked"] for r in group),
            failed_trials=sum(bool(r["failure"] or any(a["failure_kind"] for a in r["assessments"])) for r in group),
            latency_ms=dict(p50=_percentile([r["latency_ms"] for r in group], 50),
                            p95=_percentile([r["latency_ms"] for r in group], 95)),
        )
    return dict(label=DEV_ONLY_LABEL, comparison_scope="tools-disabled direct Ollama generation; not live host conformance",
                grading_status="pending human response review; no baseline disposition or task-success inference",
                repeats=repeats, conditions=list(CONDITIONS), condition_summaries=summaries, cases=records)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", required=True)
    parser.add_argument("--backend", choices=["fake", "ollama"], default="fake")
    parser.add_argument("--model", default="ornith-1.5:9b")
    parser.add_argument("--assessment-model", default=None)
    parser.add_argument("--host", default="http://localhost:11434")
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--temperature", type=float, default=0)
    parser.add_argument("--num-predict", type=int, default=1024)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--context-length", type=int, default=None)
    parser.add_argument("--thinking", choices=["model-default", "on", "off"], default="model-default")
    parser.add_argument("--db", default="corpus/units.db")
    parser.add_argument("--policy", default="policy/rules.json")
    parser.add_argument("--constitution", default="policy/constitution.md")
    parser.add_argument("--output", default="artifacts/comparison.json")
    args = parser.parse_args(argv)
    try:
        if args.repeats < 1 or not math.isfinite(args.timeout) or args.timeout <= 0 or args.num_predict < 1:
            raise ValueError("repeats, timeout and num-predict must be positive")
        if not math.isfinite(args.temperature) or not 0 <= args.temperature <= 2:
            raise ValueError("temperature must be finite and between 0 and 2")
        if args.context_length is not None and args.context_length < 1:
            raise ValueError("context-length must be positive")
        policy = load_policy(args.policy)
        path = Path(args.cases)
        cases = load_cases(path)
        reviewed = None
        if "heldout" in path.name.casefold():
            kind = "ambiguity" if "ambiguity" in path.stem.casefold() else "base"
            reviewed = validate_reviewed_set(path, cases, kind=kind, policy_doc=policy,
                                            development_cases=load_cases(ROOT / "eval/scenarios.jsonl"))
        constitution = Path(args.constitution).read_text()
        if not constitution.strip():
            raise ValueError("constitution must not be empty")
        validate_comparison_cases(cases)
        hashes = {name: hashlib.sha256(file.read_bytes()).hexdigest() for name, file in (
            ("cases_sha256", path), ("constitution_sha256", Path(args.constitution)),
            ("policy_sha256", Path(args.policy)), ("corpus_sha256", Path(args.db)))}
        options = dict(temperature=args.temperature, num_predict=args.num_predict, seed=args.seed)
        if args.context_length is not None:
            options["num_ctx"] = args.context_length
        think = None if args.thinking == "model-default" else args.thinking == "on"
        if args.backend == "fake":
            generator = lambda messages: HostOutput(text="Offline placeholder response; not model behavior.")
            interpreter = FakeInterpreter([])
        else:
            generator = OllamaGenerator(args.model, args.host, args.timeout, options, think=think)
            interpreter = OllamaInterpreter(model=args.assessment_model or args.model,
                                            host=args.host, timeout_s=args.timeout,
                                            num_ctx=args.context_length, think=think)
        report = run_comparison(cases, generator, interpreter, policy, args.db,
                                constitution, repeats=args.repeats)
        report.update(backend=args.backend, generation_model=args.model if args.backend == "ollama" else None,
                      assessment_model=(args.assessment_model or args.model) if args.backend == "ollama" else None,
                      generation_options=options, timeout_s=args.timeout,
                      thinking=args.thinking,
                      assessment_options=dict(temperature=0, num_predict=512, num_ctx=args.context_length),
                      host=args.host if args.backend == "ollama" else None,
                      cases_path=str(path), **hashes,
                      policy_version=policy.get("policy_version"), corpus_version="0.1.0-draft")
        if reviewed:
            report["label"] = "owner-attested held-out evaluation — experimental, not a release claim"
            report["holdout"] = reviewed
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"Saved {len(report['cases'])} response records to {output}; human grading pending.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

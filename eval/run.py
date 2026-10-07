#!/usr/bin/env python3
"""PEA evaluation harness (plan §6, M6a).

Runs scenario JSONL through the real assessment core (assess.py) and
reports disposition metrics with counts and denominators.

HARD RULE: there is no held-out set yet (plan §M6.1 requires >=120
owner-reviewed scenarios before one exists). Every output of this
harness is labelled "development set only — held-out set pending
owner review". Automated grading triages only; it cannot provide the
theological ground truth (plan §M6.3 — see eval/rubric.md).

Usage:
    python eval/run.py --cases eval/scenarios.jsonl --backend fake \
        [--db corpus/units.db] [--policy policy/rules.json] \
        [--output artifacts/eval.json] [--model NAME] [--host URL]
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

# Works from a checkout without install; harmless when installed.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from patristic_ethics.assess import assess  # noqa: E402
from patristic_ethics.context import build_envelope  # noqa: E402
from patristic_ethics.interpreter import FakeInterpreter, Observation  # noqa: E402
from patristic_ethics.policy import load_policy  # noqa: E402

DEV_ONLY_LABEL = "development set only — held-out set pending owner review"
HELDOUT_PENDING_MESSAGE = (
    "The held-out evaluation set does not exist yet. Plan §M6.1 requires "
    ">=120 human-reviewed base scenarios, balanced and separate from the "
    "development cases, before any held-out evaluation can run. The project "
    "owner must author and review that set; until then every PEA result is "
    "development-set triage only."
)

EXPECTED_DISPOSITIONS = ["allow", "guide", "refuse", "clarify", "review"]
ACTUAL_DISPOSITIONS = EXPECTED_DISPOSITIONS + ["withhold"]
_PREVENTING = {"refuse", "clarify", "review", "withhold"}
_ACTION_TO_DISPOSITION = {
    "proceed": "allow",
    "guide": "guide",
    "refuse": "refuse",
    "clarify": "clarify",
    "review": "review",
}


def load_cases(path: Path) -> list[dict]:
    """Read scenario JSONL; one JSON object per line, blank lines skipped."""
    cases: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for i, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{i}: malformed JSON: {e}") from e
    if not cases:
        raise ValueError(f"{path}: no scenarios found (empty cases file)")
    return cases


def envelope_for(scenario: dict, policy_version: str, corpus_version: str):
    """Build a validated ContextEnvelope from a scenario's `turns`.

    request = concatenation of user turns (the full objective reaches the
    interpreter and the lexical fallback, not just the last sentence).
    earlier_excerpts = all turns except the last (multi-turn only).
    history.complete = True for multi-turn cases (the file contains them).
    """
    sid = scenario["id"]
    turns = scenario["turns"]
    multi = len(turns) > 1
    return build_envelope(
        host={"name": "pea-eval", "version": "0", "mode": "eval"},
        session={"id": f"eval-{sid}"},
        turn={"id": f"{sid}-turn"},
        stage="input",
        request=" ".join(t["text"] for t in turns if t["role"] == "user"),
        messages=[
            {
                "role": t["role"],
                "source_id": f"{sid}-m{i}",
                "seq": i,
                "text": t["text"],
                "origin": t["role"],
            }
            for i, t in enumerate(turns)
        ],
        earlier_excerpts=(
            [{"source_id": f"{sid}-m{i}", "text": t["text"]} for i, t in enumerate(turns[:-1])]
            if multi
            else []
        ),
        history={"complete": multi},
        policy_version=policy_version,
        corpus_version=corpus_version,
    )


def _rate(num: int, den: int):
    """Simple proportion, or None when the denominator is zero (reported)."""
    return round(num / den, 4) if den else None


def run_cases(
    cases: list[dict],
    interpreter,
    policy_doc: dict,
    db_path,
    corpus_version: str = "0.1.0-draft",
) -> dict:
    """Assess every scenario and return the full report dict.

    Testable entry point: no CLI, no file writes. `interpreter` is any
    object satisfying the Interpreter protocol (FakeInterpreter offline).
    """
    policy_version = policy_doc.get("policy_version", "")
    records: list[dict] = []
    for sc in cases:
        env = envelope_for(sc, policy_version, corpus_version)
        res = assess(
            env,
            interpreter=interpreter,
            policy_doc=policy_doc,
            db_path=db_path,
            corpus_version=corpus_version,
        )
        decision = res.decision
        expected = sc.get("expected_disposition")
        # Disposition when a Decision exists; otherwise derive from the
        # action (interpreter failure never yields a Decision).
        actual = (
            decision.disposition
            if decision is not None
            else _ACTION_TO_DISPOSITION.get(res.action, "withhold")
        )
        principle_ids = list(decision.principle_ids) if decision is not None else []
        expected_principles = sc.get("expected_principles") or []
        overlap = sorted(set(principle_ids) & set(expected_principles))
        records.append(
            {
                "id": sc["id"],
                "family": sc.get("family", ""),
                "tags": sc.get("tags", []),
                "multi_turn": len(sc.get("turns", [])) > 1,
                "expected": expected,
                "actual": actual,
                "action": res.action,
                "match": actual == expected,
                "principle_ids": principle_ids,
                "expected_principles": expected_principles,
                "principle_overlap": overlap,
                "source_status": decision.source_status if decision is not None else None,
                "failure_kind": res.failure.kind if res.failure is not None else None,
                "latency_ms": res.audit.get("latency_ms"),
                "guidance_excerpt": (res.guidance.text[:200] if res.guidance else ""),
            }
        )
    return metrics(records)


def metrics(records: list[dict]) -> dict:
    """Compute all metrics from per-case records (pure function)."""
    n = len(records)
    matched = sum(1 for r in records if r["match"])
    confusion = {e: {a: 0 for a in ACTUAL_DISPOSITIONS} for e in EXPECTED_DISPOSITIONS}
    for r in records:
        if r["expected"] in confusion and r["actual"] in ACTUAL_DISPOSITIONS:
            confusion[r["expected"]][r["actual"]] += 1

    expected_counts = {d: sum(1 for r in records if r["expected"] == d) for d in EXPECTED_DISPOSITIONS}
    actual_counts = {d: sum(1 for r in records if r["actual"] == d) for d in ACTUAL_DISPOSITIONS}

    per_disposition = {}
    for d in EXPECTED_DISPOSITIONS:
        correct = confusion[d][d]
        per_disposition[d] = {
            "correct": correct,
            "precision": _rate(correct, actual_counts[d]),
            "recall": _rate(correct, expected_counts[d]),
        }

    refuse_cases = [r for r in records if r["expected"] == "refuse"]
    refuse_recognized = sum(1 for r in refuse_cases if r["actual"] == "refuse")
    refuse_prevented = sum(1 for r in refuse_cases if r["actual"] in _PREVENTING)
    allow_cases = [r for r in records if r["expected"] == "allow"]
    false_interventions = sum(1 for r in allow_cases if r["actual"] != "allow")
    task_completed = sum(1 for r in allow_cases if r["action"] == "proceed")
    principle_den = [r for r in refuse_cases if r["expected_principles"]]
    principle_hit = sum(1 for r in principle_den if r["principle_overlap"])
    multi = [r for r in records if r["multi_turn"]]

    families: dict[str, dict] = {}
    for r in records:
        f = families.setdefault(r["family"], {"n": 0, "matched": 0, "match_rate": None})
        f["n"] += 1
        f["matched"] += int(r["match"])
    for f in families.values():
        f["match_rate"] = _rate(f["matched"], f["n"])

    latencies = [r["latency_ms"] for r in records if r["latency_ms"] is not None]
    return {
        "counts": {
            "total": n,
            "matched": matched,
            "by_expected": expected_counts,
            "by_actual": actual_counts,
            "failures": sum(1 for r in records if r["failure_kind"]),
        },
        "match_rate": _rate(matched, n),
        "confusion_matrix": confusion,
        "per_disposition": per_disposition,
        "refusal_recall": _rate(refuse_recognized, len(refuse_cases)),
        "refusal_recognized": refuse_recognized,
        "refuse_expected": len(refuse_cases),
        "prevention_rate": _rate(refuse_prevented, len(refuse_cases)),
        "prevented": refuse_prevented,
        "false_intervention_rate": _rate(false_interventions, len(allow_cases)),
        "false_interventions": false_interventions,
        "allow_expected": len(allow_cases),
        "task_completion_rate": _rate(task_completed, len(allow_cases)),
        "task_completed": task_completed,
        "principle_match_accuracy": _rate(principle_hit, len(principle_den)),
        "principle_matched": principle_hit,
        "principle_denominator": len(principle_den),
        "multi_turn": {
            "count": len(multi),
            "matched": sum(1 for r in multi if r["match"]),
            "match_rate": _rate(sum(1 for r in multi if r["match"]), len(multi)),
            "refuse_expected": sum(1 for r in multi if r["expected"] == "refuse"),
            "refuse_matched": sum(1 for r in multi if r["expected"] == "refuse" and r["match"]),
        },
        "families": families,
        "latency_ms": {
            "mean": round(statistics.fmean(latencies), 2) if latencies else None,
            "max": max(latencies) if latencies else None,
        },
        "note": "small n; simple proportions only, no confidence intervals",
        "cases": records,
    }


def summary(report: dict) -> str:
    """Compact markdown-ish human summary (stdout)."""
    c = report["counts"]
    lines = [
        f"# PEA eval — {report['backend']} backend ({report['cases_path']})",
        f"label: {report['label']}",
        f"cases: {c['total']} | matched: {c['matched']} | match rate: {report['match_rate']}",
        "confusion matrix (rows = expected, columns = actual):",
        "| expected \\ actual | " + " | ".join(ACTUAL_DISPOSITIONS) + " |",
        "|" + "---|" * (len(ACTUAL_DISPOSITIONS) + 1),
    ]
    for e in EXPECTED_DISPOSITIONS:
        row = report["confusion_matrix"][e]
        lines.append(f"| {e} | " + " | ".join(str(row[a]) for a in ACTUAL_DISPOSITIONS) + " |")
    lines += [
        f"refusal recall: {report['refusal_recall']} ({report['refusal_recognized']}/{report['refuse_expected']})"
        f" | prevention rate: {report['prevention_rate']} ({report['prevented']}/{report['refuse_expected']})",
        f"false interventions on allow: {report['false_intervention_rate']}"
        f" ({report['false_interventions']}/{report['allow_expected']})"
        f" | task completion: {report['task_completion_rate']} ({report['task_completed']}/{report['allow_expected']})",
        f"principle match (refuse cases): {report['principle_match_accuracy']}"
        f" ({report['principle_matched']}/{report['principle_denominator']})",
        f"multi-turn: {report['multi_turn']['matched']}/{report['multi_turn']['count']} matched"
        f" (refuse: {report['multi_turn']['refuse_matched']}/{report['multi_turn']['refuse_expected']})",
        f"failures: {c['failures']} | latency mean {report['latency_ms']['mean']} ms, max {report['latency_ms']['max']} ms",
        report["label"] + ".",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="PEA evaluation harness (development set triage)")
    ap.add_argument("--cases", required=True, help="scenario JSONL path")
    ap.add_argument("--backend", choices=["fake", "ollama"], default="fake")
    ap.add_argument("--db", default="corpus/units.db")
    ap.add_argument("--policy", default="policy/rules.json")
    ap.add_argument("--output", default="artifacts/eval.json")
    ap.add_argument("--model", default="ornith-1.5:9b")
    ap.add_argument("--host", default="http://localhost:11434")
    ap.add_argument("--corpus-version", default="0.1.0-draft")
    args = ap.parse_args(argv)

    cases_path = Path(args.cases)
    if not cases_path.exists():
        print(f"error: cases file not found: {cases_path}", file=sys.stderr)
        if "heldout" in cases_path.name:
            print(HELDOUT_PENDING_MESSAGE, file=sys.stderr)
        return 2

    policy_doc = load_policy(args.policy)
    if args.backend == "fake":
        # Empty script -> default benign observation, no topics: assess()
        # falls back to the emergency lexical path. This is deliberate
        # (offline triage) and is a documented caveat in the results.
        interpreter = FakeInterpreter([])
    else:
        from patristic_ethics.interpreter import OllamaInterpreter

        interpreter = OllamaInterpreter(model=args.model, host=args.host)

    cases = load_cases(cases_path)
    report = run_cases(cases, interpreter, policy_doc, args.db, args.corpus_version)
    is_heldout = "heldout" in cases_path.name
    report["label"] = "held-out evaluation" if is_heldout else DEV_ONLY_LABEL
    report["backend"] = args.backend
    report["model"] = args.model if args.backend == "ollama" else None
    report["cases_path"] = str(cases_path)
    report["policy_version"] = policy_doc.get("policy_version", "")
    report["corpus_version"] = args.corpus_version

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(summary(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
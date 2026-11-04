#!/usr/bin/env python3
"""Measure remote interpreter latency on development scenarios.

This is a p50/p95 smoke, not an accuracy evaluation. It uses the same
ContextEnvelope shape as the evaluation harness and the remote interpreter
selected in Step 3. The API key is read from the provider's environment
variable; it is never printed.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from patristic_ethics.context import build_envelope  # noqa: E402
from patristic_ethics.interpreter import (  # noqa: E402
    InterpreterUnavailable,
    OllamaInterpreter,
    RemoteInterpreter,
)


def load_cases(path: Path) -> list[dict]:
    cases = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            cases.append(json.loads(line))
    return cases


def envelope_for(case: dict, policy_version: str, corpus_version: str):
    turns = case["turns"]
    sid = case["id"]
    multi = len(turns) > 1
    return build_envelope(
        host={"name": "pea-latency", "version": "0", "mode": "eval"},
        session={"id": f"latency-{sid}"},
        turn={"id": f"{sid}-turn"},
        stage="input",
        request=" ".join(t["text"] for t in turns if t["role"] == "user"),
        messages=[
            {
                "role": turn["role"],
                "source_id": f"{sid}-m{i}",
                "seq": i,
                "text": turn["text"],
                "origin": turn["role"],
            }
            for i, turn in enumerate(turns)
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


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil((p / 100) * len(ordered)) - 1))
    return round(ordered[index], 3)


def main() -> int:
    parser = argparse.ArgumentParser(description="Remote interpreter p50/p95 smoke")
    parser.add_argument("--cases", default=str(ROOT / "eval" / "scenarios.jsonl"))
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--backend", choices=["ollama", "remote"], default="ollama")
    parser.add_argument("--provider", default="openai")
    parser.add_argument("--model", default="deepseek-v4.1-flash:cloud")
    parser.add_argument("--host", default="http://localhost:11434")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--api-key-env", default=None)
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--output", default=str(ROOT / "artifacts" / "remote-latency.json"))
    args = parser.parse_args()

    try:
        if args.backend == "ollama":
            interpreter = OllamaInterpreter(
                model=args.model,
                host=args.host,
                timeout_s=args.timeout,
            )
        else:
            interpreter = RemoteInterpreter(
                provider=args.provider,
                model=args.model,
                base_url=args.base_url,
                api_key_env=args.api_key_env,
                timeout_s=args.timeout,
            )
    except ValueError as exc:
        print(f"setup failed: {exc}", file=sys.stderr)
        return 2

    policy = json.loads((ROOT / "policy" / "rules.json").read_text(encoding="utf-8"))
    policy_version = policy.get("policy_version", "")
    cases = load_cases(Path(args.cases))[: args.limit]
    latencies: list[float] = []
    attempt_latencies: list[float] = []
    failures: list[dict] = []
    for case in cases:
        envelope = envelope_for(case, policy_version, "0.1.0-draft")
        start = time.perf_counter()
        failed = False
        try:
            interpreter.interpret(envelope)
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)
            attempt_latencies.append(elapsed)
        except InterpreterUnavailable as exc:
            failed = True
            elapsed = time.perf_counter() - start
            attempt_latencies.append(elapsed)
            failures.append(
                {
                    "case": case.get("id"),
                    "kind": exc.failure.kind,
                    "reason": exc.failure.reason,
                    "seconds": round(elapsed, 3),
                }
            )
        print(f"{case.get('id')}: {'fail' if failed else 'ok'}", file=sys.stderr)

    report = {
        "date": date.today().isoformat(),
        "scope": "development scenarios; interpreter latency only; not accuracy evidence",
        "backend": args.backend,
        "provider": args.provider if args.backend == "remote" else None,
        "model": args.model,
        "host": args.host if args.backend == "ollama" else None,
        "timeout_s": args.timeout,
        "cases_requested": len(cases),
        "successes": len(latencies),
        "failures": failures,
        "p50_s": percentile(latencies, 50),
        "p95_s": percentile(latencies, 95),
        "mean_s": round(statistics.mean(latencies), 3) if latencies else None,
        "max_s": round(max(latencies), 3) if latencies else None,
        "p50_all_s": percentile(attempt_latencies, 50),
        "p95_all_s": percentile(attempt_latencies, 95),
        "success_rate": round(len(latencies) / len(cases), 4) if cases else None,
        "all_attempts_succeeded": not failures,
        "target_p95_s": 8.0,
        "p95_target_met": (
            percentile(attempt_latencies, 95) is not None
            and percentile(attempt_latencies, 95) <= 8.0
        ),
        "gate_met": (
            not failures
            and percentile(attempt_latencies, 95) is not None
            and percentile(attempt_latencies, 95) <= 8.0
        ),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"wrote {output}", file=sys.stderr)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

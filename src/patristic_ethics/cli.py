"""PEA command-line interface (plan §7): assess + corpus tools.

Stdout protocol (FROZEN for the future OpenCode adapter): `assess`
writes exactly ONE AssessResult JSON object, single line, to stdout.
All diagnostics go to stderr. Corpus subcommands print human-readable
lines (validate/build) or JSON lines (search).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from . import corpus
from .assess import assess
from .context import validate_envelope
from .interpreter import FakeInterpreter, OllamaInterpreter
from .policy import load_policy

DEFAULT_DB = "corpus/units.db"
DEFAULT_POLICY = "policy/rules.json"
DEFAULT_MODEL = "ornith-1.5:9b"
DEFAULT_HOST = "http://localhost:11434"
DEFAULT_TIMEOUT = 600.0


def _err(msg: str) -> None:
    print(msg, file=sys.stderr)


def _result_payload(result) -> dict:
    """AssessResult -> plain JSON dict (decision/guidance/failure may be None)."""
    return {
        "action": result.action,
        "decision": asdict(result.decision) if result.decision is not None else None,
        "guidance": asdict(result.guidance) if result.guidance is not None else None,
        "failure": asdict(result.failure) if result.failure is not None else None,
        "audit": result.audit,
    }


def _build_interpreter(args):
    if args.backend == "fake":
        # Empty script: FakeInterpreter defaults to a benign observation.
        return FakeInterpreter([])
    return OllamaInterpreter(model=args.model, host=args.host, timeout_s=args.timeout)


def _cmd_assess(args) -> int:
    try:
        raw = Path(args.input).read_text(encoding="utf-8") if args.input else sys.stdin.read()
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("expected a JSON object")
        envelope = validate_envelope(data)  # EnvelopeError subclasses ValueError
    except (OSError, ValueError) as e:
        _err(json.dumps({"error": "malformed input", "detail": str(e)}))
        return 2

    try:
        policy_doc = load_policy(args.policy)
        interpreter = _build_interpreter(args)
    except Exception as e:  # policy load or backend construction failure
        _err(json.dumps({"error": "setup failed", "detail": str(e)}))
        return 1

    result = assess(
        envelope,
        interpreter=interpreter,
        policy_doc=policy_doc,
        db_path=args.db,
        corpus_version=envelope.corpus_version,
    )
    print(json.dumps(_result_payload(result), ensure_ascii=False))
    return 0


def _load_and_problems(seed: str):
    """Load a seed and return (units, problems); a load error is one problem."""
    try:
        units = corpus.load_seed(seed)
    except ValueError as e:
        return None, [str(e)]
    return units, corpus.validate_units(units)


def _cmd_corpus_validate(args) -> int:
    units, problems = _load_and_problems(args.seed)
    if problems:
        for p in problems:
            _err(p)
        print(f"PROBLEMS: {len(problems)}")
        return 1
    print(f"OK: {len(units)} units")
    return 0


def _cmd_corpus_build(args) -> int:
    _, problems = _load_and_problems(args.seed)
    if problems:
        for p in problems:
            _err(p)
        print(f"PROBLEMS: {len(problems)}")
        return 1
    print(str(corpus.build_db(args.seed, args.db)))
    return 0


def _cmd_corpus_search(args) -> int:
    if not Path(args.db).exists():
        _err(f"db not found: {args.db}")
        return 1
    try:
        hits = corpus.search_passages(args.db, args.query, limit=args.limit)
    except Exception as e:  # FTS5 syntax or sqlite errors are user input
        _err(f"search failed: {e}")
        return 1
    for u in hits:
        print(json.dumps({
            "id": u.id,
            "author": u.author,
            "work": u.work,
            "locus": u.locus,
            "language": u.language,
            "text": u.text,
        }, ensure_ascii=False))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="patristic-ethics", description="PEA ethics assessment CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("assess", help="assess one context envelope")
    p.add_argument("--stdin", action="store_true", help="read envelope JSON from stdin (default without --input)")
    p.add_argument("--input", metavar="PATH", help="read envelope JSON from PATH instead of stdin")
    p.add_argument("--backend", choices=["fake", "ollama"], default="fake")
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--policy", default=DEFAULT_POLICY)
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    p.set_defaults(func=_cmd_assess)

    c = sub.add_parser("corpus", help="seed corpus tools")
    csub = c.add_subparsers(dest="corpus_command", required=True)
    cv = csub.add_parser("validate", help="validate a seed JSONL file")
    cv.add_argument("seed")
    cv.set_defaults(func=_cmd_corpus_validate)
    cb = csub.add_parser("build", help="build the SQLite index from a seed")
    cb.add_argument("seed")
    cb.add_argument("--db", default=DEFAULT_DB)
    cb.set_defaults(func=_cmd_corpus_build)
    cs = csub.add_parser("search", help="FTS5 search the index")
    cs.add_argument("query")
    cs.add_argument("--db", default=DEFAULT_DB)
    cs.add_argument("--limit", type=int, default=5)
    cs.set_defaults(func=_cmd_corpus_search)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
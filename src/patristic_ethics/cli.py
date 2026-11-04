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

from . import citations, corpus, csl, further_reading, paths, provenance
from .assess import assess
from .context import validate_envelope
from .interpreter import FakeInterpreter, OllamaInterpreter, PROVIDERS, RemoteInterpreter
from .policy import load_policy

DEFAULT_DB = str(paths.default_db_path())
DEFAULT_POLICY = str(paths.default_policy_path())
DEFAULT_MODEL = "deepseek-v4.1-flash:cloud"
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


def positive_context_length(value: str) -> int:
    length = int(value)
    if length <= 0:
        raise argparse.ArgumentTypeError("context length must be positive")
    return length


def _build_interpreter(args):
    if args.backend == "fake":
        # Empty script: FakeInterpreter defaults to a benign observation.
        return FakeInterpreter([])
    if args.backend == "ollama":
        return OllamaInterpreter(model=args.model or DEFAULT_MODEL, host=args.host,
                                 timeout_s=args.timeout,
                                 num_ctx=args.context_length,
                                 think={"model-default": None, "on": True, "off": False}[args.thinking])
    return RemoteInterpreter(
        provider=args.provider,
        model=args.model,
        base_url=args.remote_url,
        api_key_env=args.api_key_env,
        timeout_s=args.timeout,
        json_mode=args.json_mode,
    )


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
    assert units is not None
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


def _load_csl(path: str, lane: str):
    try:
        records = csl.load_csl(path)
    except ValueError as e:
        return None, [str(e)]
    return records, csl.validate_csl(records, lane)


def _cmd_corpus_validate_csl(args) -> int:
    records, problems = _load_csl(args.path, args.lane)
    if problems:
        for p in problems:
            _err(p)
        print(f"PROBLEMS: {len(problems)}")
        return 1
    assert records is not None
    print(f"OK: {len(records)} {args.lane} records")
    return 0


def _cmd_corpus_build_csl(args) -> int:
    records, problems = _load_csl(args.path, args.lane)
    if problems:
        for p in problems:
            _err(p)
        print(f"PROBLEMS: {len(problems)}")
        return 1
    assert records is not None
    db = args.db or f"corpus/{args.lane}.db"
    print(str(csl.build_csl_db(records, db, args.lane)))
    return 0


def _load_further_reading(path: str, seed: str):
    try:
        records = further_reading.load_further_reading(path)
        known = {u.id for u in corpus.load_seed(seed)}
    except (OSError, ValueError) as e:
        return None, [str(e)]
    return records, further_reading.validate_further_reading(records, known)


def _cmd_further_reading(args) -> int:
    if not Path(args.path).exists():
        _err(f"no further-reading file: {args.path}")
        return 1
    records, problems = _load_further_reading(args.path, args.seed)
    if problems:
        for p in problems:
            _err(p)
        return 1
    assert records is not None
    if args.principle:
        records = [
            r for r in records
            if args.principle in (r.get("custom") or {}).get("principle_ids", [])
        ]
    if args.reviewed_only:
        records = [
            r for r in records
            if (r.get("custom") or {}).get("review_status") == "reviewed"
        ]
    if args.format == "json":
        for record in records:
            print(json.dumps(record, ensure_ascii=False))
    elif args.format == "markdown":
        print(further_reading.render_markdown(records), end="")
    else:
        for record in records:
            print(further_reading.format_text(record))
    return 0


def _cmd_corpus_validate_further_reading(args) -> int:
    records, problems = _load_further_reading(args.path, args.seed)
    if problems:
        for p in problems:
            _err(p)
        print(f"PROBLEMS: {len(problems)}")
        return 1
    assert records is not None
    print(f"OK: {len(records)} further-reading records")
    return 0


def _cmd_corpus_validate_primary_citations(args) -> int:
    try:
        units = {u.id: u for u in corpus.load_seed(args.seed)}
        records = citations.load_primary_citations(args.path)
    except ValueError as e:
        _err(str(e))
        print("PROBLEMS: 1")
        return 1
    problems = citations.validate_primary_citations(records, units)
    if problems:
        for p in problems:
            _err(p)
        print(f"PROBLEMS: {len(problems)}")
        return 1
    print(f"OK: {len(records)} primary citations")
    return 0


def _cmd_corpus_validate_secondary(args) -> int:
    try:
        known = {u.id for u in corpus.load_seed(args.seed)}
        records = citations.load_secondary(args.path)
    except ValueError as e:
        _err(str(e))
        print("PROBLEMS: 1")
        return 1
    problems = citations.validate_secondary(records, known)
    if problems:
        for p in problems:
            _err(p)
        print(f"PROBLEMS: {len(problems)}")
        return 1
    print(f"OK: {len(records)} secondary records")
    return 0


def _cmd_corpus_validate_provenance(args) -> int:
    try:
        known = {u.id for u in corpus.load_seed(args.seed)}
        records = provenance.load_provenance(args.path)
    except ValueError as e:
        _err(str(e))
        print("PROBLEMS: 1")
        return 1
    problems = provenance.validate_provenance(records, known)
    if problems:
        for p in problems:
            _err(p)
        print(f"PROBLEMS: {len(problems)}")
        return 1
    print(f"OK: {len(records)} provenance records")
    return 0


def _cmd_corpus_search_csl(args) -> int:
    if not Path(args.db).exists():
        _err(f"db not found: {args.db}")
        return 1
    try:
        hits = csl.search_csl(args.db, args.query, limit=args.limit)
    except Exception as e:
        _err(f"search failed: {e}")
        return 1
    for u in hits:
        print(json.dumps({
            "id": u.id,
            "source_class": u.source_class,
            "citation_index": u.citation_index,
            "author": u.author,
            "title": u.title,
            "locus": u.locus,
            "text": u.text,
        }, ensure_ascii=False))
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
    p.add_argument("--backend", choices=["fake", "ollama", "remote"], default="fake")
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--policy", default=DEFAULT_POLICY)
    p.add_argument("--model", default=None)
    p.add_argument("--provider", choices=sorted(PROVIDERS), default="openai",
                   help="remote provider preset (default: openai)")
    p.add_argument("--remote-url", default=None,
                   help="override the provider base URL, e.g. https://host/v1")
    p.add_argument("--api-key-env", default=None,
                   help="environment variable holding the API key")
    p.add_argument("--no-json-mode", dest="json_mode", action="store_false",
                   help="do not request response_format=json_object")
    p.set_defaults(json_mode=True)
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    p.add_argument("--context-length", type=positive_context_length, default=None,
                   help="Ollama interpreter context length; default uses model settings")
    p.add_argument("--thinking", choices=["model-default", "on", "off"], default="model-default",
                   help="Ollama interpreter thinking mode")
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

    cv = csub.add_parser("validate-csl", help="validate a CSL-JSON lane file")
    cv.add_argument("path")
    cv.add_argument("--lane", choices=sorted(csl.LANE_SOURCE_CLASS), required=True)
    cv.set_defaults(func=_cmd_corpus_validate_csl)

    cb = csub.add_parser("build-csl", help="build a CSL-JSON lane database")
    cb.add_argument("path")
    cb.add_argument("--lane", choices=sorted(csl.LANE_SOURCE_CLASS), required=True)
    cb.add_argument("--db", default=None)
    cb.set_defaults(func=_cmd_corpus_build_csl)

    cs = csub.add_parser("search-csl", help="FTS5 search a CSL-JSON lane database")
    cs.add_argument("query")
    cs.add_argument("--db", required=True)
    cs.add_argument("--limit", type=int, default=5)
    cs.set_defaults(func=_cmd_corpus_search_csl)

    cp = csub.add_parser("validate-provenance", help="validate linked CSL provenance records")
    cp.add_argument("path")
    cp.add_argument("--seed", default="corpus/seed.jsonl")
    cp.set_defaults(func=_cmd_corpus_validate_provenance)

    cpc = csub.add_parser("validate-primary-citations", help="validate primary CSL citations")
    cpc.add_argument("path")
    cpc.add_argument("--seed", default="corpus/seed.jsonl")
    cpc.set_defaults(func=_cmd_corpus_validate_primary_citations)

    cse = csub.add_parser("validate-secondary", help="validate secondary CSL records")
    cse.add_argument("path")
    cse.add_argument("--seed", default="corpus/seed.jsonl")
    cse.set_defaults(func=_cmd_corpus_validate_secondary)

    cfr = csub.add_parser("validate-further-reading", help="validate the further-reading bibliography")
    cfr.add_argument("path")
    cfr.add_argument("--seed", default="corpus/seed.jsonl")
    cfr.set_defaults(func=_cmd_corpus_validate_further_reading)

    fr = sub.add_parser("further-reading", help="list the further-reading bibliography")
    fr.add_argument("--path", default="corpus/further_reading.jsonl")
    fr.add_argument("--principle", choices=sorted(further_reading.PRINCIPLE_IDS), default=None)
    fr.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    fr.add_argument("--reviewed-only", action="store_true")
    fr.add_argument("--seed", default="corpus/seed.jsonl")
    fr.set_defaults(func=_cmd_further_reading)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
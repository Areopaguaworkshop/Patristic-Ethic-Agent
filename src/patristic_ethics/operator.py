"""Local operator review console. This is a workflow helper, not an OS boundary."""

from __future__ import annotations

import argparse
import json
import os
import sys

from .runtime_store import OperatorBoundaryError, RuntimeStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pea-operator")
    parser.add_argument("--db", default="corpus/runtime.db")
    commands = parser.add_subparsers(dest="command", required=True)
    listing = commands.add_parser("list", help="list review records")
    listing.add_argument("--status", choices=["pending", "approved", "denied", "expired"])
    commands.add_parser("attempts", help="inspect unresolved dispatch attempts; never retry")
    show = commands.add_parser("show", help="show exact action and context for a review")
    show.add_argument("review_id")
    resolve = commands.add_parser("resolve", help="resolve a pending review")
    resolve.add_argument("review_id")
    resolve.add_argument("decision", choices=["approved", "denied"])
    resolve.add_argument("--note", required=True)
    args = parser.parse_args(argv)

    store = RuntimeStore(args.db)
    try:
        if args.command == "list":
            result = store.list_reviews(args.status)
        elif args.command == "attempts":
            result = store.stuck_attempts(older_than_s=0.0)
        elif args.command == "show":
            result = store.get_review(args.review_id)
            if result is None:
                print("review not found", file=sys.stderr)
                return 2
        else:
            token = os.environ.get("PEA_OPERATOR_TOKEN", "")
            result = store.resolve_review(
                args.review_id, args.decision, token, note=args.note
            )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (OperatorBoundaryError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    finally:
        store.conn.close()


if __name__ == "__main__":
    raise SystemExit(main())

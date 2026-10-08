# Shared native-adapter fixtures

`scenarios.jsonl` contains 23 development contract cases. Assessment actions are scripted: these cases are neither a semantic accuracy benchmark nor an owner-reviewed holdout. `tests/integration/test_shared_host_conformance.py` uses the same records for Codex/Claude Python handlers and the actual OpenCode plugin under Bun with a synthetic CLI and fixture SDK messages.

Each record has a stable ID, input/pre-action stage, request/arguments text, target or isolated session, scripted result, and optional fault. Tests assert protocol/guidance behavior, proposed arguments, incomplete history metadata, session isolation and covered OpenCode mock effects. Host-specific differences are intentional and documented in `docs/evaluation/host-conformance.md`.

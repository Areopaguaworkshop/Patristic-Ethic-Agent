# Patristic Ethics Agent (PEA)

PEA is an experimental dialogue/action review layer grounded in a draft Christian patristic constitution. It interprets expressed requests and context, applies deterministic policy, retrieves exact source quotations, and supplies guidance. It does not claim to read hidden intentions.

**Engineering backlog E1–E6 is implemented. This is not a qualified release:** policy/corpus editorial review, live host acceptance, operator OS isolation, untouched human-reviewed holdouts and backend accuracy/latency remain pending. Current acceptance: M2 complete; M0/M1/M3/M4/M5/M6 partial. See the [canonical plan](docs/plans/2026-10-06-pea-implementation-plan.md) and [remaining external dependencies](docs/plans/2026-10-08-remaining-engineering.md).

## Run from this checkout

Python 3.11+ is required. Install the locked dependencies when package-index access is available:

```sh
uv sync --frozen --extra dev
```

The existing `.venv` supports these source-checkout commands:

```sh
.venv/bin/python -m patristic_ethics.cli corpus validate corpus/seed.jsonl
.venv/bin/python -m patristic_ethics.cli corpus build corpus/seed.jsonl --db corpus/units.db
.venv/bin/python -m patristic_ethics.cli assess --backend fake --input tests/fixtures/assess/benign.json
.venv/bin/pytest -q
```

`fake` exercises plumbing and limited lexical fallback; it is not a usable semantic-quality claim. For configured local inference, use `assess --backend ollama` with `--model`, `--host`, `--timeout`, optional positive `--context-length`, and `--thinking model-default|on|off`. The installed `ornith-1.5:9b` diagnostic ran CPU-only and had substantial delays/timeouts; [the evidence](docs/evaluation/ollama-diagnostic.md) does not meet release gates.

## Host modes

| Host | Native adapter | Controlled display |
|---|---|---|
| OpenCode | Advisory prompt guidance and covered pre-tool gate; text-only SDK history | Tools-disabled runner checks effective config, buffers candidates and assesses before release; live managed-policy/compaction evidence incomplete |
| Codex | Covered prompt/pre-tool block protocol, optional hook-observed history; live delivery incomplete | Unsupported: preventive tools-disabled boundary not established |
| Claude Code | Covered prompt/pre-tool block protocol, optional hook-observed history; live delivery incomplete | Tools-disabled print/JSON runner with buffered review; live enforcement/continuation evidence incomplete |

Native hooks provide no general before-display guarantee. Their covered error responses require the hook process to remain alive. The [shared conformance report](docs/evaluation/host-conformance.md) covers synthetic adapter contracts, not installed-host enforcement. Host versions, examples and limits: [OpenCode](docs/hosts/opencode.md), [Codex](docs/hosts/codex.md), [Claude](docs/hosts/claude-code.md).

Controlled CLI examples use explicit backends/models:

```sh
.venv/bin/python -m patristic_ethics.controlled --backend ollama \
  --model ollama/ornith-1.5:9b --prompt 'Explain a Python addition function.'
.venv/bin/python -m patristic_ethics.claude_controlled --backend ollama \
  --prompt 'Explain a Python addition function.'
```

The Claude command invokes your configured Claude host and may require credentials/use paid inference. These commands are examples, not recorded successful live runs. Both clients accept `--interactive`, `--interpreter-context-length`, `--interpreter-thinking`, and opt-in `--revise-once`. Revision defaults off; when enabled, at most one fresh host correction is semantically/structurally rechecked with safe fallback. Rejected text is excluded from future visible history. Dialogue history is limited to 40 released messages / 16000 characters with explicit loss notices.

Native Python history is opt-in through the operator-configured `PEA_HISTORY_DB` path; transcript paths supplied by hook payloads are not read. This observed history remains incomplete. Keep native plugins and controlled profiles separate. Shell-capable review workflows require deployment isolation first; [the operator boundary](docs/operator-boundary.md) remains unproven at OS level.

## Evaluation and operator workflow

```sh
.venv/bin/python eval/compare.py --cases eval/scenarios.jsonl --backend fake --output /tmp/pea-comparison.json
.venv/bin/python eval/grade.py --report /tmp/pea-comparison.json \
  --grades /path/to/actual-reviewer-grades.jsonl --output /tmp/pea-reviewed-comparison.json
.venv/bin/python -m patristic_ethics.operator --db corpus/runtime.db attempts
```

Comparison outputs are development data. [Grade ingestion](docs/evaluation/human-grading.md) binds actual reviewer judgments to report/response hashes, keeps missing grades ungraded and preserves disagreements. No actual reviewer grades or release holdout exist. `attempts` inspects uncertain dispatches without resetting or retrying them; establish the external outcome before any new reviewed action.

Optional process checks require an environment that permits their transports:

```sh
PEA_RUN_BUN_TEST=1 .venv/bin/pytest -q tests/integration/test_shared_host_conformance.py tests/test_history_limits.py
PEA_RUN_STDIO_TEST=1 .venv/bin/pytest -q tests/integration/test_proxy.py
```

## Frozen experimental configuration

[Profile](docs/releases/pea-0.0.1-experimental-profile.json) and [snapshot](docs/releases/pea-0.0.1-experimental-snapshot.json) record baseline/tuning settings, declared host modes, package/model identity limits, source/corpus/policy/lock hashes and selected evidence. The profile is a declaration, not an automatically applied deployment preset. Verification checks local file integrity; it does not validate installed packages, model weights, credentials or host behavior.

```sh
.venv/bin/python eval/freeze.py --verify docs/releases/pea-0.0.1-experimental-snapshot.json
```

After changes, preserve the old snapshot and generate a new versioned one:

```sh
.venv/bin/python eval/freeze.py --profile docs/releases/pea-0.0.1-experimental-profile.json \
  --output /tmp/pea-new-experimental-snapshot.json
```

The tool refuses release-ready declarations, project-escaping/hidden/symlinked inputs and existing output files. It excludes private runtime/history databases, environment credentials, caches and dependency directories. A snapshot is experimental evidence, not proof that M0–M6 acceptance is complete.

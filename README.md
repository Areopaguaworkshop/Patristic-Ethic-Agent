# Patristic Ethics Agent (PEA)

PEA is an experimental dialogue/action review layer grounded in an owner-approved Christian patristic constitution; the corpus remains under review. It interprets expressed requests and context, applies deterministic policy, retrieves exact source quotations, and supplies guidance. It does not claim to read hidden intentions.

**Engineering backlog E1–E6 is implemented. This is not a qualified release:** corpus editorial review, live host acceptance, operator OS isolation, untouched human-reviewed holdouts and backend accuracy/latency remain pending. The policy is approved; the corpus remains partly draft. Current acceptance: M2 complete; M0/M1/M3/M4/M5/M6 partial. See the [canonical plan](docs/plans/2026-10-06-pea-implementation-plan.md) and [remaining external dependencies](docs/plans/2026-10-08-remaining-engineering.md).

## Packages

The 0.0.1 packaging is implemented and reviewed; nothing has been published yet.

| Registry | Package |
|---|---|
| PyPI | `patristic-ethics` |
| npm | `pea-mcp` |

No npm package has been published yet. The Codex and Claude Code hooks are Python console scripts in the PyPI package; the OpenCode plugin runs from this checkout. After publication, generic MCP hosts run `npx pea-mcp`. The launcher prefers `uvx --from patristic-ethics pea-mcp` and falls back to `python -m patristic_ethics.mcp_server`; it never installs packages silently. Names, review evidence, and publish commands: [docs/releases/publishing.md](docs/releases/publishing.md).

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

`fake` exercises plumbing and limited lexical fallback; it is not a usable semantic-quality claim. For configured local inference, use `assess --backend ollama` with `--model`, `--host`, `--timeout`, optional positive `--context-length`, and `--thinking model-default|on|off`. The project default is now `deepseek-v4.1-flash:cloud` through Ollama. The installed `ornith-1.5:9b` remains a local fallback; its CPU-only diagnostic had substantial delays/timeouts. The first 20-case `deepseek-v4.1-flash:cloud` latency smoke reached p95 6.512 s with 19/20 successes and one timeout; [the evidence](docs/evaluation/ollama-deepseek-latency.md).

## Remote interpreter backends

Remote inference uses `--backend remote` with a provider preset. API keys are read from environment variables; never pass them on the command line.

```sh
# OPENAI_API_KEY is set in the environment
.venv/bin/python -m patristic_ethics.cli assess --backend remote \
  --provider openai --model <model> --timeout 8 --input tests/fixtures/assess/benign.json

# DEEPSEEK_API_KEY is set in the environment
.venv/bin/python -m patristic_ethics.cli assess --backend remote \
  --provider deepseek --model deepseek-chat --timeout 8 --input tests/fixtures/assess/benign.json

# ANTHROPIC_API_KEY is set in the environment
.venv/bin/python -m patristic_ethics.cli assess --backend remote \
  --provider anthropic --model <model> --timeout 8 --input tests/fixtures/assess/benign.json

# Custom OpenAI-compatible endpoint
.venv/bin/python -m patristic_ethics.cli assess --backend remote \
  --provider custom --remote-url https://host/v1 --model <model> --timeout 8
```

Provider presets: `openai`, `deepseek`, `anthropic`, `openrouter`, `groq`, `together`, and `custom`. Use `--no-json-mode` for endpoints that reject `response_format=json_object`. The controlled clients accept the same `--backend remote` plus `--interpreter-provider`, `--interpreter-base-url`, `--interpreter-api-key-env`, and `--interpreter-timeout`.

## Operator isolation

```sh
sudo bash scripts/setup_operator_isolation.sh
```

The script creates a separate `pea-operator` identity, an operator-owned `runtime.db` with mode 0600, and a root-owned token with mode 0640. It prints direct-read and direct-write denial checks. It was syntax-checked here but not run: `sudo` requires interactive authentication. The current agent user is in the `sudo` group, so the script warns; remove that membership or run the agent under a non-admin identity before claiming the boundary.

## Host modes

| Host | Native adapter | Controlled display |
|---|---|---|
| OpenCode | Advisory prompt guidance and covered pre-tool gate; text-only SDK history | Tools-disabled runner checks effective config, buffers candidates and assesses before release; live managed-policy/compaction evidence incomplete |
| Codex | Covered prompt/pre-tool block protocol, optional hook-observed history; live delivery incomplete | Unsupported: preventive tools-disabled boundary not established |
| Claude Code | Covered prompt/pre-tool block protocol, optional hook-observed history; live delivery incomplete | Tools-disabled print/JSON runner with buffered review; live enforcement/continuation evidence incomplete |

Native hooks provide no general before-display guarantee. Their covered error responses require the hook process to remain alive. The [shared conformance report](docs/evaluation/host-conformance.md) covers synthetic adapter contracts, not installed-host enforcement. Host versions, examples and limits: [OpenCode](docs/hosts/opencode.md), [Codex](docs/hosts/codex.md), [Claude](docs/hosts/claude-code.md).

### Host setup

PEA does not configure a host automatically. Choose one surface:

| Surface | What it checks | Setup |
|---|---|---|
| MCP server | Exposes four read-only tools; the host must call `check_action` | Add `npx pea-mcp` to the host |
| MCP proxy | Every downstream `tools/call` before it runs | Launch the proxy as the host's MCP command |
| Codex hooks | Supported prompt and pre-tool events | Add `examples/codex/hooks.json` |
| Claude Code hooks | Supported prompt and pre-tool events | Add `examples/claude-code/settings.json` |
| OpenCode plugin | Advisory input and covered pre-tool events | Load `adapters/opencode/index.ts` |
| Controlled client | Input and output; buffers host output | Run `pea-controlled` or `pea-controlled-claude` |

**MCP server.** Add the server in the host configuration:

```json
{
  "mcpServers": {
    "pea": {
      "command": "npx",
      "args": ["pea-mcp"]
    }
  }
}
```

The server only exposes tools. The host or model must call `check_action`; the server cannot intercept other tools. For automatic tool gating, run the proxy as the host's MCP command:

```sh
python -m patristic_ethics.proxy \
  --downstream-cmd "npx -y @modelcontextprotocol/server-filesystem /tmp" \
  --backend ollama
```

For Pi, OMP and Hermes, add an MCP server named `pea` with the same command:

```sh
npx -y pea-mcp@0.0.1
# or the installed executable:
pea-mcp
```

These hosts expose the four PEA tools; they do not gate their own prompts or tools automatically.

**Codex.** Copy the example hook file and replace its command with the installed console script:

```sh
mkdir -p .codex
cp examples/codex/hooks.json .codex/hooks.json
# .codex/hooks.json: "command": "pea-codex-hook"
```

Enable hooks in `~/.codex/config.toml`:

```toml
[features]
hooks = true
```

Open the project in Codex and trust the project hook. An untrusted hook file is silently skipped. From this checkout, use `uv run --project "$PWD" python -m patristic_ethics.adapters.codex` as the command instead of `pea-codex-hook`.

**Claude Code.** Copy the example settings and replace the command with `pea-claude-hook`:

```sh
mkdir -p .claude
cp examples/claude-code/settings.json .claude/settings.json
# .claude/settings.json: "command": "pea-claude-hook"
```

To test without changing your user settings:

```sh
claude --settings "$PWD/examples/claude-code/settings.json" --print "How do I write a regex?"
```

The example covers `UserPromptSubmit` and `PreToolUse` for `Bash` only. From this checkout, use `uv run --project "$PWD" python -m patristic_ethics.adapters.claude_code`.

**OpenCode.** Copy the plugin and example config:

```sh
cp examples/opencode/opencode.json ./opencode.json
mkdir -p .opencode/plugins
cp adapters/opencode/index.ts .opencode/plugins/pea-ethics.ts
# opencode.json: "plugin": [".opencode/plugins/pea-ethics.ts"]
```

OpenCode 2.x uses the v2 plugin schema. The bundled `adapters/opencode/index.ts` targets 1.18.x and fails to load on 2.2.5. Use the `pea` MCP server or the controlled client on OpenCode 2.x; keep the plugin for 1.18.x.

Set the CLI and data paths in the host environment:

```sh
export PEA_CLI="uv run --project $PWD python -m patristic_ethics.cli"
export PEA_DB="$PWD/corpus/units.db"
export PEA_POLICY="$PWD/policy/rules.json"
export PEA_BACKEND="ollama"
```

**Controlled clients.** The controlled client is the only before-display path. For OpenCode, put the tools-disabled profile in the target directory, then run:

```sh
cp examples/opencode/controlled/opencode.json ./opencode.json
pea-controlled --prompt "How do I kill a process on Linux?" \
  --dir . --model ollama/deepseek-v4.1-flash:cloud --backend ollama
```

For Claude Code:

```sh
pea-controlled-claude --interactive --dir . --backend ollama
```

From this checkout, use `uv run --project "$PWD" python -m patristic_ethics.controlled` or `...claude_controlled`. The client buffers all host stdout and releases only assessed text. `--revise-once` is opt-in.

Publishing either package does not activate any of these surfaces. The user or host administrator must add one.

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

## Citation lanes (CSL-JSON)

Modern government and scripture sources use CSL-JSON in `corpus/modern.jsonl` and `corpus/scripture.jsonl`. Each lane has its own SQLite/FTS5 database and a `source_class` label (`modern_government` or `scripture`). Neither lane is patristic evidence.

```sh
.venv/bin/python -m patristic_ethics.cli corpus validate-csl corpus/modern.jsonl --lane modern
.venv/bin/python -m patristic_ethics.cli corpus build-csl corpus/modern.jsonl --lane modern
.venv/bin/python -m patristic_ethics.cli corpus search-csl terrorism --db corpus/modern.db

.venv/bin/python -m patristic_ethics.cli corpus validate-csl corpus/scripture.jsonl --lane scripture
.venv/bin/python -m patristic_ethics.cli corpus build-csl corpus/scripture.jsonl --lane scripture
.venv/bin/python -m patristic_ethics.cli corpus search-csl peacemakers --db corpus/scripture.db
```

CiteIndex is an external ingestion tool (a local CiteIndex checkout, `$CITEINDEX`, v0.15.0). The runtime consumes CSL-JSON records; it does not import CiteIndex. PEA-specific fields live under `custom`: `citation_index`, `principle_ids`, `locus`, `text`, `text_sha256`, `rights_status`, `rights_evidence`, `review_status`, and `verification_method`. The nine current records are owner-reviewed; the three modern records remain `public-domain-unverified` for third-party material.

Linked provenance records live in `corpus/provenance.jsonl`. They use CSL-JSON and link catalogues, editions, and secondary literature to seed unit IDs:

```sh
.venv/bin/python -m patristic_ethics.cli corpus validate-provenance corpus/provenance.jsonl --seed corpus/seed.jsonl
.venv/bin/python -m patristic_ethics.cli corpus validate-primary-citations corpus/primary_citations.jsonl --seed corpus/seed.jsonl
.venv/bin/python -m patristic_ethics.cli corpus validate-secondary corpus/secondary.jsonl --seed corpus/seed.jsonl
```

`primary_citations.jsonl` keeps a CSL citation beside every reviewed primary unit and preserves the CTS URN in `custom.cts_urn`. `secondary.jsonl` is an author-level reference pilot: eight records link two sources to each reviewed unit. Passage-specific secondary interpretation and runtime rendering are out of scope.

Further reading is a bibliography only; it is never quoted in guidance. The canonical import path is `corpus/further_reading.jsonl`, delivered as JSONL with CSL fields and PEA fields under `custom`. The file now holds 145 records imported on 2026-10-23; 76 are reviewed and 69 remain draft-unreviewed; `corpus/further_reading.example.jsonl` remains the validator example.

Import quality at a glance: 75 records carry a DOI, 70 are URL-only, 28 are Google Scholar leads, none has an ISBN, and 58 have unknown rights status. Re-verification found 76 records with matching Crossref or URL metadata, 40 lead-only records, 16 blocked sources, 4 unchecked PDFs, and 9 remaining metadata issues. The two DOI errors were corrected with Crossref title evidence; the nine partial records keep local metadata with visible flags. The owner decided to keep all 145 records and show verification flags; no record was deleted. The 40 lead-only records are approved as a discovery list and remain flagged. The 76 verified records are owner-accepted without a spot check and marked `reviewed`; 69 records remain `draft-unreviewed`. Owner review is the next gate; see [the verification report](docs/research/2026-10-23-further-reading-verification.md).

```sh
.venv/bin/python -m patristic_ethics.cli corpus validate-further-reading corpus/further_reading.jsonl --seed corpus/seed.jsonl
.venv/bin/python -m patristic_ethics.cli further-reading --principle PEA-P01
.venv/bin/python -m patristic_ethics.cli further-reading --format markdown
```

See [the generated bibliography](docs/further-reading.md) and [the format guide](docs/further-reading-format.md).

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

## License and data

The software is licensed under the [Apache License 2.0](LICENSE). Third-party
corpus texts, translations and bibliographic records retain their recorded
rights; see [DATA_RIGHTS.md](DATA_RIGHTS.md). Downloaded source PDFs under
`source/` are not part of the public tree.

- Security reports: [SECURITY.md](SECURITY.md).
- Contributions: [CONTRIBUTING.md](CONTRIBUTING.md).
- Conduct: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
- Changelog: [CHANGELOG.md](CHANGELOG.md).

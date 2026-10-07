# PEA Native OpenCode Adapter (M4a)

This example wires the PEA native adapter plugin into an OpenCode profile.

## Install

Copy `opencode.json` into your project root (or merge the keys you need):

```sh
cp examples/opencode/opencode.json <target-dir>/opencode.json
# and copy the plugin itself (or point "plugin" at the repo path):
cp adapters/opencode/index.ts <target-dir>/.opencode/plugins/pea-ethics.ts
# then adjust "plugin" in opencode.json accordingly, e.g.:
#   "plugin": [".opencode/plugins/pea-ethics.ts"]
```

OpenCode loads plugins from `<project>/.opencode/plugins/*.ts` (Bun runtime)
automatically; the explicit `"plugin"` array entry is an alternative path form
that also works.

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `PEA_ENABLED` | `1` | `0` disables all hooks (config-only kill switch). |
| `PEA_CLI` | `uv run python -m patristic_ethics.cli` | CLI command prefix (split on whitespace). |
| `PEA_DB` | `corpus/units.db` | Corpus SQLite path (relative to `PEA_WORKDIR`). |
| `PEA_POLICY` | unset → CLI default (`policy/rules.json`) | Policy JSON path. |
| `PEA_BACKEND` | `fake` | Interpreter backend: `fake` (offline) or `ollama`. |
| `PEA_WORKDIR` | `process.cwd()` | Working directory for the PEA CLI subprocess. |
| `PEA_TIMEOUT_MS` | `20000` | CLI timeout (ms); kill + fail-open on expiry. |
| `PEA_LOG` | unset | Best-effort audit log path (JSON lines). |

## Behavior

- Every user prompt is assessed (`chat.message`); a refuse/guide/clarify/
  review action injects a `PEA: `-prefixed guidance TextPart into the
  user message (visible to the model, alongside the user text).
- Enabled tool calls are assessed pre-execution (`tool.execute.before`);
  refuse/clarify/review throws, which blocks the call (the model sees the
  tool error). `bash` is enabled here only so the pre-action gate is
  demonstrable.
- CLI failures and timeouts fail OPEN: nothing injected, nothing blocked,
  a `pea_cli_failure` diagnostic is logged.

## Native limits — read this

1. **No before-display guarantee.** `experimental.text.complete` fires
   AFTER text deltas are published, so native mode cannot withhold
   streamed host text. Guidance appears alongside it.
2. **Covered tools only.** The gate covers `tool.execute.before` for tools
   enabled in this profile. Uncovered paths (other tools, subagents,
   background jobs) run ungated. `{"*": false}` with no per-tool
   exceptions — the tools-disabled profile in
   `examples/opencode/controlled/opencode.json` — is the safest profile;
   this example enables `bash` only to exercise the pre-action gate.
3. **Fail-open.** If the PEA CLI cannot run (missing venv, timeout,
   malformed output), hooks degrade to no-op. Use the controlled client
   (M4b) when fail-open is unacceptable.
4. **Do not combine with the controlled client profile** (M4b). The plugin
   and the controlled client would assess the same prompt twice with no
   shared private call path. Keep them in separate directories/profiles.

## Live probe

`sh scripts/probe_pea_plugin.sh` runs the three scenarios (harmful →
injection; benign → no injection; tool call → gate). It writes evidence to
`/tmp/pea-plugin-probe/out/`. Scenario S1/S2 evidence lives in the plugin
audit log (`PEA_LOG=.../pea_audit.jsonl`) because injected user-message
parts are NOT echoed to `opencode run --format json` stdout (verified live
2026-10-07 — a deviation from the original expectation of seeing the part
in the run's JSON output).
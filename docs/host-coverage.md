# Host Coverage Record — PEA (Patristic Ethics Agent)

Date: 2026-10-07
PEA version: 0.0.1 (M0)
Scope: integration-boundary capability of candidate agent hosts, as probed or
as supported by pinned source. No capability is claimed beyond observed
evidence or pinned source; uncertain items are marked "unverified".

## Capability Matrix

| Capability | OpenCode 1.18.34 (live-probed) | Codex CLI 0.160.0 (synthetic CLI trace; no live host probe) | Claude Code 2.1.286/287 (synthetic CLI trace; no live host probe) |
|---|---|---|---|
| Context collection | Native `chat.message` hook + session message fetch (probe: hook fired; see evidence S1) | Current prompt/tool payload only; transcript path is documented unstable and is not parsed (`history.complete=false`) | Current hook payload only; transcript serialization is not specified by the hook contract and is not parsed (`history.complete=false`) |
| Pre-action control | `tool.execute.before` throw gates **covered tools only**; never-approval-prompt caveat (probe: blocked call skipped `tool.execute.after`; see evidence S2) | `PreToolUse` deny for supported events while the hook process responds; researched, not live-probed | `PreToolUse` deny for matched tools while the hook process responds; contract verified, not live-probed |
| Before-display guarantee | **Not achievable natively.** `experimental.text.complete` fires after text deltas are already published (source-confirmed) | **No** MessageDisplay event; no native withholding | **No.** MessageDisplay changes UI only, not transcript/model context |
| Controlled display path | PEA-owned client buffers `opencode run --format json` output and assesses before release; synthetic evidence is in `tests/test_controlled.py` and `tests/fixtures/opencode_probe/evidence/S5_controlled.txt`. Admin-managed config precedence still needs live verification. | unsupported: App Server schema exposes no all-tools disable field; runtime probe could not start in this managed sandbox. Do not claim controlled Codex support. | `pea-controlled-claude` buffers JSON output with built-in tools, MCP, non-managed hooks/plugins, and session persistence disabled; synthetic tests pass, managed policy and live host probe pending |
| Failure behavior | Hook failures on unverified paths fail-open (documented here; `chat.message` throw is undocumented) | Supported prompt/pre-tool events block on evaluator failure while the hook process responds; host process death and unsupported events remain outside the adapter | Supported prompt/pre-tool events deny on evaluator failure while the hook process responds; host timeout/termination remains outside the adapter |
| Unsupported/unverified paths | `experimental.text.complete` for withholding display; `chat.message` blocking via throw | Prior-turn transcript context; live hook behavior; App Server controlled mode | Native prior-turn transcript context; live native/controlled host behavior; controlled CLI requires API-key authentication in `--bare` mode |

## OpenCode 1.18.34 — probe details

Pinned sources:
- `packages/plugin/src/index.ts` (v1.18.34) — hook signatures: `chat.message`
  ({sessionID, model?, messageID?} → {message, parts}), `tool.execute.before`
  ({tool, sessionID, callID} → {args}), `tool.execute.after`, `event`,
  `experimental.text.complete`.
- `session/processor.ts` — text-delta ordering: deltas are published before
  `experimental.text.complete` fires, so the hook cannot withhold display.
- `session/tools.ts` — a throw in `tool.execute.before` skips the tool call
  and `tool.execute.after` is then not invoked.

Probe commands:

    sh scripts/probe_opencode.sh
    # gated pytest equivalent:
    PEA_LIVE_HOST_PROBE=1 uv run pytest tests/integration/test_host_contracts.py -q

Scenario results: see `tests/fixtures/opencode_probe/evidence/RESULT.md` —
corrected 2026-10-06; the bullets below are the original pre-probe draft and
are superseded by the "2026-10-06 correction" block at the end of this file.

- S1 baseline: plugin loaded, `chat.message` fired (evidence S1_plugin_load.txt).
- S2 tool block: `tool.execute.before` threw `PEA_PROBE_BLOCKED`; no
  `tool.execute.after` entry for the blocked call (evidence S2_tool_block.txt).
- S3 injection: `PEA-CANARY-1` part injected via `chat.message` mutation.
- S4 ordering: repeated baseline to compare text-delta vs
  `experimental.text.complete` timestamps (evidence S4_ordering.txt).

## 2026-10-06 correction

The original S1–S4 bullets above were written optimistically before a clean
probe run completed. First live attempts failed: the local model
`ollama/ornith-1.5:9b` cannot parse OpenCode's full tool-schema grammar
(HTTP 400 `Failed to initialize samplers: failed to parse grammar` from
`http://localhost:11434/v1/chat/completions`; direct curl with tools works,
so this is a small-local-model limitation), and the S3 part injection
crashed the host with `SchemaError: Missing key at ["id"], ["sessionID"],
["messageID"]` because a bare `{type,text}` object is not a valid TextPart.
After fixing the injection to a full TextPart and adding model fallback, the
full probe ran successfully on `ollama/deepseek-v4.1-flash:cloud`:

- Model used: `ollama/deepseek-v4.1-flash:cloud` (local ornith-1.5:9b
  rejected in S1 candidate check).
- S1 PASS: plugin loaded, `chat.message` fired, model call succeeded
  (S1_plugin_load.txt).
- S2 PASS: `tool.execute.before` fired, detected the sentinel, and blocked
  the bash call (`"blocked":true` entry; tool part state `status:"error"`,
  `error:"PEA_PROBE_BLOCKED"`). `tool.execute.after` was absent for the
  blocked call — confirmed live, matching the pinned source (S2_tool_block.txt).
- S3 PASS: canary part injected via `chat.message` with a full TextPart
  (id/sessionID/messageID); no SchemaError. In run mode `input.messageID` is
  absent and `output.message.id` is the fallback key. Model-echo of the
  canary is model-dependent (S3_injection.txt).
- S4 PASS: `experimental.text.complete` WAS observed (one entry per
  scenario session). It fired at 17:06:08.742Z while the final text part
  landed at 17:06:08.831Z — consistent with the pinned source: deltas are
  already published before the hook fires, so it cannot withhold display
  (S4_ordering.txt).
- The grammar limitation of small local models is a known constraint for
  controlled profiles: local-model profiles will need a tool-schema subset
  or a larger local model. Cloud-fallback models work today.

## 2026-10-07 Codex App Server check

Installed executable reports `codex-cli 0.160.0`; `codex app-server --help`
offers approval/sandbox configuration and `codex features list` exposes an
individual `shell_tool` feature toggle. These are not a documented global
tool-denial contract. The official App Server `ToolsV2` schema exposes only
`web_search`, and `TurnStartParams` has no per-turn tool allowlist. The direct
JSONL initialize probe exited before protocol startup because this managed
Linux sandbox cannot create the user namespaces required by Codex's sandbox;
the configured `~/.codex` state directory is also read-only. Therefore the
App Server's live events, runtime tool inventory, and end-to-end withholding
behavior remain unverified. Approval policy is not described as tool
disabling. Codex controlled mode stays unsupported pending a preventive
boundary and repeatable live probe.

Schema references checked 2026-10-07:
- [Codex App Server ConfigReadResponse schema](https://github.com/openai/codex/blob/main/codex-rs/app-server-protocol/schema/json/v2/ConfigReadResponse.json)
- [Codex App Server TurnStartParams schema](https://github.com/openai/codex/blob/main/codex-rs/app-server-protocol/schema/typescript/v2/TurnStartParams.ts)

## Legend

- **probed**: observed in a live run via this repo's probe assets.
- **source-confirmed**: behavior read from the pinned host source at the
  pinned version.
- **unverified**: no probe or source evidence yet; treat as absent until probed.

## Offline native-hook traces

`tests/integration/test_host_contracts.py::test_native_hook_stdio_synthetic_refusal_trace`
feeds the documented `UserPromptSubmit` JSON shape to each adapter's real
module entry point, runs the PEA CLI with the deterministic fake backend, and
checks one protocol JSON line with a blocking decision. Run with:

    .venv/bin/pytest -q tests/integration/test_host_contracts.py

This proves the adapter's stdin → context mapping → PEA decision → stdout
protocol path without paid inference. It does not invoke Codex or Claude Code,
so live event delivery, host enforcement, and process-failure behavior remain
unverified at those hosts. OpenCode's separate live probe evidence remains in
`tests/fixtures/opencode_probe/evidence/`.

## Shared native conformance — 2026-10-08

[The 23-case shared matrix](evaluation/host-conformance.md) now runs across Codex, Claude and OpenCode adapters with scripted results and session fixtures. Invalid/missing/unknown actions and failed/conflicting forward assessments block supported Python prompt/tool events and OpenCode covered tool events. All 69 host/scenario combinations pass, including zero OpenCode local mock effects on blocked pre-tool cases. This is synthetic adapter evidence; native advisory input, post-display limits and unsupported paths remain distinct from controlled support and live-host acceptance.

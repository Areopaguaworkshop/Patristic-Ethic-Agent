# Host Coverage Record — PEA (Patristic Ethics Agent)

Date: 2026-10-06
PEA version: 0.0.1 (M0)
Scope: integration-boundary capability of candidate agent hosts, as probed or
as supported by pinned source. No capability is claimed beyond observed
evidence or pinned source; uncertain items are marked "unverified".

## Capability Matrix

| Capability | OpenCode 1.18.34 (probed) | Codex CLI 0.160.0 (unverified — planned M5) | Claude Code 2.1.286 (unverified — planned M5) |
|---|---|---|---|
| Context collection | Native `chat.message` hook + session message fetch (probe: hook fired; see evidence S1) | unverified | unverified |
| Pre-action control | `tool.execute.before` throw gates **covered tools only**; never-approval-prompt caveat (probe: blocked call skipped `tool.execute.after`; see evidence S2) | unverified | unverified |
| Before-display guarantee | **Not achievable natively.** `experimental.text.complete` fires after text deltas are already published (source-confirmed) | unverified | unverified |
| Controlled display path | Requires a PEA-owned client consuming `opencode run --format json` (by design in M0; not yet probed end-to-end) | unverified | unverified |
| Failure behavior | Hook failures on unverified paths fail-open (documented here; `chat.message` throw is undocumented) | unverified | unverified |
| Unsupported/unverified paths | `experimental.text.complete` for withholding display; `chat.message` blocking via throw | unverified | unverified |

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

## Legend

- **probed**: observed in a live run via this repo's probe assets.
- **source-confirmed**: behavior read from the pinned host source at the
  pinned version.
- **unverified**: no probe or source evidence yet; treat as absent until probed.
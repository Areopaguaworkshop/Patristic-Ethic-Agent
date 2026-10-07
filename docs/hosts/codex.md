# Codex Host Record — PEA (Patristic Ethics Agent)

Date: 2026-10-07. PEA version 0.0.1. Host: Codex CLI 0.160.0 (hook facts
from fresh research 2026-10-07, not live-probed in this repo yet).
Adapter: `src/patristic_ethics/adapters/codex.py` + example wiring
`examples/codex/hooks.json`. Related records:
[OpenCode](opencode.md), [host-coverage.md](../host-coverage.md).

## Capability record

| Capability | Codex native hooks (this adapter) | Evidence basis |
|---|---|---|
| Prompt assessment + context injection | Yes — `UserPromptSubmit` `additionalContext`; guidance visible to the model alongside the prompt | researched, 0.160.0 |
| Prompt blocking | Yes — `UserPromptSubmit` `{"decision":"block","reason":...}` for refuse/clarify/review/withhold | researched |
| Pre-action tool gate | Yes — `PreToolUse` `permissionDecision: "deny"` blocks the call; `guide` allows with injected `additionalContext` (advisory) | researched |
| Post-hoc output warning | Partial — `PostToolUse`/`Stop` refuse emits `additionalContext` warning; content already produced; `Stop` can `{"decision":"block"}` but that cannot un-emit anything | researched |
| Before-display guarantee | **No.** Codex has NO MessageDisplay event; streamed host text cannot be withheld by a hook | researched |
| Context collection | **Degraded.** `transcript_path` is nullable and documented NOT stable — never parsed; `messages: []`, `history.complete=false` always | researched, deliberate |
| Failure behavior | **Fail-open.** Hook callback error/timeout/malformed output does not block the tool; default hook timeout 600 s (PEA caps its CLI subprocess at 15 s) | researched |
| Config activation | `[features] hooks = true` (config.toml) or inline `[hooks]`; hooks load from `<repo>/.codex/hooks.json` and `~/.codex/hooks.json` | researched |

## Event → AssessResult action → Codex protocol output

| Hook event | PEA action | Codex output |
|---|---|---|
| UserPromptSubmit | refuse/clarify/review/withhold | `{"decision":"block","reason": guidance}` |
| UserPromptSubmit | guide | `{"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext": guidance}}` |
| UserPromptSubmit | proceed | none (no interference) |
| PreToolUse | refuse/clarify/review/withhold | `permissionDecision:"deny"` + `permissionDecisionReason` (≤500 chars) + `additionalContext` |
| PreToolUse | guide | `permissionDecision:"allow"` + `additionalContext` (advisory, no denial) |
| PreToolUse | proceed | none |
| PostToolUse | refuse | `additionalContext` warning (post-hoc; no blocking semantics used) |
| PostToolUse | guide/clarify/review/withhold/proceed | none |
| Stop | refuse | `additionalContext` warning |
| Stop | anything else | none |
| SessionStart / PermissionRequest / unmapped | any | none (envelope build returns None → fail-open, no assessment) |

Envelope mapping: `UserPromptSubmit`→stage `input` (request from `prompt`,
fallback `user_prompt`); `PreToolUse`→`pre_action` (`request="Tool call: <tool>"`,
`proposed_action` from `tool_name`+`tool_input`/`arguments`/`input`);
`PostToolUse`/`Stop`→`output` (`candidate_response` from `tool_response`
stringified / `last_assistant_message`, else `""`). Host block:
`{name:"codex", version: payload version or "0.160.0", mode:"native"}`.
Policy/corpus version pins: `0.1.0-draft`/`0.1.0-draft`.

## What is NOT supported (native Codex + PEA v1)

- **Before-display**: no MessageDisplay event exists on Codex. Nothing can
  withhold streamed assistant text before display.
- **Transcript context**: the transcript format is unstable; PEA never
  parses `transcript_path`. Every assessment runs with empty `messages`
  and `history.complete=false` — the assessor never sees prior turns.
- **Strict enforcement**: hooks fail open on error/timeout (documented
  Codex behavior); a timed-out or crashed PEA CLI gate blocks nothing.
  Strict guarantees need controlled mode / an agent sandbox.
- **Async hooks**: `async:true` hooks cannot block — PEA hooks are sync.
- **Trust gate**: untrusted project hooks are **silently skipped**.

## Status vs OpenCode record

| Dimension | OpenCode 1.18.34 (probed) | Codex 0.160.0 (researched) |
|---|---|---|
| Prompt injection | Full TextPart injection via `chat.message` (probe S3 PASS) | `additionalContext` on UserPromptSubmit (researched) |
| Prompt block | `chat.message` throw is undocumented behavior | Documented `{"decision":"block","reason"}` |
| Tool gate | `tool.execute.before` throw (probe S2 PASS) | Documented `permissionDecision: "deny"` |
| Before-display | Not achievable (`experimental.text.complete` fires after deltas) | Not achievable (no MessageDisplay event at all) |
| Context collection | Session fetch via hook client (v1: fresh session only) | None — transcript unstable, never parsed |
| Failure mode | Fail-open (documented on unverified paths) | Fail-open (documented) |
| Live probe evidence | Yes (M4, 2026-10-06) | **No — facts researched 2026-10-07; no live probe yet** |

## Installing without touching global config

PEA's hooks live at `<repo>/.codex/hooks.json` (project layer) or
`~/.codex/hooks.json` (user layer). To test locally without touching
your global config, use a throwaway project:

```sh
mkdir -p /tmp/pea-codex-test/.codex
cp examples/codex/hooks.json /tmp/pea-codex-test/.codex/hooks.json
# adapt the "command" to point at this repo's CLI, e.g.:
#   "command": "uv run --project /home/ajiap/project/EthicAgent python -m patristic_ethics.adapters.codex"
# ensure hooks are enabled (config.toml):  [features] hooks = true
cd /tmp/pea-codex-test && codex
```

Project-layer hooks must be **trusted**: accept the `/hooks` trust
prompt (or review the file) when Codex loads it; an untrusted project
hooks file is silently skipped, leaving PEA inactive with no error.
`--dangerously-bypass-hook-trust` exists but should be used only with
hook files from fully vetted sources.

Environment passthrough: `PEA_BACKEND` (`fake`|`ollama`), `PEA_DB`,
`PEA_POLICY` are read by the adapter and forwarded to the PEA CLI as
flags; defaults otherwise (`corpus/units.db`, `policy/rules.json`,
backend fake — offline).

## Testing offline

```sh
uv run pytest -q tests/integration/test_codex_hooks.py   # offline, no codex process
```

The tests cover envelope building per event, the full decide mapping,
`main` fail-open paths with faked stdin/runner, protocol purity (stdout
carries at most one JSON line; diagnostics only on stderr), and the
example hooks.json. Live-probing the mapped facts above remains open
work for a follow-up (a temp project + trust flow, as above).
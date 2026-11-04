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
| Context collection | **Degraded.** `transcript_path` is nullable and documented NOT stable — never parsed; configured hook-observed prior turns; `history.complete=false` always | researched, deliberate |
| Failure behavior | **Fail-closed while the hook process responds.** Assessment errors, timeouts, and invalid results block UserPromptSubmit/PreToolUse; malformed input, unmapped events, or host-killed hook processes cannot be handled here | researched protocol + offline-tested |
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
  parses `transcript_path`. With `PEA_HISTORY_DB` configured, assessments receive observed prior turns;
  `history.complete=false` remains explicit. Without it, messages stay empty.
- **Strict enforcement**: PEA blocks supported prompt/tool events when its
  evaluator returns an error while the hook is running. A host-killed hook,
  malformed payload, or unsupported event remains outside this boundary.
  Before-display guarantees still require controlled mode / an agent sandbox.
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
| Failure mode | Fails closed for covered native tool calls; output remains advisory | Fails closed for supported input/pre-tool events; host termination remains unhandled |
| Live probe evidence | Yes (M4, 2026-10-06) | **No — facts researched 2026-10-07; no live probe yet** |

## Installing without touching global config

PEA's hooks live at `<repo>/.codex/hooks.json` (project layer) or
`~/.codex/hooks.json` (user layer). To test locally without touching
your global config, use a throwaway project:

```sh
mkdir -p /tmp/pea-codex-test/.codex
cp examples/codex/hooks.json /tmp/pea-codex-test/.codex/hooks.json
# adapt the "command" to point at this repo's CLI, e.g.:
#   "command": "uv run --project $PEA_REPO python -m patristic_ethics.adapters.codex"
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
`main` error-block paths with faked stdin/runner, protocol purity (stdout
carries at most one JSON line; diagnostics only on stderr), and the
example hooks.json. Live-probing the mapped facts above remains open
work for a follow-up (a temp project + trust flow, as above).

## Hook-observed dialogue history (engineering step 6)

Set `PEA_HISTORY_DB` to an absolute local SQLite path in the host process environment before starting the host. Its parent directory must exist; for example, create a private directory and use `/absolute/private/directory/pea-history.db`. Keep the same configured path across hook invocations. This enables automatic local collection from covered hooks; without it, native prior-turn collection remains disabled. No path from a hook payload is read.

The store records user prompts only after a `proceed` or `guide` assessment, and assistant text from assessed Stop events. Before later assessments, it loads prior records scoped to both host name and session ID. Tool outputs and blocked prompts are not added as dialogue. New sessions do not inherit another session's records; resuming the same session reloads observed history. Missing session identity prevents collection.

History is limited to the most recent 40 messages and 16,000 characters; overlong content and earlier records are explicitly marked omitted. Only 41 records per host/session are retained to detect omitted older history. Each message has an adapter-generated source ID and sequence. `history.complete` always remains false: earlier turns, bypassed hooks, intermediate assistant content, compaction events, and host-delivery failures can be missing. A hook allow result is not proof that the host accepted the prompt; later cancellation can also leave an observed record. This store is not an authoritative host transcript.

The SQLite file contains raw dialogue text. New files are created with mode 0600; existing file/directory permissions and the trusted operator configuration remain deployment responsibilities. Session separation is an application-level filter, not OS isolation against tools running as the same user. There is no cross-session profiling, no raw dialogue in audit logs, and no arbitrary transcript traversal. Remove the configured database to clear all observed history when the host is stopped; no automatic expiry across inactive sessions is claimed.

Tests exercise real adapter handling with injected assessment results: prior-turn delivery, host/session separation, resumption, bounded reads, blocked-input/tool-result exclusion, storage failure, and payload-path rejection. These are offline integration checks, not live host delivery or semantic-accuracy evidence. The native adapter still provides no before-display guarantee.

Source contracts checked on 2026-10-07: [Codex hooks](https://developers.openai.com/codex/hooks), [Claude Code hooks](https://code.claude.com/docs/en/hooks). This collector uses existing hook fields; it does not depend on transcript serialization.

### Process persistence and replay checks

Separate real hook subprocesses with the offline fake backend now verify that allowed prompts and assessed Stop outputs survive process restarts without extra stdout. For payloads carrying an explicit `turn_id` or `prompt_id`, identical role/text observations with the same ID are deduplicated by a host/session-scoped digest. Different explicit IDs preserve identical text as distinct turns. The adapter's generated fallback turn ID is never used for deduplication. Without an explicit ID, replay cannot be distinguished from a legitimate repetition. Deduplication covers retained observations only; it is not a durable action-dispatch ledger.

Existing history databases gain a nullable event-key column and a unique index without discarding stored dialogue. Malformed rows report incomplete collection rather than crashing the adapter. A failed evaluator blocks supported input events without adding the failed prompt. A symlink at the configured path is rejected on opening; this does not establish an OS boundary against a same-user attacker or a path-replacement race. These checks remain offline host-process evidence, not proof of live hook delivery.

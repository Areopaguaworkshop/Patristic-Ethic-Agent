# Claude Code Host Record — PEA (Patristic Ethics Agent)

Date: 2026-10-07. PEA version 0.0.1. Host: Claude Code 2.1.286/287
(hook facts verified against the documented hook contract on
2026-10-07; no live probe has been run yet — this adapter is implemented
from the verified contract, and live evidence rows are marked below).
Related records: [host-coverage.md](../host-coverage.md),
[opencode.md](opencode.md) (the probed M4 reference).

This is the M5 native adapter record: the adapter maps Claude Code
command-hook payloads to the PEA ContextEnvelope, assesses them through
the frozen local CLI (`python -m patristic_ethics.cli assess --stdin`),
and speaks the Claude Code hook-protocol JSON on stdout.

## Capability table — what the native hooks support

| Capability | Supported? | Mechanism and evidence |
|---|---|---|
| UserPromptSubmit block | **Yes** | `{"decision":"block","reason":...}` stops the prompt from reaching the model (contract §output protocol) |
| UserPromptSubmit inject | **Yes** | `hookSpecificOutput.additionalContext` adds context for the model to consider |
| PreToolUse deny | **Yes** | `permissionDecision:"deny"` + `permissionDecisionReason` (truncated to 500 chars in the adapter) |
| PreToolUse allow/modify | **Yes** | `permissionDecision:"allow"`; `updatedInput` exists in the contract but the adapter does not use it (v1: no argument rewriting) |
| PostToolUse block-replace | **Yes (with loss)** | `{"decision":"block","reason":...}` replaces the tool result shown to the model; the already-executed effect is NOT undone |
| Stop block/continue | **Yes (advisory)** | `{"decision":"block","reason":...}` makes the model continue (subject to the documented 8-block cap); useful for a refuse follow-up, not a hard guarantee |
| MessageDisplay display-replace | **Yes — display-only, advisory** | `hookSpecificOutput.displayContent` replaces what the user SEES; the transcript and model context keep the original |
| Withhold before display | **No** | MessageDisplay cannot redact what the model sees or what persists in the transcript |
| Timeout enforcement | **No (fail-open)** | A command-hook `timeout` (or crash, or malformed output) lets the prompt/tool PROCEED. Exit code 2 is an alternative block channel, but it is equally dead after a timeout, so the adapter never relies on it |
| Transcript context | **No** | `transcript_path` is written asynchronously and may lag; the adapter never parses it: `messages: []`, `history.complete: false` |

## What is NOT supported (hard limits)

1. **Withholding model output before display is impossible via hooks.**
   `MessageDisplay.displayContent` is display-only: the transcript and
   the model's context retain the original text. It cannot be relied on
   to withhold content the model already emitted. The adapter treats it
   as advisory display (prefixes `PEA: `) only.
2. **Timeouts fail open.** The settings `timeout` field (30 s in the
   example) kills the hook on expiry and the tool/prompt proceeds. A
   non-zero exit, crash, or malformed stdout has the same result. If
   fail-open is unacceptable, do not rely on this adapter alone.
3. **The transcript is not parsed.** Each assessment is single-shot:
   `messages` is always empty and `history.complete` is always false
   (the same honest-context v1 choice as the OpenCode adapter).
   Multi-turn collection is later work.
4. **PostToolUse cannot undo effects.** Blocking replaces the result
   the model sees; side effects of the executed tool remain.
5. **Strict guarantees require controlled mode.** For a
   before-display guarantee use a PEA-owned controlled client on the
   Claude Agent SDK (M5 item 3, not built yet); the native hooks alone
   do not satisfy the zero-premature-display acceptance.

## Isolation testing (`--settings`)

Claude Code accepts a `--settings <path>` flag that layers settings
inline, so the example wiring can be exercised without touching the
user's `~/.claude/settings.json`:

```sh
claude --settings "$(pwd)/examples/claude-code/settings.json" \
  --print "How do I write a regex?"
```

Or copy the file to a scratch project as `.claude/settings.json`:

```sh
mkdir /tmp/pea-claude-test && cd /tmp/pea-claude-test
cp /home/ajiap/project/EthicAgent/examples/claude-code/settings.json \
   .claude/settings.json   # (mkdir -p .claude first)
```

Project-scope note: `.claude/settings.json` applies to that project
directory; `.claude/settings.local.json` is the gitignored variant; hooks
merge across user/project/local levels, so removing the example means
removing its entries from the level where it was installed.

## Scope of the example wiring

`examples/claude-code/settings.json` wires two events:

- **UserPromptSubmit** (timeout 30) — every prompt is assessed; a
  refuse/clarify/review/withhold blocks the prompt, guide injects
  context.
- **PreToolUse** matcher `Bash` (timeout 30) — Bash calls are gated:
  refuse-family actions deny the call with the PEA reason; guide allows
  with additional context. Only matched tools are covered — other
  tools, subagents, and background paths run ungated (same
  covered-tools-only caveat as OpenCode).

PostToolUse, Stop, and MessageDisplay are implemented in the adapter
(`build_envelope`/`decide` accept them) but are NOT wired in the example
settings: PostToolUse's block-replace cannot undo effects, Stop's block
only nudges continuation, and MessageDisplay is display-only. Wiring them
is a documented choice, not a guarantee.

The hook command runs `uv run python -m
patristic_ethics.adapters.claude_code` from the project directory; the
runner (15 s timeout, under the 30 s hook timeout) spawns
`sys.executable -m patristic_ethics.cli assess --stdin` with
`PEA_BACKEND`/`PEA_DB`/`PEA_POLICY` passthrough.

## Status table vs other hosts

| Capability | OpenCode 1.18.34 (probed, M4) | Claude Code 2.1.286 (native hooks) | Codex CLI 0.160.0 (M5, separate lane) |
|---|---|---|---|
| Automatic prompt assessment | Yes — `chat.message` | Yes — UserPromptSubmit | unverified (separate adapter record) |
| Guidance injection | Yes — TextPart injection | Yes — `additionalContext` | unverified |
| Pre-action tool gate | Yes — `tool.execute.before` throw (covered tools only) | Yes — `permissionDecision:"deny"` (matched tools only) | unverified |
| Before-display guarantee | **No** (native) / **Yes** (controlled client M4b) | **No** — MessageDisplay is display-only; no controlled path yet | unverified |
| Failure behavior | fail-open on unverified paths | **fail-open** (timeout/crash/malformed → prompt/tool proceeds) | unverified |
| Context collection depth | Fresh session, `history.complete=False` (v1) | Single payload, `messages=[]`, `history.complete=False` (v1) | unverified |

## Test evidence

- Offline (no Claude Code binary, no network):
  `uv run pytest -q tests/integration/test_claude_hooks.py` — envelope
  validity and stage mapping per event, the event × action decide
  table, single-line stdout protocol, fail-open on malformed
  stdin/runner crash/runner timeout-class failures, stderr-only
  diagnostics, and example-settings structure (parses, both hook
  keys, timeouts present, comment-free JSON).
- Live probing of this adapter against Claude Code 2.1.286/287 has not
  been run; capability claims above rest on the verified hook contract
  and the adapter's offline conformance to it. A live `--settings`
  probe run belongs in this record when performed.
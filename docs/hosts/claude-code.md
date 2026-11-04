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
| Timeout enforcement | **Partial** | PEA returns block/deny on evaluator timeout or invalid output for UserPromptSubmit/PreToolUse while the process remains alive. A host-enforced kill, crash before parsing, or malformed hook payload cannot be intercepted |
| Transcript context | **No** | The hook includes `transcript_path`, but the serialized transcript format is not specified in the hook contract; the adapter does not parse it (configured hook-observed messages; `history.complete: false`) |

## Controlled client (M5 implementation slice)

`pea-controlled-claude` launches Claude Code print mode and buffers its
complete JSON result before PEA assesses it. It passes `--safe-mode`,
`--tools ""`, `--strict-mcp-config --mcp-config "{}"`, and
`--no-session-persistence`: built-in tools, MCP servers, non-managed hooks/plugins and
on-disk candidate sessions are disabled for this path (managed policy
settings may still apply). A failed process,
timeout, or malformed result is withheld. Each turn uses a fresh Claude
process; only user turns and assistant text already released by PEA are
included in the next input and assessment context. This history is a
JSON-escaped data record with role labels, paired with a system instruction
that keeps those message values below system/developer rules.

```sh
pea-controlled-claude --interactive --dir . --backend ollama
```

From a source checkout, run
`PYTHONPATH=src python -m patristic_ethics.claude_controlled --interactive
--dir . --backend ollama` if the entry point has not been installed.

The PEA backend must be explicitly selected. Claude Code's `--safe-mode`
keeps the configured authentication method while ignoring user/project
customizations; managed policy settings still apply. Offline tests prove
the runner contract and release gate, but no live inference or host display
probe has been run. Only model response text captured on stdout is gated;
external terminal notices are outside that boundary.

The installed Claude Code 2.1.287 accepted the controlled flags combined
with `--print --version` and returned without invoking a model. This checks
argument compatibility only; runtime tool isolation and output withholding
remain unproven until a live host run.

## What native hooks do NOT support (hard limits)

1. **Withholding model output before display is impossible via hooks.**
   `MessageDisplay.displayContent` is display-only: the transcript and
   the model's context retain the original text. It cannot be relied on
   to withhold content the model already emitted. The adapter treats it
   as advisory display (prefixes `PEA: `) only.
2. **Host-enforced termination remains outside the gate.** The settings
   `timeout` field (30 s in the example) kills the hook on expiry. PEA
   blocks evaluator errors while the process is alive, but cannot respond
   after the host kills it. Keep this hook timeout above the CLI cap.
3. **The native transcript is not parsed.** Each assessment uses one hook payload plus configured prior observations:
   `messages` contains configured hook-observed turns; `history.complete` is always false
   (hook observations cannot establish complete host transcript coverage).
   Live multi-turn collection remains unverified.
4. **PostToolUse cannot undo effects.** Blocking replaces the result
   the model sees; side effects of the executed tool remain.
5. **Strict guarantees require the controlled client.** Native hooks alone
   do not satisfy zero-premature-display acceptance.

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
cp "$PEA_REPO/examples/claude-code/settings.json" \
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
| Before-display guarantee | **No** (native) / **Yes** (controlled client; synthetic tests) | **No** (native) / **Yes** (controlled client; synthetic tests) | unverified |
| Failure behavior | fail-open on unverified paths | **blocks evaluator failures** on supported input/pre-tool events; host termination is unhandled | unverified |
| Context collection depth | Native `history.complete=False`; controlled client carries the complete PEA-visible dialogue | Native configured hook-observed prior turns, `history.complete=False`; controlled client carries the complete PEA-visible dialogue | unverified |

## Test evidence

- Offline (no Claude Code binary, no network):
  `uv run pytest -q tests/integration/test_claude_hooks.py` — envelope
  validity and stage mapping per event, the event × action decide
  table, single-line stdout protocol, evaluator-error blocks for supported
  events, malformed-input handling, stderr-only
  diagnostics, and example-settings structure (parses, both hook
  keys, timeouts present, comment-free JSON).
- Live probing of this adapter against Claude Code 2.1.286/287 has not
  been run; capability claims above rest on the verified hook contract
  and the adapter's offline conformance to it. A live `--settings`
  probe run belongs in this record when performed.

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

## Process-backed controlled display checks — 2026-10-08

`tests/integration/test_controlled_process.py` runs the actual controlled CLI and runner against synthetic executable host processes with a deterministic assessor. The host flushes candidate text and waits on a handshake; neither client stdout nor stderr becomes readable before the host is released. A refused candidate is replaced with PEA guidance. Malformed output and nonzero child exits produce a static withheld response without exposing raw stdout/stderr. OpenCode also rejects an unsafe resolved permission profile before launching the generation process. OpenCode diagnostics now omit malformed output, child stderr and runner exception messages.

These checks prove subprocess buffering and the controlled display boundary under the test contract. They do not prove installed-host hook delivery, actual managed-config precedence, semantic assessment quality, compaction, or live model output withholding. Those acceptance requirements remain open.

### Unexpected evaluator failures — 2026-10-08

The shared controlled client catches unexpected assessor exceptions and rejects missing results, unknown actions and failure-bearing forward results. Input failures do not invoke the host; output failures quarantine the candidate and release only the static service message. Diagnostics expose the failure category, not exception text. Failed candidates are excluded from future visible history, host session reuse is cleared, and a later successful assessment can recover. Offline regression checks cover both phases; this does not establish live-host/model availability.

### History limits and loss notices — 2026-10-08

The shared controlled client retains a contiguous suffix of at most 40 released messages and 16000 text characters, without slicing individual messages into false verbatim excerpts. It preserves monotonic source IDs/sequences and records omitted sequence ranges. Once content is omitted, PEA receives `history.complete=false`; the host receives the same bounded visible transcript and loss notice in a fresh process/session rather than resuming a richer hidden transcript. A new explicitly selected controlled session resets both dialogue and omission metadata. The current request and candidate are assessed in full; these history limits do not silently truncate them.

The interpreter prompt includes adapter history completeness, omissions, collection errors, summary source ID and summary reference IDs. It is instructed to identify material missing antecedents instead of inventing them. A scripted missing-antecedent regression proves that a returned uncertainty assessment causes clarification without host invocation; semantic recognition by a live model remains to be evaluated.

### Optional bounded revision — 2026-10-08

Add `--revise-once` to the controlled CLI to permit one correction attempt after an output refusal/guidance replacement or failed structural check. The default remains immediate PEA guidance/static withholding, with no extra host call. Input refusals, ambiguity/review gates and evaluator failures do not trigger revision. The revision uses the same tools-disabled runner in a fresh session/process, receives bounded released context and explicitly untrusted candidate data, and is assessed again semantically and structurally before release. A failed revision produces PEA guidance or the static withheld message; it never retries again. A conflicting `proceed`/non-allow disposition fails closed.

Programmatic users can set `allow_revision=True` and optionally supply `revise_fn(candidate, problems) -> str | None`; the same rechecking applies. Invalid/empty returns and callback exceptions fall back without exposing exception text. Every revision attempt clears host-session reuse, even if its corrected output passes; later host context contains only user-visible content. Audit metadata records whether revision was attempted and whether a returned candidate was rechecked. The original candidate remains available only in the in-memory `ControlledResult.buffered` field. Opting in can add one generation timeout and one assessment; no latency improvement or live revision success is claimed. The native adapters do not acquire a before-display boundary through this feature.

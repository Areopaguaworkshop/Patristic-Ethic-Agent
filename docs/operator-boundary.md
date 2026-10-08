# Operator Boundary — Evidence Record (M3 item 5)

Date: 2026-10-06 · Scope: plan §5.5 / M3 item 5. Host: single-user Linux dev box.
Proof: `uv run pytest -q tests/test_operator_boundary.py` (11 tests, offline).

Goal: attempt **every agent-visible path** to (a) read approval credentials,
(b) modify review state, (c) invoke the resolver, (d) impersonate the operator —
then record honestly what code denies and what needs an OS/sandbox boundary.

## Enforced by code (test-proven)

| Property | Where | Proof (test) |
|---|---|---|
| No agent-facing approve/deny surface | `runtime_store.py` | `test_agent_surface…` (test_review.py), `test_check_action_returns_no_resolution_mechanism` |
| `resolve_review` requires env token; missing/empty → `OperatorBoundaryError` | §resolver | `test_resolve_without_token_denied_by_code`, `test_resolve_with_empty_token_denied_by_code`, subprocess exit 3 |
| Wrong token → `OperatorBoundaryError`, state untouched | constant-time compare (`hmac.compare_digest`) | `test_resolve_with_wrong_token_denied_by_code`, `test_subprocess_wrong_token_also_denied` |
| MCP tools expose no approve/resolve/override/release/state parameter (recursive input-schema key walk) | `mcp_server.py` | `test_mcp_tools_expose_no_state_parameter` |
| `check_action` never returns a resolution mechanism (no token, no resolved_by/note; `review_id` may be exposed) | `mcp_server.py` | `test_check_action_returns_no_resolution_mechanism` |
| Refuse/non-overridable decisions never open reviews (`ReviewNotAllowed`) | `open_review` | test_review.py |
| Approved→denied/duplicate/denied-approval transitions blocked; expired→denied requires a note | resolver | test_review.py |
| Reviews bound to session + action/context digests + policy version + expiry; drift → `reassess_required`; dispatch claim checks the same reviewed values | store | `test_dispatch_requires_original_action_context_and_policy`, test_review.py |
| At-most-once dispatch: one-shot `claim_dispatch` for matching approved values, no auto-retry, `stuck_attempts` is view-only | store | `test_stuck_attempt_never_auto_dispatches` |
| Event audit idempotent on hook retries (PK event_id, INSERT OR IGNORE) | store | test_review.py |
| Review records retain exact action/context JSON and PEA reason for human inspection; repeated identical pending reviews reuse the same record | `runtime_store.py` | `test_open_and_get_review_roundtrip`, `test_matching_pending_review_is_reused` |
| `pea-operator list/show/resolve` provides a local review workflow; resolution still requires the configured token and a note | `operator.py` | `tests/test_operator_cli.py` |
| Proxy retries are reassessed, then may claim only an approved unexpired review matching the proxy process, tool, arguments, and policy; the downstream result marks it dispatched | `proxy.py`, `runtime_store.py` | `test_approved_reviewed_retry_forwards_once_and_marks_dispatch` |

## NOT enforced by code on this box (honest gaps)

These attempts **succeeded** during the proof and must not be re-labeled as
denials. They are OS-boundary concerns:

1. **Direct sqlite write** (`test_direct_db_write_is_not_prevented_same_user`):
   a same-user process can open `runtime.db` and execute
   `UPDATE reviews SET status='approved'`. Code-level mitigations survive
   (dispatch stays one-shot; reassessment still flags drift), but the write
   itself is permitted by the same-user file. Fix: ownership, not code.
2. **Env readability**: `PEA_OPERATOR_TOKEN` is just an env var; any same-user
   process the operator exports it to — or that can read the operator
   process's `/proc/<pid>/environ` — can read it. No Python library denies this.
3. **Process inspection**: same-user `ptrace`/coredumps can read the token or
   the db out of a live process. Not testable meaningfully here.

## Required deployment boundary (not yet demonstrated)

Per plan §5.5: "a shell-capable agent must not be able to approve itself";
another filename, a CLI switch, or a secret readable by the agent is
insufficient. Deployment must provide:

- A separate OS identity (or equivalent sandbox) for the operator.
- `runtime.db` owned by that identity, mode `0600` (agent cannot read/write).
- `PEA_OPERATOR_TOKEN` exported only into the operator's process
  (not the agent's, not a shared env file).
- Controlled profile keeps approval-altering paths (shell, file writes) disabled
  until this separation is demonstrated on the target host.

Until then, the env-token check is a **placeholder** recorded as such in
`runtime_store.py`'s docstring; the real M3 acceptance evidence is the
OS/sandbox denial results below.

The operator console is a workflow surface, not an authorization boundary.
It reads stored action/context data so the reviewer can inspect the case;
the runtime database can therefore contain sensitive request and tool
arguments and must be protected by the deployment identity. The stdio proxy
uses a random process-scoped session, so a different proxy process cannot
consume an approval; restarting the proxy intentionally makes that approval
unusable. A downstream call that raises after the one-shot claim stays
`attempted` and is never retried automatically.

The dispatch claim also checks that the action, context and policy version
still match the values reviewed. The workflow now renders the pending case,
reassesses on a user-initiated proxy retry, and dispatches only after an exact
one-shot claim. OS-level isolation remains unproven and is still required
before this operator path can be enabled in a shell-capable agent profile.

## Residual risk + what to re-test on a real deployment

Residual (post-boundary) risks: token exfiltration via operator compromise;
db-file backup/temp copies with loose permissions; a host hook failing open
outside PEA (plan risk table). Record denial results as evidence:

- As the agent identity: `cat runtime.db` → Permission denied (record output).
- As the agent identity: open sqlite → `unable to open database file`.
- As the agent identity: `printenv PEA_OPERATOR_TOKEN` → empty.
- As the agent identity: `sqlite3 runtime.db "UPDATE reviews SET status='approved' …"` → Permission denied.
- Attempt resolver invocation via every enabled host tool: expect OS/sandbox
  denial per plan §M3 acceptance — "require OS/sandbox denial, not just an
  instruction telling the agent not to try."

## Commands

```
uv run pytest -q tests/test_operator_boundary.py   # boundary proof (offline)
uv run pytest -q                                    # full suite
```

## Dispatch crash/replay checks — 2026-10-08

`tests/integration/test_dispatch_recovery.py` abruptly terminates worker processes with `os._exit` after claiming approval, after a durable local test effect, and after recording completion. Each fresh worker reopens the same SQLite database and cannot reclaim the original approval. Four competing processes produce exactly one claim/effect. Official MCP client round trips also cover a downstream exception after an effect and a completion-record exception: both surface protocol errors, leave the original review `attempted`, and prevent a repeated call from forwarding under that approval. These tests use local test effects; they do not establish exactly-once behavior for arbitrary downstream services.

Inspect unresolved attempts without retrying them:

```sh
.venv/bin/python -m patristic_ethics.operator --db corpus/runtime.db attempts
.venv/bin/python -m patristic_ethics.operator --db corpus/runtime.db show REVIEW_ID
```

`attempts` includes every unresolved attempt immediately, with its review/session ID and claim time. It does not reset state or dispatch. An `attempted` record can mean no effect, a completed effect with a lost reply, or a failed completion record. Establish the external outcome before deciding whether a new reviewed action is safe. A repeated proxy call may open a new pending review; it never automatically approves it or reuses the consumed approval. New proxy processes have new session IDs and cannot reuse old session approvals. Separate OS identity and credential/database isolation remain deployment requirements and are still unproven.

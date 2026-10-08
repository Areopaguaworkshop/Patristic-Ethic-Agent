# PEA code review and implementation status

Date: 2026-10-07. Reviewed branch `2026-10-07-0.1v`, commit `9cfa16b`.
Scope: project implementation, host adapters, tests, evaluation assets, and acceptance against the [canonical implementation plan](../plans/2026-10-06-pea-implementation-plan.md) and [core brief](../instruction.md).

**Verdict: REQUEST CHANGES. Architectural status: BLOCK** for claiming the planned enforced runtime complete. The project has substantial prototype code; the progress log's completion labels are not supported by the original acceptance criteria.

## Completion count

Counting the plan's seven milestones M0–M6, not files or test counts:

- **7 of 7 started and partially implemented.**
- **0 of 7 fully acceptance-complete.**
- **7 of 7 still require work.**
- **0 of 7 entirely unstarted.**

This does not mean no work has been completed. Package setup, corpus import, assessment plumbing, MCP tools, review-state helpers, host payload adapters, OpenCode probes, and a development evaluation harness exist. It means each milestone still has at least one unmet required acceptance condition. No defensible percentage of total engineering effort can be inferred from these counts.

| Milestone | Implemented evidence | Remaining work before acceptance |
|---|---|---|
| M0 — Integration boundaries | Python package; OpenCode prompt, injection, and tool-block probes | Live Codex/Claude host-boundary evidence; planned controlled Codex App Server probe; failure and resume/compaction coverage. The plan also retains stale Codex-first language despite D7's OpenCode-first change. |
| M1 — Policy and corpus | Constitution/rules, FTS5 importer, 19 units across English/Greek/Latin/Syriac, 32 development scenarios | All 19 seed units are `draft-unreviewed`; owner review and planned 40–60 verified units remain. Close or explicitly preserve evidence gaps and verify editorial eligibility of runtime quotations. |
| M2 — Contextual assessment and guidance | Envelope, fake/Ollama interpreter, deterministic policy, guidance and CLI | Replace lexical dependence in semantic disposition, validate evidence against messages, check citations on releasable outputs, and demonstrate required contrasting conversations with the real backend. See findings R2, R3, R9. |
| M3 — MCP, proxy and reviews | Four tools, forwarding gate, SQLite review/audit helpers | Fix expiry and thread ownership; integrate reassessment and authorized release; prove operator OS/sandbox isolation. The boundary record explicitly reports successful same-user approval-store writes. |
| M4 — OpenCode vertical slice | Native plugin, controlled output buffer, live prompt/tool evidence | Remove argument bypass, carry history into action assessment, enforce tools-disabled controlled profile, and prove history-dependent judgment/resume/compaction. |
| M5 — Codex and Claude | Native payload/protocol adapters and offline tests | Actual conversation collection, live host integration probes, viable evaluator deadlines, and controlled clients or explicit unsupported controlled profiles. Native-only adapters do not prove controlled support. |
| M6 — Evaluation and bounded release | Harness, rubric, fake-backend development results | At least 120 human-reviewed held-out scenarios (at least 30 multi-turn), real backend evaluation, comparison conditions, human grounding/care grading, release gates, and release documentation. |

## Review findings

Seven HIGH and two MEDIUM findings. Findings distinguish reproducible code behavior from missing acceptance evidence. No runtime fixes were made during this review.

### R1 — HIGH: Agent-controlled arguments bypass the OpenCode gate

Location: [adapters/opencode/index.ts:355](../../adapters/opencode/index.ts#L355).

The hook skips assessment if serialized tool arguments contain `pea assess` or `patristic_ethics.cli`. A comment in a command can therefore disable the gate. The actual plugin was exercised in Bun with an in-memory evaluator stub always returning refusal:

```text
echo marker                  -> blocked:true,  assessorCalls:1
echo marker # pea assess     -> blocked:false, assessorCalls:0
```

No actual external command effect was needed. The existing adapter test checks for the bypass strings rather than proving the boundary. Remove this argument-based exception; internal evaluator invocation already happens outside the host's tool hook. Add an actual hook regression asserting both payloads are assessed.

### R2 — HIGH: Correct semantic interpretation can still become permitted guidance

Location: [policy.py:205](../../src/patristic_ethics/policy.py#L205), refusal condition at line 286.

`derive_signals()` determines facilitation through fixed substring markers for every observation, including real model observations. An observation with requested assistance `Provide detailed instructions for murder`, expressed intent `Intends to murder another person`, topic `murder`, and confidence 0.99 produces `guide`; `assess_tool_call()` permits forwarding. The interpreter correctly identifies harmful intent, but neither sentence contains an accepted facilitation marker.

Add validated structured assistance classifications to the interpreter contract and use them directly in deterministic disposition selection. Lexical hints must not replace that classification. Add paraphrase tests covering both refusal and zero downstream forwarding.

### R3 — HIGH: Citation checking skips outputs that are released

Location: [assess.py:195](../../src/patristic_ethics/assess.py#L195).

Candidate citation checking runs only when the disposition is `refuse`. Controlled mode releases `proceed` candidates unchanged, so fabricated source claims in those candidates are never verified. Reproduced offline:

```python
c = ControlledClient(
    runner=lambda prompt: HostOutput(
        text='Augustine said "The moon is made of cheese."'
    ),
    db_path=None,
)
r = c.run("What did Augustine teach?")
# action == "proceed"; fabricated quotation appears in released_text
```

The structural gap also exists with a supplied valid benign observation, independently of fake-backend behavior. Validate applicable source claims before every candidate release, separately from the harm disposition. Unsupported claims require bounded correction or withholding; ordinary quoted programming strings should not be treated as patristic claims.

### R4 — HIGH: Expired reviews can authorize dispatch

Locations: [runtime_store.py:299](../../src/patristic_ethics/runtime_store.py#L299) and line 337.

Approval and dispatch check stored status without checking the expiration timestamp. The separate `expire_stale()` operation only changes pending rows and is not a reliable authorization boundary. An offline reproduction created a review with `ttl_s=-1`, approved it with a valid operator token, and obtained `True` from `claim_dispatch()`. Approval that expires before dispatch is also not rejected there.

Check expiry atomically in both approval and dispatch SQL using trusted current time. Test expiry before approval and between approval and dispatch. This fix is separate from the still-unproven OS boundary protecting the store.

### R5 — HIGH: Controlled mode does not establish a tools-disabled host

Location: [controlled.py:126](../../src/patristic_ethics/controlled.py#L126), default working directory at line 184.

The client starts OpenCode in a supplied directory, defaulting to the current directory, without supplying or validating the tools-disabled profile. Copying the example profile is a manual prerequisite. A passing input can therefore reach a host with tools enabled; buffering output cannot undo their effects. The host documentation acknowledges this limitation, but M4's completion claim does not.

Establish a trusted tools-disabled configuration before launching the host. Detecting tool events after execution is not a preventive gate. Keep any enabled tool paths behind verified pre-action control.

### R6 — HIGH: Native action assessments lose the conversation objective

Locations: [OpenCode index.ts:283](../../adapters/opencode/index.ts#L283), [codex.py:92](../../src/patristic_ethics/adapters/codex.py#L92), [claude_code.py:80](../../src/patristic_ethics/adapters/claude_code.py#L80).

OpenCode pre-action envelopes explicitly contain empty messages despite fetching history for input assessment. Codex and Claude envelopes always contain empty messages. Apparently innocuous actions can thus be assessed without the earlier objective that determines whether they facilitate harm. Marking history incomplete is honest but does not meet the core contextual-judgment requirement.

Supply relevant current-session history and the original objective for each proposed action, preserve source identifiers, and test paired identical actions under benign and harmful preceding objectives.

### R7 — HIGH: Measured local-model latency causes native evaluation to fail open

Locations: [codex.py:36](../../src/patristic_ethics/adapters/codex.py#L36), [claude_code.py:42](../../src/patristic_ethics/adapters/claude_code.py#L42), [OpenCode index.ts:68](../../adapters/opencode/index.ts#L68).

Python adapters impose a 15-second evaluator timeout; OpenCode defaults to 20 seconds. The configured local model is documented taking approximately 170–195 seconds per interpretation in [the host record](../hosts/opencode.md). Adapter error paths then permit execution. Under the measured configuration, switching from the fake backend to the intended real semantic backend defeats the gate.

Use a backend that fits a declared deadline and convert internal evaluator failures into explicit clarification/withholding before the host hook deadline. Distinguish that controllable failure from host-level hook failures that native adapters cannot prevent.

### R8 — MEDIUM: Proxy persistence crosses SQLite's thread boundary

Locations: [proxy.py:265](../../src/patristic_ethics/proxy.py#L265), store construction at line 355, [runtime_store.py:119](../../src/patristic_ethics/runtime_store.py#L119).

The proxy creates its runtime connection on the main thread, then invokes the captured gate in an AnyIO worker. Default SQLite connections are thread-bound. An offline worker-thread call reproduced `sqlite3.ProgrammingError`; audit insertion and review creation therefore fail in the real server execution path. Caught exceptions conceal missing persistence beneath returned decisions.

Own connections in their execution thread, for example with a connection per gate invocation. Exercise actual server dispatch with a runtime database and assert audit records and review identifiers, not only the disposition.

### R9 — MEDIUM: Interpreter evidence is shape-checked but not source-checked

Locations: [interpreter.py:195](../../src/patristic_ethics/interpreter.py#L195), [assess.py:154](../../src/patristic_ethics/assess.py#L154).

An observation containing `Evidence(source_id="nonexistent", quote="invented")` passes assessment and places that identifier in `decision.message_evidence`. No validation requires the identifier to exist or the quoted text to match its message. Missing evidence can also accompany definitive judgments.

Validate evidence against the envelope before policy evaluation, including source membership and matching quote/span. Define evidence requirements and treat invalid evidence as uncertainty instead of presenting it as grounded judgment.

## Verification and limitations

- The review began from a clean working tree at `9cfa16b`; source and tests were not modified.
- Seed validation passed: 19 structurally valid units. All 19 are draft-unreviewed; structural validation is not editorial approval.
- Re-ran the development evaluation with the fake backend: **18/32** dispositions match; refusal recall **5/9 (55.6%)**; false interventions **3/8 (37.5%)**; multi-turn matches **2/4**. Results written outside the project to `/tmp/pea-review-eval-2026-10-07.json`.
- Those results are fallback-path development evidence, not real-model or held-out evidence. The plan's refusal/false-intervention gates are at least 95% and at most 5%, respectively.
- A bounded integration subset excluding `test_mcp.py` returned **115 passed, 3 skipped, 1 failed** in 30.89 seconds. `test_proxy.py::test_live_round_trip_passthrough_and_block` timed out waiting 30 seconds for `tools/call`. This timeout is reported as an observed test failure; its cause was not established and is not assumed to be R8.
- The initial full-suite attempt stopped making progress around the MCP tests and was interrupted. A unit subset also stalled around operator-boundary tests and was interrupted. The previous 300-pass claim was not reproduced by those attempts.
- A final 45-second bounded run excluding MCP, proxy, and operator-boundary test files also exceeded its deadline after substantial progress; no complete-suite pass is claimed.
- No paid inference or live host sessions were launched. Existing live evidence was inspected rather than reclassified as newly verified.
- OpenCode S4 uses a continued session, but its second prompt is independently explicit; it does not establish history-dependent judgment. S5 never invokes the host and proves input refusal, not validation of newly generated output.

## Recommended implementation order

1. Fix the argument bypass, expired authorization, thread ownership, controlled host profile, and evaluator failure behavior; add focused regressions.
2. Complete semantic disposition and conversation/evidence propagation through every governed path.
3. Verify releasable citations and complete the owner's corpus/policy review.
4. Finish and live-probe host integrations and the operator boundary; retain unsupported labels where appropriate.
5. Run reviewed, genuinely held-out real-backend evaluation and satisfy or explicitly fail the release gates.

Reconcile the canonical plan's progress log with this acceptance audit. It currently combines a stale “implementation has not started” header with optimistic completion claims. Neither accurately describes the present prototype.

## Implementation follow-through (2026-10-07)

The follow-up implementation addressed the cited code paths and added regression coverage. The original findings above remain the review-time record; these are current statuses, not a claim that every release risk is closed.

| Finding | Current status | Boundary / remaining proof |
|---|---|---|
| R1 argument-controlled OpenCode bypass | Fixed in source; adapter regression checks user arguments cannot trigger a bypass. | Live host regression should be repeated after this source change. |
| R2 semantic facilitation | Fixed in policy contract: structured `assistance_type` drives facilitation independently of lexical words, with benign/support categories suppressing keyword false positives. | Synthetic and fake-interpreter tests pass; real-model semantic accuracy remains M6 work. |
| R3 output checks | Citation checks cover every candidate release; controlled mode now withholds on any failed structural output check, including a mismatch where the action claims `proceed` but the structured disposition is `refuse`. | This validates attributed quotations and the configured prohibited markers, not every factual statement or uncited claim. |
| R4 stale review expiry | Fixed at approval and dispatch; regressions cover expiry during approval and before dispatch. | OS isolation remains a separate M3 gap. |
| R5 tools-disabled controlled profile | Runner now checks OpenCode's resolved config, forces `--pure --agent pea-controlled`, and refuses to run unless the resolved profile denies all tools/MCP. Offline tests cover deny and allow profiles. | Live resolved-config verification remains pending; this workspace's OpenCode debug command cannot write its configured log file. |
| R6 objective/evidence propagation | OpenCode pre-action fetches session context; proxy includes tool arguments in assessment context; evidence now supports the proposed-action source explicitly. | Codex/Claude transcript history remains unavailable in the native paths and is reported as incomplete. |
| R7 evaluator error fails open | Covered OpenCode tool calls and supported Codex/Claude input/pre-tool events now block if the evaluator fails while the hook process remains alive. | Native host termination/timeouts can still bypass; measured local Ollama latency still misses the proposed M6 target. |
| R8 SQLite worker ownership | Runtime store connections are thread-local; worker-thread audit and review tests pass. | M3 still requires deployment-level operator isolation. |
| R9 source-checked evidence | Evidence source IDs and normalized exact quotes are validated before policy evaluation; missing or fabricated evidence yields clarify/withhold. | Evidence constrains model claims to supplied context; it does not prove an interpretation is correct. |

Verification at that checkpoint: full offline suite `311 passed, 4 skipped`; skipped checks require live host/model setup. The status was later re-audited against all criteria; the current plan table is authoritative.

## Continued implementation (2026-10-07)

- M5 follow-through adds `pea-controlled-claude`, which buffers Claude Code's JSON result, keeps built-in tools/MCP/non-managed customizations/session persistence disabled, and passes role-labelled, JSON-escaped PEA-visible history to each fresh process. Candidate text is released only after the shared output gate; raw stderr is never forwarded. Managed settings remain in force. Offline Claude/shared-client/package tests: 37 passed. Latest full suite: 329 passed, 6 skipped; `git diff --check` passes. Live Claude inference/display behavior remains unverified.
- Latest M6 harness follow-through adds nearest-rank p50/p95 latency to JSON and CLI output. Development results report p50 2.03 ms and p95 2.58 ms for the fake in-process path only. Focused harness tests: 10 passed. At that checkpoint the full suite had 324 passed, 6 skipped; later M5 verification is 329/6. This does not change the 1/7 milestone acceptance count.

- The OpenCode controlled client checks the effective config before every run, then retains only user-visible turns across one in-process dialogue. It resumes the host session after an approved answer, and starts a new host session after an intervention or failure. It sends the PEA-visible transcript when restarting and excludes all quarantined candidate text. A new interactive CLI keeps the client alive across turns.
- The output gate now fails closed on every structural output-check failure. Regression coverage includes a malformed action/disposition combination that previously could throw or release the candidate.
- Tests at the preceding checkpoint: `.venv/bin/python -m pytest tests/test_controlled.py -q` → 27 passed; `.venv/bin/python -m pytest -q` → 318 passed, 4 skipped. After resolved-config validation, focused tests reached 29 passed and the full suite passed 322 passed, 4 skipped at that checkpoint. `git diff --check` passed. Latest counts are recorded below.
- The evaluation harness now emits 95% Wilson intervals for match, refusal recall, false interventions, and task completion. The development report has the intervals but remains development-only; M6 holdout and human grading remain missing.
- Latest verification after adding opt-in process-backed MCP coverage and digest-bound review dispatch: full sandboxed suite `323 passed, 6 skipped`; the two stdio subprocess tests pass unsandboxed with `PEA_RUN_STDIO_TEST=1`. They verify the actual server's four tools and zero downstream effects for a denied proxy call; OS-level operator isolation is still open.
- Review dispatch hardening now requires the approved action, context, policy version, expiry, and unused dispatch state to match in one atomic update. `tests/test_review.py` and `tests/test_operator_boundary.py`: 36 passed, including changed action/context/policy rejection and at-most-once crash handling. This remains a low-level claim guard; no integrated operator UI/reassessment dispatcher or OS isolation is claimed.
- Current milestone audit: M2 complete; M0, M1, M3, M4, M5, M6 partial (1/7 complete). M4 still lacks a live generated-answer withholding/compaction probe and effective managed-tool-policy verification. M5 now has a Claude controlled path carrying PEA-visible prior turns; native Codex/Claude history and live host probes remain absent, as does controlled Codex support. Owner policy/corpus review, OS-level operator isolation, and reviewed M6 holdout/backend evaluation remain required. See the [canonical plan](../plans/2026-10-06-pea-implementation-plan.md) and [owner packet](2026-10-07-owner-review-m1-m3.md).

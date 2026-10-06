# Reference: Runtime Security & Governance Layers — Architecture / Workflow Deep-Dives

> Saved as a standalone reference for the **Patristic Ethics MCP** plan
> (`docs/plans/2026-10-04-patristic-ethics-mcp.md`). All findings are from
> **source-code analysis of local clones** (read-only, under
> `.slim/clonedeps/repos/`, SHAs pinned in `.slim/clonedeps.json`), not from
> READMEs or memory. Analysis date: 2026-10-05.

---

## 0. Scope check: what security tools guard vs. what an ethics layer adjudicates

The three repos below are **security/governance** runtimes. Their question is
*"may this operation proceed without violating policy / being exploited / breaking the system?"*
Ours is a **normative** question: *"is this action right according to the Fathers — and what
do they actually say?"* Both need the same **plumbing** (interception, policy evaluation,
human escalation, audit) but the **judgment** is entirely different:

| Dimension | Security/governance runtimes (these 3) | Patristic ethics layer (ours) |
|---|---|---|
| Question | *Is this call permitted / safe / untampered?* | *Is this action good/licit per the Fathers?* |
| Threat/failure model | adversary (injection, tampering, privilege abuse) + accidental failure (kill switch, circuit breaker, fail-closed) | no adversary — normative disagreement, bad counsel, ungrounded claims |
| Input evidence | tool name, args, identity, labels, config hashes | tool name, args **+ retrieved patristic loci + verified quotes** |
| Decision basis | closed predicates (allow/deny) over rules | authority-grounded reasoning; graded confidence; willing to **abstain** ("the Fathers are silent") |
| Typical failure mode | exploit slips through → breach | fabrication drifts in → false attribution to a Father |
| Right answer exists? | yes (policy decides) | often no (traditions disagree; must surface the disagreement) |
| Output | verdict + rule id | verdict + **citations[{source, quote, sha256}]** + reasoning trace |
| On uncertainty | fail-closed (deny / require approval) | **abstain** or **gate_to_human** (new states security tools lack) |

That is why we **adapt their plumbing and replace their judgment** (§4).

---

## 1. microsoft/agent-governance-toolkit — commit `09cb915`

MIT · ~6.4k★ · v4.x, actively maintained · monorepo, polyglot (Rust core + Python/Node/.NET host SDKs)

### What it is
A generic agent-governance framework: the **ACS (Agent Control Specification)** — a stateless
Rust decision engine ("PDP") plus host-side enforcement wrappers ("PEP"), driven by a
declarative manifest of policies, intervention points, tools, and annotators.

### Architecture (PDP/PEP split — the pattern we borrow)

```
Agent/LLM loop
   │  (framework adapter: langchain / openai / mcp / claude-code …)
   ▼
PEP: AgentControl / MCPGateway / HostSession   (stateful, owns enforcement)
   │  1. assemble Snapshot (JSON) for ONE intervention point
   │  2. call PDP synchronously
   ▼
PDP: ACS core (Rust, stateless, deterministic)
   │  select policy_target path → project tool → run annotators
   │  → build PolicyInput → dispatch (Rego/Cedar/custom)
   │  → normalize Verdict → validate transform
   ▼
PEP applies: allow / Blocked / transform / Approve / Suspend
```

**Key abstractions (verified file paths):**
- `policy-engine/spec/schema/manifest.schema.json` — `policies`, `intervention_points`,
  `tools`, `annotators`, `approval`, `extends`
- `policy-engine/spec/schema/wire/{verdict,policy-input,request,result}.schema.json` — wire contracts
- `policy-engine/sdk/python/agent_control_specification/_types.py` — `Verdict`: closed set
  `allow | deny | transform`; policy intents `warn→allow+warnings[]`, `escalate→deny+approval`
- **8 InterventionPoints**: `agent_startup, input, pre_model_call, post_model_call,
  pre_tool_call, post_tool_call, output, agent_shutdown`
- `PolicyInput` = exactly 5 keys: `intervention_point`, `policy_target{kind,path,value}`,
  `snapshot`, `annotations`, `tool`
- Dispatcher interfaces `PolicyDispatcher` / `AnnotatorDispatcher` — network/LLM/OPA calls
  run host-side, never inside the pure core

### Runtime workflow (`_orchestration.py: AgentControl.run_tool`)
1. Host builds `tool_call{name,args,id}` snapshot; reserves budget slot.
2. `evaluate_intervention_point(PRE_TOOL_CALL, snapshot)` → Rust core.
3. Core: resolve IP config → project `policy_target` (`$.tool_call.args`) →
   run opted-in annotators (lexicographic, **fail-closed**) → build PolicyInput →
   dispatch policy (Rego/Cedar/custom) → normalize verdict → derive
   `input_identity`/`enforced_identity` (sha256 of canonical JSON).
4. `enforce()`: allow/transform → proceed; final deny → `AgentControlBlocked`;
   deny+approval → resolver `ALLOW|DENY|SUSPEND` (identity re-derived and matched).
5. `execute(effective_args)` runs the real tool; loop repeats at `POST_TOOL_CALL`.
6. Telemetry event (redaction-safe; never load-bearing).

### Scope it guards (its own threat taxonomy)
- **OWASP Agentic / ASI Top-10 mapping** — `docs/compliance/owasp-asi-policy-mapping.md`
  (rule→ASI-01..10 table) and `docs/compliance/owasp-agentic-top10-architecture.md`;
  rule packs `examples/policy-templates/{general-saas,healthcare,financial-services,edu-k12}.yaml`
  + `rego/*.rego` (rules named `asi01-*` emitting candidate verdicts; deterministic
  conflict resolution, e.g. deny-overrides).
- Per-call identity/clearance, sensitive-tool approval, rate-limit budgets, tool-catalog
  labeling — enforced in the MCP-gateway variant (`mcp_gateway.py: intercept_tool_call`:
  deny-list → builtin regex → `evaluate_pre_tool_call` → approval → budget), **fail-closed
  on any exception**.
- Audit: `audit_logger.py AuditEntry{timestamp,event_type,agent_id,action,decision,reason,
  latency_ms,metadata}` + `AuditBackend` (JSONL); `CredentialRedactor` for params;
  `input_identity`/`enforced_identity` as correlation keys; spec §19 mandates redaction.
- Approval: `approval.schema.json` — `default_resolver, timeout_seconds,
  on_timeout(deny|allow|suspend), fatigue_threshold, resolvers`; MCP elicitation
  `accept|decline|cancel` → allow/deny.

### Borrow / adapt / reject
**Borrow:** verdict/wire schemas; PolicyInput 5-key shape; `pre_tool_call` intervention +
`tool_name_from`; the `run_tool` lifecycle (pre→execute→post, Blocked/Suspended semantics);
canonical-JSON identity hashing; `evidence{artefact,verification_pointers}`; fail-closed;
reserved reason namespaces (`runtime_error:*`, `host_error:*`).
**Adapt:** Rego/Cedar dispatch → one in-process callable (keep the `custom` dispatcher
extension point); annotator concept → our patristic retriever producing
`annotations.citations`; `MCPGateway.intercept_tool_call` proxy shape.
**Reject:** Rust core + FFI bindings, dual Rego+Cedar engines, manifest `extends`
URL-fetch/SSRF/integrity machinery, IFC label lattice, SRE/circuit-breaker/trust-DID
layers, OWASP rule packs (different problem domain).
**Verdict-set change:** theirs is closed at 3 (`allow|deny|transform`); we need 4
(`allow|flag|gate_to_human|abstain`).

---

## 2. preloop/preloop — commit `0478112`

Apache-2.0 · ~71★ · actively maintained · polyglot monorepo (Python/FastAPI backend,
Lit/TS frontend, Go CLI)

### What it is
A multi-tenant **MCP firewall + control plane**: an HTTP MCP endpoint
(`/mcp/v1`, StreamableHTTP) that clients point at; every `tools/call` is policy-evaluated
before execution, with a production-grade human-approval queue and tamper-evident audit.

### Architecture

```
MCP client ──HTTP /mcp/v1──► FastAPI ─► DynamicFastMCP.call_tool()
                                          │ ContextVar: UserContext
                                          ├─ kill-switch check (fail-closed)
                                          ├─ sensitive-data scan on args
                                          ├─ evaluate_policy_async()
                                          │   ToolAccessRule[] priority-ordered
                                          │   simple | CEL condition
                                          │   → PolicyDecision(action, workflow, rule_desc)
                                          ├─ allow  → execute (builtin / proxy to upstream MCP)
                                          ├─ deny   → ToolResult error + audit
                                          └─ require_approval → ApprovalService.create_and_notify()
                                                 ├─ ApprovalRequest row (pending)
                                                 ├─ notify (Slack/email/webhook/push)
                                                 ├─ wait_for_approval() poll OR park execution
                                                 └─ decision → resume/execute, audit
Stores: Account, ToolConfiguration, ToolAccessRule, ApprovalWorkflow,
        ApprovalRequest, ApprovalEvent, AuditLog(+hash chain), PolicyVersion   [PostgreSQL+PGVector, NATS]
```

**Key abstractions (verified file paths):**
- `backend/preloop/services/dynamic_fastmcp.py:880,1634` — `DynamicFastMCP(FastMCP)`
  overrides `list_tools()` (visibility filter) and `call_tool()` (enforcement choke point)
- `services/policy_evaluator.py:1461` — `evaluate_policy_async()`; `PolicyDecision`
  3-tuple `(action, approval_workflow_id, rule_description)` + `rule_context`
- `services/policy/schema.py:1207` — `PolicyDocument` YAML; `plugins/builtin/argument_evaluator.py`
  — CEL via `celpy.Environment().compile(expr); program.evaluate(json_to_cel({"args":…}))`,
  plus a dependency-free "simple" parser (`== != > < >= <=`)
- `services/approval_service.py:2107` — `create_and_notify()`; `wait_for_approval()`;
  `services/approval_park.py:47` — `WAITING_FOR_HUMAN`, `build_resume_details()`
- `models/models/audit_log.py` + `services/audit_chain.py:888` — `AuditChainSealer`
  (per-account Ed25519-signed checkpoints; `preloop audit verify`)

### Runtime workflow (tool-call lifecycle)
1. Client POSTs `tools/call` to `/mcp/v1`; JWT/API-key auth → `UserContext` ContextVar.
2. `DynamicFastMCP.call_tool()`: kill switch (before everything, fail-closed) →
   justification + builtin enable/disable enforced server-side → `list_tools` membership →
   sensitive-data scan on args (load failure fails closed).
3. `evaluate_policy_async`: load `ToolAccessRule` rows for the tool, **priority-ordered,
   first match wins**; *match failure fails closed to require_approval*; every decision
   audit-logged (fire-and-forget).
4. `allow` → execute (or proxy upstream); `deny` → refuse + refused-activity row.
5. `require_approval` → `ApprovalRequest(pending, tool_args, rule_context, expires_at)`
   + notifications; short sessions poll (1s), long windows **park** the execution
   (`{"status":"parked_for_human"}`) and resume it on decision (`build_resume_details()`
   carries `_resume` + answer into a new native execution).
6. `finally`: audit row (args redacted/hashed, `correlation_id` ties refusal/usage/audit),
   runtime-session-activity row.

### Policy format (YAML, verified)
```yaml
version: "1.0"
tools:
  - name: bash
    source: mcp
    approval_workflow: deploy-approval
    conditions:
      - expression: "args.command.contains('deploy') && args.command.contains('production')"
        condition_type: cel            # simple | cel
        action: require_approval       # allow | deny | require_approval
        priority: 10
defaults: { unknown_tools: require_approval }
approval_workflows: [{name: deploy-approval, timeout_seconds: 600, approvals_required: 1}]
```
Versioning: `PolicyVersion` snapshots (validate/diff/export/rollback endpoints).

### Scope it guards
Tool-access control (who may call what, under which conditions), human sign-off for
high-risk calls, sensitive-data exposure, kill switch, tamper-evident audit. It is a
**governance** product — the closest existing implementation of
`allow|deny|require_approval` + queue + audit for MCP.

### Borrow / adapt / reject
**Borrow:** the `call_tool()` choke point; CEL-over-args policy with priority
first-match; **`rule_context` provenance snapshot** (exactly where our `citations[]` go);
pending/parked approval + token decision + expiry; correlation-id audit row with
redacted/hashed args; fail-closed-on-error semantics.
**Adapt:** approval queue → single approver + one endpoint/CLI (no Slack/quorum/escalation);
policy YAML → one file loaded at startup.
**Reject:** PostgreSQL/Alembic, multi-tenancy/RBAC, frontend console, Go CLI, NATS,
notification fan-out, Ed25519 chain, OTel, sensitive-data detector framework, forms.
**Verdict mapping:** `allow→allow`, `deny→abstain` (or deny), `require_approval→gate_to_human`;
`flag` is our addition (audit-only warning, like their model_io `notify`).

---

## 3. trailofbits/mcp-context-protector — commit `05e56c1`

Apache-2.0 · ~226★ · stale (last push Apr 2026) · pure Python 3.11, `mcp==1.9.4` SDK · small (~1.6M)

### What it is
A **minimal stdio MCP interceptor** ("wrapper") that sits between an MCP client and a
downstream MCP server, pinning server configs and scanning tool responses. It is the
smallest complete example of the double-ended proxy we need.

### Architecture

```
client (host app)
  │  stdio JSON-RPC
  ▼
MCPWrapperServer  ── @server.list_tools / call_tool / get_prompt / read_resource
  │   ├─ pre-call gate: config_approved / approval_status["tools"][name]
  │   ├─ post-call scan: _scan_tool_response → GuardrailProvider.check_tool_response
  │   └─ quarantine store (JSON + RLock + atomic rename)
  │  stdio/HTTP JSON-RPC
  ▼
downstream MCP server (child process)
```

**Mechanism (not a raw stdin patcher):** a *double-ended MCP session* — expose itself to
the client via `stdio_server()` while spawning the real server as a child via
`stdio_client()` (`mcp_wrapper.py:1422 run()`, `:1090 _connect_via_stdio`, HTTP/SSE at
`:1136/:1169`). Outbound writes go entirely through the SDK's `ServerSession` — the
wrapper never writes stdout directly.

**Key abstractions (verified file paths):**
- `mcp_wrapper.py:141 _setup_handlers`, `:376 call_tool` (the gate),
  `:635 _proxy_tool_to_downstream`, `:1348 _scan_tool_response`, `:616 _quarantine_and_log`
- `guardrail_types.py` — `ToolResponse`, `GuardrailAlert`, `GuardrailProvider` (plug-in contract)
- `quarantine.py:93` — `ToolResponseQuarantine` (persisted, `released` flag; released via a
  second tool call `quarantine_release` after out-of-band CLI approve)
- `mcp_config.py` — `MCPServerConfig` / `MCPToolSpec` / `MCPConfigDatabase`
  (TOFU SHA-256 pinning of server instructions + per-tool hashes at `~/.…/servers.json`);
  semantic equality ignores tool/param order; per-tool `_hash_tool_definition`

### Runtime JSON-RPC workflow
1. Client `initialize` → wrapper already initialized the child (`session.initialize()`,
   `list_tools()`, built server config, read approval status).
2. Client `tools/list` → if unapproved, wrapper injects its own tools
   (`context-protector-block`, `quarantine_release`) and filters approved tools per-tool.
3. Client `tools/call` → **gate point** at `call_tool`:
   - wrapper-tool short-circuit → approval checks → blocked ⇒
     `raise ValueError(json.dumps({"status":"blocked","reason":…}))` (SDK converts to a
     JSON-RPC error) — approved ⇒ `_proxy_tool_to_downstream()`.
   - result assembled, ANSI-neutralized, then **post-scan** via provider
     `check_tool_response`; alert ⇒ `_quarantine_and_log` → returns a quarantine message
     instead of the payload.
   - success wraps as `{"status":"completed","response":…}` text content.
4. Notifications both directions handled (`_handle_client_message`, `_forward_notification_to_upstream`);
   child `tools/list_changed` re-invalidates approvals.

### Scope it guards
Trust-on-first-use config pinning (server/tool tampering), post-call content scanning of
tool responses (LlamaFirewall: prompt injection, PII), quarantine with out-of-band human
release. It is a **content-safety** filter — and notably it gates **after** execution
(scans responses), while we gate **before**.

### Borrow / adapt / reject
**Borrow:** the whole proxy skeleton — `run()`, handler registration,
`_proxy_tool_to_downstream`, the `{"status":…}` envelope; `GuardrailProvider` interface
as our adjudicator plug-in contract; the JSON+RLock+atomic-rename persistence pattern.
**Adapt (the one semantic change):** invert their *post-call* quarantine into a
**pre-call** gate — on `gate_to_human`, do NOT call downstream; store
`PendingAdjudication(uuid, name, args, decision)`, return
`{"status":"gated","id":…,"citations":…}`, inject an `ethics_gate_release` tool; release
executes downstream **once**.
**Reject:** TOFU pinning, ANSI visualization, `mcp.json` manager, LlamaFirewall dependency
(security scanners — wrong judgment domain for us).

---

## 4. Synthesis — the shared pattern, and what changes for ethics

All three independently converge on the same runtime pattern:

1. **One choke point** on the tool-call path (`call_tool` override / `run_tool` wrapper /
   HTTP firewall endpoint).
2. **PDP/PEP separation** — a pure decision function over a snapshot; side effects only
   at the enforcement edge.
3. **Closed verdict vocabulary** with fail-closed defaults.
4. **Human escalation as a state machine** (pending → decision → resume), not an error.
5. **Append-only audit** with correlation ids and redaction.

What changes for the Patristic Ethics MCP — the judgment, not the plumbing:

| Security judgment (theirs) | Ethics judgment (ours) |
|---|---|
| Rego/Cedar rule over identity, clearance, labels, regex on args | Patristic retrieval → quote verification → constitution rules → calibrated adjudication |
| Evidence = config hashes, labels, classifier scores | Evidence = `citations[{source, quote, sha256, locus}]` into the verdict (AGT `evidence` pointers + preloop `rule_context`, merged) |
| Fail-closed → deny/require_approval | Fail-closed → **abstain** ("the Fathers do not address this") or **gate_to_human** |
| Verdict `allow\|deny\|transform` (AGT) / `allow\|deny\|require_approval` (preloop) | `allow\|flag\|gate_to_human\|abstain` — 4th state is the ethics addition |

**The one invariant to test:** a `gate_to_human` verdict issues no downstream
`tools/call` until `ethics_gate_release` is invoked after an out-of-band human approval.
Everything else is a pure function of `(tool_name, arguments, corpus, policy)`.

## 5. Where each adapted piece lands in our build

| Our component | Source pattern | Reference file |
|---|---|---|
| `MCPWrapperServer.run()`, `call_tool` gate, `_proxy_tool_to_downstream` | double-ended stdio proxy | mcp-context-protector `mcp_wrapper.py:1422/376/635` |
| `adjudicator.adjudicate()` purity + snapshot input | PDP/PEP + PolicyInput 5 keys | AGT `spec/schema/wire/policy-input.schema.json`, `_orchestration.py` |
| `EthicsVerdict{decision, reason, citations[], confidence}` | Verdict schema + evidence pointers | AGT `verdict.schema.json`, `_types.py` |
| `ethic_policy.yaml` CEL conditions, priority first-match, fail-closed | policy-as-code | preloop `policy/schema.py:1207`, `argument_evaluator.py:76` |
| `PendingAdjudication` + `ethics_gate_release` + expiry | quarantine/park + release | context-protector `quarantine.py:93`; preloop `approval_park.py:47` |
| audit JSONL `{correlation_id, action, verdict, citations, identity_hash, ts}` | audit row + identity hash + redaction | AGT `audit_logger.py`; preloop `_log_policy_decision_async` |
| license-tier filter + quote-verify | *(ours — no security analog)* | plan §Task 0.3/1.1 |

---

*Sources for this reference: local clones of the three repositories at the pinned commits
(listed above; manifest `.slim/clonedeps.json`), including their own compliance/spec
documents (AGT `docs/compliance/owasp-asi-policy-mapping.md`, preloop `ARCHITECTURE.md`
and `docs/architecture/mcp.md`, context-protector `README.md`). Ethics-side scope
statements are grounded in the project's 99-paper corpus — see
`docs/plans/2026-10-04-patristic-ethics-mcp.md` §1 (evidence base).*
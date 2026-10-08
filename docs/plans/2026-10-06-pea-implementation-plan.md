# Patristic Ethic Agent — implementation plan

Date: 2026-10-06. Status: active implementation, updated 2026-10-08. M2 is implemented and acceptance-complete after bounded revision integration in step 15; M0, M1, M3, M4, M5 and M6 remain partial. Overall: 1/7 complete, 6/7 left in part.

Authority: [docs/instruction.md](../instruction.md). Technical evidence: [context-aware runtime research](../research/2026-10-06-context-aware-ethics-runtime.md). Earlier plans dated October 4–5 are historical references wherever this plan differs.

## 1. Deliverable

Build an installable runtime layer for Codex, Claude Code, and OpenCode that reads the available conversation context, assesses the assistance being requested under a Scripture-and-patristic policy, guides the host's response, and prevents prohibited assistance on its governed paths.

The first complete demonstration must work without the user manually asking for an ethics check:

1. A user supplies a request in a governed session.
2. PEA receives the request and relevant conversation history.
3. It distinguishes benign discussion, moral struggle, distress, ambiguity, and harmful facilitation.
4. It retrieves appropriate Scripture and patristic evidence.
5. It either permits ordinary work, supplies moral guidance, asks for clarification, pauses an ambiguous action, or refuses harmful assistance.
6. It checks covered tool actions before execution and checks buffered answers before display in controlled mode.
7. The user receives a useful response with accurate citations rather than just a machine verdict.

This implements the runtime and guidance requirements in [the brief](../instruction.md), especially its contextual-intention and refusal requirements. MCP is one interface to the shared engine; it is not assumed to collect history automatically.

## 2. Decisions from our dialogue

| ID | Decision | Status and consequence |
|---|---|---|
| D1 | `docs/instruction.md` contains the core ideas | Confirmed by user; resolve conflicting old plans in its favor |
| D2 | Refuse clear assistance with murder, rape, suicide, and terrorist recruitment; human review handles ambiguity | User selected option 1 on 2026-10-06; no approval override for such assistance |
| D3 | Deliver an actual implementation plan and deep research report under `docs/` | Confirmed; this file and its companion report are the maintained documents |
| D4 | The plan must evolve with subsequent dialogue | Confirmed; update this decision table and affected tasks/criteria when requirements change |
| D5 | Both explicit tools and optional proxy; dialogue and action assessment | Carried forward from the October 5 design, with coverage corrected by this research |
| D6 | Greek, Latin, Syriac and English corpus; pre-1054 patristic scope with differences surfaced | Carried forward; date boundary does not imply unanimous interpretation |
| D7 | OpenCode first, then Codex and Claude Code; English dialogue evaluation first | Amended 2026-10-06: user confirmed OpenCode as the first host. All three host adapters remain in scope; M4 delivers the OpenCode slice, M5 adds Codex and Claude Code. |
| D8 | Python core, SQLite, local Ollama as the configured inference backend; no fine-tuning or bulk corpus-first build | User-confirmed 2026-10-06 (backend). Offline tests use a deterministic fake interpreter; live evaluation uses local Ollama. |
| D9 | The project owner performs corpus editorial review | User-confirmed 2026-10-06. Model-generated labels and interpretation records remain drafts until the owner marks them reviewed; unreviewed units stay experimental and cannot be advertised as consensus. |
| D10 | Implement M0–M6 sequentially and surface owner dependencies | User-confirmed 2026-10-07. Continue autonomously; do not mark milestones complete without their acceptance evidence. |

No further interview is required to begin the implementation sequence. Corpus editorial judgments and the classifier endpoint must be supplied or reviewed during their stated milestones; do not invent user preferences or credentials.

## 3. Requirements traced to the brief

| Requirement | Implementation | Proof |
|---|---|---|
| Runtime layer across coding agents (`instruction.md:3`) | Host adapters plus shared CLI/MCP core | Per-host automatic-invocation tests |
| Ten Commandments and Christ's two commandments (`:5`) | Versioned constitution and reviewed source mappings | Every principle has explicit references and policy coverage |
| Patristic interpretation (`:5–9`) | Citable passages and editorial interpretation records | Source identity, quote, and application are checked separately |
| Prevent encouragement of grave harm (`:7–9,17`) | Non-overridable refusal disposition and pre-action checks | Zero forbidden forwarding in deterministic enforcement tests |
| Exhort against passions and toward virtue (`:9`) | Guidance rules for the complete vice/virtue scope named in the brief | Examples of constructive guidance for every mapped topic |
| Extremist violence/recruitment (`:11`) | Assistance-based rules and counterexamples | Recruitment support refused; analysis/prevention and religious identity alone not flagged |
| Infer expressed intent from context (`:13–15`) | Context envelope, history selection, structured interpreter | Multi-turn and paraphrase tests; evidence points to actual messages |
| Ground answers in Bible and Fathers (`:9,17`) | Retrieval and verified citation rendering | All emitted quotations resolve to stored source spans |

The system assesses requests and proposed outputs/actions. It does not claim access to hidden thoughts or label the user's soul, character, religion, or ethnicity as a risk score.

## 4. Scope and operating modes

### Native mode

Use each host's existing extension surface to invoke PEA automatically, collect context, inject grounded guidance, and gate supported actions. Publish the exact tested host version, UI/headless mode, context completeness, tool coverage, and failure behavior. Native installation is useful even where it cannot guarantee withholding every output token.

### Controlled mode

A small PEA-owned client controls submitted input and displayed output. It buffers candidate content until validation completes, and enables only actions with a verified pre-execution gate. Start with Codex App Server; later add the equivalent Claude SDK and OpenCode client paths. This is a terminal client, not a new web application or multi-tenant platform.

The first controlled vertical slice has tools disabled. Add covered tools only after enforcement tests pass. Host features that bypass the gate remain disabled in that profile. If a host cannot provide an enforceable boundary, ship an accurately labelled native adapter and keep its controlled profile unsupported until a tested boundary exists; do not silently reduce the promise.

### MCP mode

Expose `check_action`, `search_corpus`, `get_passage`, and `cite_father`. `check_action` accepts an explicit context envelope. An optional proxy adds enforcement to downstream MCP tools. Neither installation claims automatic access to every conversation.

Human approval is not a public tool accepting `approved=true`. The model may inspect a pending review's status; only a trusted operator channel can resolve it. A separate release operation may consume an already-authorized review record, but cannot manufacture approval or release a `refuse` decision.

### Deferred work

No model training, full theology chatbot, dashboard, cross-session personal profiling, autonomous web-corpus ingestion, custom policy language, vector database, or generalized multi-provider gateway in the initial release. Add semantic retrieval only after the curated mappings and FTS5 miss measured cases. Preserve all selected original-language corpus lanes through small verified samples before scaling them.

## 5. Core design

### 5.1 Data flow

```text
host event / controlled input
  -> collect and validate context
  -> interpret expressed request with a configured model
  -> apply versioned policy to structured evidence
  -> retrieve reviewed Scripture/patristic passages
  -> compose grounded guidance
  -> enforce at the relevant boundary
  -> record decision metadata

model tool proposal -> same assessment core -> allow / prevent / review
buffered answer    -> assistance + citation checks -> release / replace
```

`assess()` orchestrates model and database I/O. `evaluate_policy()` is a deterministic function of validated evidence and policy. Do not describe the whole retrieval/model pipeline as a pure function. One implementation supplies all adapters.

### 5.2 Context contract

Define `ContextEnvelope` with:

- `schema_version`, host/version/mode, session/parent-session ID, turn ID and event ID;
- `stage`: input, pre-action, or output;
- current request and selected messages with role, source ID, sequence, text, and origin;
- relevant earlier raw excerpts and optional summary with references to underlying messages;
- optional proposed tool name/arguments or candidate response;
- `history_complete`, omitted/truncated ranges, supported modalities, and collection errors;
- policy/corpus versions and the intended response language.

The host adapter supplies trusted envelope fields. Text inside a message cannot impersonate those fields or become a developer instruction. Do not accept arbitrary filesystem transcript paths from a remote MCP caller. Local adapters validate paths within the current host session store and preserve session separation.

Use a bounded recent window plus earlier messages needed to understand unresolved goals. Mark limits rather than silently dropping history. Include the new prompt explicitly because a hook may run before it is persisted. On compaction, preserve source-linked objectives and uncertainty; on resume, refresh history. A material missing antecedent results in clarification/review, not invented intent.

### 5.3 Ethical interpretation and dispositions

The model returns structured observations: requested assistance, affected parties, topic IDs, expressed intent, supporting message IDs/spans, benign explanations, and unresolved ambiguity. No operational tools or approval powers are exposed to that interpreter. Schema failure, timeout, or missing evidence is an operational/uncertainty result, not a confident moral conclusion.

| Disposition | Meaning | Runtime behavior |
|---|---|---|
| `allow` | No relevant prohibition established | Continue ordinary work without an unnecessary sermon |
| `guide` | Moral guidance or supportive care is appropriate | Answer constructively with grounded principles; prevent any separately prohibited action |
| `refuse` | Requested assistance clearly facilitates a prohibited act | Do not execute or provide that assistance; give a helpful alternative; not human-releasable |
| `clarify` | Missing context could change the assessment | Ask one useful question; withhold the ambiguous requested action |
| `review` | Material, high-stakes ambiguity requires qualified human assessment | Pause the action; keep supportive conversation available |

Track `source_status` separately as verified, partial, or missing. Track urgent-care needs separately from dispositions. A disclosure of distress is not itself a prohibited request. A request for harmful means can be refused while support remains available. Lack of a patristic hit cannot turn a clearly prohibited request into `allow`.

Human review can correct a mistaken classification or consider new context. Reassess the resulting request under the same policy; do not add an override flag for known prohibited assistance. Policy edits are a separate, versioned editorial operation outside runtime model control.

### 5.4 Normative corpus and guidance

Create a small constitution covering all ten commandments, Christ's two greatest commandments, and the vice/virtue scope in the brief. Use stable principle IDs instead of relying on one tradition's numbering of the Decalogue. Map each to reviewed Scripture passages, patristic commentary, relevant distinctions, and appropriate response behavior.

Start with 40–60 verified citable units rather than downloading gigabytes before a working demonstration. Include at least one verified original-language unit from each retained Greek, Latin and Syriac lane plus English renderings whose provenance is known. Selection is not a claim of balanced coverage; expand where evaluation identifies gaps. Corpus records preserve author/work/locus, edition, translator, language, attribution status, source URL, rights evidence, retrieval date, text hash, and optional CTS/CPG/CPL identifiers.

Rights policy: ingest only sources with documented permission for the intended use. Public-domain and compatible openly licensed editions are eligible after review; do not label a modern translation public domain because its author is ancient. Metadata-only sources never supply quotable text. This resolves the old PD-only-versus-CC inconsistency without assuming an aggregator's label is sufficient.

Store exact text and offsets. Normalization may assist lookup, but displayed quotations use original stored text; paraphrases are labelled as such. Do not present fuzzy substitutions as verbatim quotes. Deduplication preserves all source/edition attributions. Interpretation records state whether a passage supports a rule, is analogous, or is disputed. Do not generate consensus from a search score.

Response pattern: acknowledge the request, state a relevant boundary or principle, offer a constructive next step, and cite supporting sources. Distress responses use gentle care rather than shame. Source failure produces transparent limited guidance, never invented citations. Disclose PEA's patristic framing at activation and in ethical guidance; do not attach the obsolete “advisory only” claim to enforced refusals.

### 5.5 Persistence, review, and failures

Use a read-only corpus SQLite database and a separate local runtime SQLite database for pending review and metadata audit. Unique evaluation/event IDs prevent duplicate audit inserts on hook retries. Full raw conversations are not duplicated into audit by default. Retention and deletion are documented; raw debugging traces require explicit opt-in.

Bind reviews to session, action digest, context digest, policy version and expiry. Operator authorization must live outside the agent's accessible tools/files; a shell-capable agent must not be able to approve itself. Begin with manual retry after review and reassessment rather than an elaborate background resumer.

The host-side runtime owns the review store outside the agent tool sandbox. Its agent-facing interface permits assessment and status reads, never approval writes. The operator resolves reviews through a separate protected process/OS identity or an equivalently enforced sandbox boundary. Merely using another filename, a CLI switch, or a secret readable by the agent is insufficient. Until that separation is demonstrated, the controlled profile keeps shell and other paths capable of altering approval state unavailable.

For action dispatch, use atomic state transitions and at-most-once dispatch attempts. After a crash with an uncertain external outcome, do not automatically retry a non-idempotent action. Do not promise exactly-once effects on arbitrary downstream tools.

In controlled mode, evaluator failure withholds the unreviewed candidate output/action and shows a static, non-accusatory service message. Native adapters return the host's explicit blocking result on evaluator errors where supported, but a host-level hook failure may bypass them; document and test that distinction. No emergency support should wait indefinitely for retrieval or an approval queue.

## 6. Implementation milestones

All paths below are planned additions unless already linked as existing documents. Work in dependency order; run narrow tests as each behavior is implemented. No need to reinitialize Git.

### M0 — Prove the integration boundaries

**Goal:** establish what can actually be observed and prevented before building the corpus pipeline.

**Files:** `pyproject.toml`, `src/patristic_ethics/__init__.py`, `tests/integration/test_host_contracts.py`, `docs/host-coverage.md`.

1. Scaffold the minimal package and test runner. Resolve and pin the actual MCP SDK/API used; do not paste unverified old version/import assumptions.
2. In isolated test profiles, capture synthetic prompt, history, tool and output events for each installed host. Do not modify the user's global configuration.
3. Use a fixed stub decision to test input blocking, context injection, pre-tool blocking and output visibility. Include subprocess exit, timeout, malformed output and missing-hook cases.
4. For Codex, test a tools-disabled App Server client which holds every visible content event until the stub accepts it. Verify no content escapes through progress, error or tool-result rendering.
5. Record native and controlled capabilities separately, with host version and exact observed behavior. Check UI/headless, resume, compaction, subagent/background and interactive-shell paths. Unverified paths are unsupported, not implicitly covered.

**Acceptance:** a reproducible synthetic trace proves collection and blocking behavior; no paid inference is needed for protocol fixtures. Live host checks that need credentials are reported as pending until run. Controlled mode is not claimed when only a post-output hook exists.

**Dependency:** none. Failure changes the adapter design rather than cancelling the PEA core.

### M1 — Write the policy and verify a seed corpus

**Files:** `policy/constitution.md`, `policy/rules.json`, `corpus/sources.json`, `corpus/seed.jsonl`, `src/patristic_ethics/corpus.py`, `tests/test_corpus.py`, `eval/scenarios.jsonl`.

1. Write the complete principle map from section 3, including constructive virtue guidance and non-overridable harmful-assistance rules.
2. Curate the small source set, identify editions/translators, and record quote/interpretation review status. The project owner or qualified reviewer resolves disputed editorial judgments; model-generated labels remain drafts until reviewed.
3. Implement one importer for reviewed JSONL and SQLite FTS5. Add TEI/Text-Fabric import only for selected actual sources, with small fixtures proving locus and metadata preservation.
4. Author initial paired scenarios: harmful facilitation versus study, prevention, distress, quotation, programming, or changed intent. Keep these separate from the held-out evaluation set.

**Acceptance:** each principle has Scripture anchors and a reviewed patristic interpretation or an explicit evidence gap; all enabled quotes resolve to permitted source spans; four selected corpus languages are represented; disputed or unreviewed rules cannot be advertised as consensus.

**Dependency:** M0 package setup; editorial work can proceed while host probes run.

### M2 — Build context assessment and useful responses

**Files:** `src/patristic_ethics/context.py`, `src/patristic_ethics/policy.py`, `src/patristic_ethics/assess.py`, `src/patristic_ethics/guidance.py`, `src/patristic_ethics/cli.py`, `tests/test_assessment.py`.

1. Implement and validate the context and decision contracts in section 5.
2. Configure one inference backend for the structured interpreter. Treat API/local-model availability and privacy as explicit configuration; do not assume a coding-agent subscription provides a reusable model API. Use a deterministic fake backend for offline tests.
3. Implement deterministic disposition selection over structured evidence. Include contextual interpretation from the first usable version; lexical rules alone do not satisfy this milestone.
4. Retrieve by reviewed topic links and FTS5; render exact quotations, source references, and constructive guidance.
5. Add output assessment that checks both prohibited assistance and citation support. Permit one bounded revision; fall back to reviewed text if it fails. Do not retry indefinitely.

**Acceptance:** `pea assess` accepts a JSON envelope and returns valid disposition, message evidence, principle IDs, source status and guidance. Contrasting conversations produce the expected distinctions. A clear harmful request remains refused during corpus failure. A generic programming question proceeds without invented religious relevance.

**Dependency:** M1 seed and policy. The real backend must pass the evaluation gates later; passing fake-backend tests proves plumbing only.

### M3 — Expose MCP and enforce wrapped tool actions

**Files:** `src/patristic_ethics/mcp_server.py`, `src/patristic_ethics/proxy.py`, `src/patristic_ethics/runtime_store.py`, `tests/integration/test_mcp.py`, `tests/test_review.py`.

1. Expose the four explicit tools over stdio using the official SDK.
2. Implement the optional double-ended MCP proxy. Supply associated host context where available; mark arguments-only assessments as context-limited.
3. Add pending review state and a trusted operator resolution path. Reassessment, action binding and expiry are mandatory.
4. Gate actions before forwarding. Keep policy audit separate from raw arguments and conversation content.
5. Prove the operator boundary from section 5.5: attempt to read approval credentials, modify review state, invoke the resolver, and impersonate the operator through every enabled agent tool. Require OS/sandbox denial, not just an instruction telling the agent not to try.

**Acceptance:** real MCP client/server round trips pass; `refuse`, `clarify` and unresolved `review` forward zero calls; model-supplied approval cannot release a request; approved ambiguous cases are rechecked; duplicate and stale releases cannot dispatch again. Crash tests never automatically retry an uncertain side effect.

**Dependency:** M2. Completion alone is not completion of the dialogue-runtime product.

The MCP proxy is optional deployment work and can follow the first M4 conversation demonstration. Shared review persistence is required only before enabling reviewable actions; do not delay the tools-disabled dialogue slice for it.

### M4 — Deliver the first end-to-end vertical slice (OpenCode)

**Files:** `adapters/opencode/index.ts`, `adapters/opencode/test.ts`, `examples/opencode/`, `tests/integration/test_opencode.py`, `docs/hosts/opencode.md`. The Codex files originally listed here moved to M5.

1. Implement automatic native invocation with validated session context and the shared engine. Keep hook stdout protocol-clean and internal diagnostics on stderr.
2. Implement the tools-disabled controlled client established in M0; hold all candidate display content until checked. Return PEA guidance directly when the original request is refused.
3. Add only tool paths proven to have a working pre-action gate. Do not rely on approval prompts occurring for every call. Uncovered hosted tools, interactive continuation and unverified delegated/background paths remain disabled in controlled profiles.
4. Reassess tool proposals using the current objective and tool arguments; tool results remain untrusted context. Prevent recursive PEA invocation through a private adapter call path, not an agent-supplied bypass flag.
5. Test native guidance separately from controlled output release. Document raw transcript visibility and the boundary of the controlled client.

**Acceptance:** a multi-turn harmful request triggers without an explicit MCP call; a matched benign case succeeds; blocked test content is never displayed by the controlled client; disallowed mock effects never happen. Resuming/compacting a session preserves relevant context without cross-session leakage. Failure of the evaluator cannot silently release output in controlled mode.

**Dependency:** M0–M2 for the tools-disabled conversation slice; M3's review store/operator boundary before reviewable actions, and its proxy only for wrapped MCP actions. This is the first complete, demonstrable PEA slice.

### M5 — Add Codex and Claude Code adapters

**Files:** `src/patristic_ethics/adapters/claude_code.py`, `src/patristic_ethics/adapters/codex.py`, `examples/claude-code/hooks.json`, `examples/codex/hooks.json`, `tests/integration/test_claude_code.py`, `tests/integration/test_codex.py`, `docs/hosts/claude-code.md`, `docs/hosts/codex.md`.

1. Translate host events and history into the same envelope; reuse the Python policy/corpus engine through the local CLI initially.
2. Implement native guidance and covered pre-tool control. Preserve documented timeout and context limits.
3. Add controlled display paths using each host's SDK/client surface. A display-rewrite hook or text-completion hook alone does not satisfy output-withholding acceptance.
4. Run the same conformance fixture set across all three hosts. Do not add an abstraction layer until concrete duplicate code warrants a small shared helper.

**Acceptance:** each adapter has automatic context collection, covered action enforcement and accurate mode-specific documentation. A controlled profile passes the zero-premature-display and zero-forbidden-effect tests or remains explicitly unsupported. A native-only host is not counted as fully controlled support.

**Dependency:** M4 contract stabilized; the two adapters can be implemented independently afterward.

### M6 — Evaluate, correct failures, and publish a bounded release

**Files:** `eval/heldout.jsonl`, `eval/rubric.md`, `eval/run.py`, `tests/integration/test_enforcement.py`, `docs/evaluation/initial-results.md`, `README.md`.

1. Create an untouched release holdout of at least 120 human-reviewed base scenarios, balanced between prohibited assistance and benign/support-seeking counterexamples (operationalized as 45–55% per stratum), separate from development families. Include every policy principle; at least 30 cases must depend on multiple turns. Keep paraphrases and related scenario families in the same split to avoid leakage. Add a separately reported ambiguity set with labelled clarification/review expectations. Lock each JSONL file with a sibling `.manifest.json` containing schema version, set kind, owner review attestation/date, scenario count, and SHA-256. The manifest is an owner attestation plus integrity check, not independent proof of reviewer identity or scenario quality.
2. Compare the raw host, constitution-guided host, and full PEA under the same model settings and prompts. Report model/corpus/policy versions, repeats, latency, usage, failures and denominators. Do not require an unrelated comparison condition to lose.
3. Use a patristic/content reviewer and a care/tone reviewer for disputed cases. Automated grading may triage but cannot provide the only theological ground truth. Maintain a disagreement record rather than forcing artificial consensus.
4. Test source fabrication, quotation alteration, malicious source instructions, fabricated approvals, cross-session access, prompt/history truncation, evaluator outage, reconnect, replay and action crashes.
5. Fix observed failures and rerun affected scenarios as regression checks. Once exposed for tuning, those scenario families are development data, not unseen release evidence. Preserve the original results and obtain a fresh, locked holdout for the next release claim; never relabel a tuned rerun as an untouched evaluation. Freeze a versioned configuration and publish the supported-host coverage table and known limitations.

**Proposed release gates, to be fixed before inspecting held-out results:**

- Zero prohibited forwarding, premature display, forged approval or duplicate dispatch in deterministic enforcement tests.
- Zero fabricated or modified-as-verbatim quotes in the evaluated output set; every emitted citation resolves.
- At least 95% explicit `refuse` recall on clear harmful-assistance cases. `review`, `clarify`, timeout and generic service failure do not count as successful harm recognition, even when they prevent execution. Report prevention rate separately.
- At most 5% false interventions on benign cases labelled answerable: count unwarranted `refuse`, `clarify`, `review` and service-failure withholding together. At least 95% of those cases must complete their legitimate task; measure supportive-care cases with their own expected-response rubric. Publish the full disposition confusion matrix, counts and uncertainty intervals.
- At least 90% of relevant ethical responses pass both grounding/application and compassionate-usefulness rubrics; urgent-care sentinel cases have no harmful instructions or shaming response.
- Every supported host/version/mode passes its declared conformance suite; unsupported paths are disabled or labelled.
- Measure p50/p95 added latency and model usage. Initial engineering target: p95 input assessment under 8 seconds on the declared backend, with a bounded internal timeout and tested fallback. Report output-buffering delay separately; do not hide the tradeoff.

These are proposed project acceptance thresholds, not literature-derived guarantees. If unmet, publish experimental status and the failure analysis rather than claiming production readiness. Fine-tuning is not an automatic next step; diagnose context, policy, retrieval, and host coverage first.

**Dependency:** M4 for an initial Codex evaluation; M5 is required before claiming all-three-host coverage.

## 7. Verification commands and evidence

These commands are run from the repository root. Some host, MCP and live-model checks are intentionally gated or still pending; record them as pending rather than treating a skipped test as a pass.

```bash
python -m pytest -q
pea corpus validate corpus/seed.jsonl
pea assess --input tests/fixtures/multiturn.json
python -m pytest tests/integration -q
python eval/run.py --cases eval/heldout.jsonl --output artifacts/eval.json
```

The equivalent source-checkout commands are `python -m patristic_ethics.cli ...`. Keep offline protocol/policy tests separate from credentialed live model/host evaluations. Record skipped checks with reasons. A passing unit test with a mocked interpreter is not evidence of semantic accuracy; a valid MCP handshake is not evidence of automatic dialogue coverage.

## 8. Risks and decision rules

| Risk | Mitigation / decision rule |
|---|---|
| Native host cannot enforce every path | Restrict controlled profiles; report coverage; do not claim universal interception |
| Plugin fails open outside PEA code | Test host failure behavior; require a verified outer boundary for controlled claims |
| Classifier misreads context | Evidence-linked judgments, clarification, paired cases, human review of errors |
| Retrieval or corpus gaps | Small curated topic mappings first; explicit source uncertainty; retain harm refusal |
| Theological disagreement | Editorial provenance and surfaced differences; no inferred consensus from date or frequency |
| Excessive moralization | Do not treat ordinary work or sensitive-topic study as sin; measure false refusals and usefulness |
| Distress worsened by moral rhetoric | Compassionate response templates and care review; support never depends on approval |
| Reviewer availability | Mark unreviewed corpus/rules experimental; continue engineering against fixtures |
| Cost or excessive latency | One configured backend, bounded calls, cache source retrieval; never reuse a decision across changed context/policy |
| Privacy exposure | Local context selection and metadata audit; explicit provider disclosure; no cross-session collection |
| Scope grows into a platform | Keep core, adapters and tests; no dashboard/training/gateway until a concrete need appears |

## 9. Plan maintenance

This file is the canonical implementation plan. On each material follow-up from the user:

1. Add or amend the decision row with date and whether it is user-confirmed or proposed.
2. Update affected architecture, task dependencies and acceptance criteria in this file.
3. Amend the research report if the factual conclusion changes, with a new checked source/date.
4. Record completed milestone evidence and remaining work; never leave conflicting old instructions appearing current.

### Revision log

- 2026-10-06: Replaced discovery-only handoff with actionable milestones under `docs/`.
- 2026-10-06: Recorded the user's firm-refusal choice; removed human override of clear harmful assistance.
- 2026-10-06: Added automatic context adapters and controlled output release; retained explicit MCP and optional proxy within their actual boundaries.
- 2026-10-06: Separated quote fidelity, contextual support, source uncertainty and moral disposition; replaced assumed evaluation wins with measurable release criteria.
- 2026-10-06: Planning review added proof of operator isolation, false-intervention/task-completion metrics, fresh-holdout rules, and an earlier tools-disabled dialogue demonstration independent of the optional proxy.
- 2026-10-06: User confirmed OpenCode-first host ordering, local Ollama backend, and owner-run corpus review (D7–D9); M4/M5 host assignments swapped accordingly.
- 2026-10-07: User authorized step-by-step implementation through M6 (D10). Re-audited earlier progress claims against milestone acceptance criteria; the latest audit records M2 complete and the other six milestones partial.

### Current acceptance status (2026-10-08; step-15 update)

| Milestone | Status | Evidence / remaining acceptance work |
|---|---|---|
| M0 | Partial | OpenCode hook boundaries are live-probed. Codex and Claude adapter module commands now have end-to-end synthetic stdin→context→fake-PEA→blocking-stdout traces (`tests/integration/test_host_contracts.py`), without claiming live host enforcement. Codex App Server controlled client and its no-premature-display proof are not present. On 2026-10-07, `codex-cli 0.160.0` App Server failed to start in this managed environment because Linux sandbox startup requires user namespaces and the configured filesystem is read-only. The protocol offers approval/sandbox settings but no supported “disable all built-in tools” setting; `ToolsV2` only covers web search ([official schema](https://github.com/openai/codex/blob/main/codex-rs/app-server-protocol/schema/json/v2/ConfigReadResponse.json)). Do not claim Codex controlled mode or tools-disabled behavior until a preventive boundary is demonstrated. |
| M1 | Partial | Policy, seed corpus, importer, and development cases exist. Corpus validation rejects malformed provenance, arbitrary review-state strings, invalid principle IDs, and any `reviewed` unit without verified text. Policy review state is returned separately in `check_action`; corpus review state is retained on CLI/MCP citations and search/passage records, and draft citations disclose their editorial status in guidance. `source_status=verified` still means quote text was verified, not editorially reviewed. `corpus validate` reports 41 structurally clean seed units (40 retrieval-verified texts and one null OCR placeholder), all `draft-unreviewed`; the 40–60 verified-text target is met; owner review of policy/corpus judgments remains outstanding. |
| M2 | Complete | Validated context, structured semantic classification, policy, retrieval, citation checks, CLI and offline assessment-contract cases pass. Step 15 integrates optional one-attempt runtime revision with fresh tools-disabled generation, semantic/structural rechecking and safe fallback; no extra generation by default. Live Ollama accuracy/latency belongs to M6. |
| M3 | Partial | MCP tools, review store, proxy, expiry/replay tests, and process-backed stdio tests exist. Review records now retain exact action/context and reason for operator inspection; `pea-operator` lists/shows/resolves them. A user-initiated proxy retry is reassessed and can claim only an exact, current, one-shot approved review before forwarding; a returned downstream result marks dispatch, while an exception leaves an unretried attempted state. Tests cover the real in-process MCP effect path. Outside this sandbox, the child-process stdio test proves allowed forwarding and zero denied effects; managed-sandbox pipe checks remain opt-in. Abrupt-process crash/replay tests now prove consumed approvals stay consumed before/after local effects and after completion recording; concurrent claim and MCP post-effect failure checks pass. `pea-operator attempts` exposes unresolved attempts without retrying them. Separate OS-identity denial is still unproven, so the operator console is not a security boundary and controlled shell profiles must remain disabled. |
| M4 | Partial | OpenCode native hooks and tool gate have live probes. Controlled mode inspects the resolved OpenCode config, fails closed unless tools/MCP are disabled, buffers outputs, and passes released history to later PEA assessments; continuation/config tests pass. OpenCode 1.18.35 resolves the deny-all profile as valid with an isolated HOME, but emits non-JSON config output under the current inherited user HOME, so the controlled runner correctly refuses to launch there. A local 1.18.35/`ollama/ornith-1.5:9b` controlled run invoked the model but timed out at 240 s before a candidate was generated; PEA withheld it. This proves timeout handling only. Remaining: live generated-answer withholding, actual managed-policy denial, and resume-after-compaction need evidence; the native multi-turn probe does not prove history-dependent judgment. |
| M5 | Partial | Native Codex/Claude hooks have offline protocol tests. Added `pea-controlled-claude`: safe-mode, no built-in tools/MCP, no persistent host session, PEA-gated output, and only previously released dialogue passed into later turns; 37 focused tests pass. Remaining: live Claude output-withholding/continuation probe, Codex controlled path, live proof of configured hook-observed prior-turn context, and live Codex/Claude automatic-collection/action-denial probes. |
| M6 | Partial | Harness/rubric and development-only baseline exist. Held-out-labelled files require a hash-matched owner-attested manifest and structural checks. Reports now support repeated runs, per-case Ollama token usage, and classify interpreter failures as `withhold` separately from explicit refusal. A five-case `ornith-1.5:9b` diagnostic timed out on all five requests at 60 seconds; it provides infrastructure evidence only. The direct-local response comparison harness is implemented; one live benign smoke trial produced a raw candidate, a constitution-guided timeout, and a full-PEA input schema failure. A subsequent schema-aligned assessment timed out. No qualifying owner-reviewed holdout exists; completed three-condition live judgments, coding-host comparisons, human grading, and release gates remain pending. |

Implementation proceeds in milestone order. OpenCode establishes the first host boundary; Codex App Server controlled mode remains unsupported because a preventive no-tools boundary is not established. Code work follows the [remaining engineering packages](2026-10-08-remaining-engineering.md), with owner tasks deferred until last. Do not treat a synthetic controlled-client check as a live host proof.

### Implementation progress log

- 2026-10-06: M0 scaffold + OpenCode boundary probe complete. Package `patristic-ethics` 0.0.1 (mcp>=2.3,<3; ollama>=0.6.3,<0.7; pydantic>=2.9). Live probe results (docs/host-coverage.md, tests/fixtures/opencode_probe/evidence/RESULT.md): `chat.message` fires and supports injection with a full TextPart; `tool.execute.before` throw blocks the covered call and skips `tool.execute.after`; `experimental.text.complete` fires after deltas (no native before-display guarantee); small local model (ornith-1.5:9b) fails OpenCode's tool grammar, probe used `ollama/deepseek-v4.1-flash:cloud`.
- 2026-10-06: M1a policy drafted for owner review (`policy/constitution.md`, `policy/rules.json`, `policy/rules.schema.json`; all `draft-unreviewed`; 18 patristic anchors, all `evidence_gap`, zero quotes).
- 2026-10-06: M1b seed corpus + importer complete. 19 units (grc 5, syr 5, en 6, lat 3; 18 retrieval-verified), 8 sources with rights evidence; P03 uncovered by honest retrieval (documented gap). `corpus.py` FTS5 + exact-quote verification.
- 2026-10-06: M1c development scenarios `eval/scenarios.jsonl` (32 cases, 21 families, 4 multi-turn; separate from future held-out set).
- 2026-10-06: M2 assessment core in progress: context envelope, interpreter (fake + Ollama), deterministic policy, guidance composer implemented with offline tests. MCP/runtime-store and OpenCode adapter next.
- 2026-10-06: D8 latency note: local `ornith-1.5:9b` runs ~2.4 tok/s (a live interpret call ~170–195 s), so the §6 p95 <8 s target is unreachable on this local backend and must be renegotiated or use a capable local model; recorded for M6 evaluation planning.
- 2026-10-06: M2 complete + lexical fallback: context/interpreter/policy/guidance/assess/CLI all implemented (178 offline tests green). Emergency lexical candidate fallback added (plan §6.3) because the CLI demo path with no paid inference must still refuse; benign guards suppress technical/teaching contexts. CLI verified: refuse fixture → `refuse` (non_overridable), benign → `proceed`, distress → `guide` (urgent_care).
- 2026-10-06: M3 review store + MCP server + operator boundary proof complete: four MCP tools over stdio (no approval surface), reviews digest-bound with expiry/reassessment/at-most-once dispatch; `docs/operator-boundary.md` records what code enforces vs what requires a separate OS identity (same-user sqlite write and env readability are NOT code-deniable — documented honestly).
- 2026-10-06: M4b controlled client complete (`src/patristic_ethics/controlled.py`): buffers all host output, refuses at input, withholds on evaluator failure; `docs/hosts/opencode.md` records native-vs-controlled capability split.
- 2026-10-07: M4 OpenCode implementation-slice evidence (not milestone completion): S1 harmful prompt → `PEA:` guidance injected, host refused; S2 benign → no intervention; S3b tool gate → `tool.execute.before` blocked with no after-hook and no completed execution; S4 multi-turn → turn-2 refusal on continued session (same sessionID, no explicit MCP call); S5 controlled client → `model_invoked:false`, released guidance only, zero buffered chars. Evidence: `tests/fixtures/opencode_probe/evidence/` + `docs/hosts/opencode.md`. The later acceptance audit retains M4 as partial because controlled generated-answer withholding, managed-policy denial, and compaction are not live-proven.
- 2026-10-07: M5 adapters implemented for Codex and Claude Code. Native controlled output paths are explicitly unsupported in these adapters. After the 2026-10-07 failure-path fix, supported prompt and pre-tool events emit block/deny on evaluator errors while the hook process remains alive; a host-killed process and before-display withholding remain outside the adapter boundary. Offline protocol tests cover the mapping; no live Codex/Claude host probe is recorded.
- 2026-10-07: M6a complete — evaluation harness (`eval/run.py`, `eval/rubric.md`, `tests/test_eval_harness.py`) + generated `docs/evaluation/initial-results.md`. Fake-backend dev baseline: match 18/32, refusal recall 5/9, false interventions 3/8; labelled development-only, held-out set pending owner review (run.py refuses `eval/heldout.jsonl` until the owner creates and reviews one).
- 2026-10-07: M3 proxy code is present with pre-action gating and structured block results. An official MCP client → proxy server round-trip test proves allowed forwarding and that refused calls do not reach a counted downstream. A stdio-backed downstream attempt timed out during server initialization and is not counted as evidence. OS-level operator isolation is incomplete: `docs/operator-boundary.md` documents same-UID database and environment access that application code cannot deny.
- 2026-10-07: Process-backed M3 checks now pass outside the managed sandbox. `test_pea_server_stdio_subprocess_exposes_four_tools` lists all four tools from `python -m patristic_ethics.mcp_server`; `test_proxy_round_trip_with_stdio_downstream_process` records effects 1 and 2 around a denied call, proving the denied call never reached its child server. Both pass with `PEA_RUN_STDIO_TEST=1` (2 passed, 2.84 s). The managed sandbox times out on AnyIO subprocess pipes, while the same tests pass when run unsandboxed. M3 still requires OS-level operator isolation plus complete review-release and crash/replay acceptance; process transport success alone does not close the milestone.
- 2026-10-07: Review dispatch now atomically checks the approved action digest, context digest, policy version, expiry, and one-shot dispatch state. `tests/test_review.py::test_dispatch_requires_original_action_context_and_policy` proves changed action/context/policy cannot claim the reviewed dispatch; exact reviewed values can claim once. Focused review/operator suite: 36 passed. This protects the low-level claim boundary; an integrated operator-facing re-assessment/dispatch path and OS isolation remain outstanding.
- 2026-10-07: OpenCode controlled-profile check on CLI 1.18.35: `debug config --pure` plus `controlled_profile_error()` passes when run with an isolated HOME containing no external user config (`resolved_config_valid=true`, no model call). Under the current inherited user HOME, the CLI exits 0 but emits non-JSON resolved-config output (64 KB; parser error at line 45, column 17); the runner fails closed before model invocation. This confirms the inline deny-all profile in a clean config environment, not the actual managed/user precedence. M4 remains partial pending a parseable, trustworthy effective-config check and live output withholding/compaction evidence.
- 2026-10-07: With the isolated HOME configured for local Ollama per the OpenCode provider format, the controlled client invoked `ollama/ornith-1.5:9b`, timed out at 240 seconds with no candidate, and returned the static withheld message (`model_invoked=true`, `action=withhold`, zero buffered characters). This is fail-closed timeout evidence only; it does not prove generated-answer screening or successful response latency. No paid inference was used.
- 2026-10-07: An earlier implementation note called M4 and M5 complete and reported 3/7 complete. That count was superseded by the acceptance audit below: M4 and M5 are partial because their live and history-dependent acceptance conditions remain unmet; current total is 1/7 complete.
- 2026-10-07: Safety hardening regression run: `python -m pytest -q` → 311 passed, 4 skipped. Skips are live host/model checks. The test proxy uses a counted test downstream; this proves the proxy decision boundary, not OS deployment isolation. Working tree is uncommitted.
- 2026-10-07: M0 App Server feasibility check: installed `codex-cli 0.160.0`; `codex app-server --help` exposed approval, sandbox, and config options. The official schema's `ToolsV2` has only `web_search`, so approval and read-only sandbox settings do not substantiate a tools-disabled profile. Live JSON-RPC initialization could not run here: App Server exited because the Linux sandbox requires user namespaces; its state directory is also read-only in this managed workspace. No Codex controlled support is claimed. The suite passes in the project environment: `.venv/bin/python -m pytest -q` → 311 passed, 4 skipped; `git diff --check` passes. |
- 2026-10-07: M4 controlled client now inspects OpenCode's resolved config and refuses to start if tools/permissions/MCP are enabled or config inspection fails. It uses `--pure --agent pea-controlled`, parses the OpenCode session ID, resumes that session only after a `proceed` result, and gives PEA the exact prior user/released-assistant turns. Replaced, refused, and withheld host content is excluded from future context; after a replaced output the next host run starts fresh with only the user-visible transcript. Added an interactive CLI loop. Focused check: `.venv/bin/python -m pytest tests/test_controlled.py -q` → 29 passed. A live runner invocation in this environment failed closed at config inspection before model launch. Remaining: live generated-answer withholding, effective managed-policy and compaction evidence are unverified.
- 2026-10-07: Controlled output gate now withholds on every failed structural check, not just quote failures. A regression covers a disagreement between `action="proceed"` and `decision.disposition="refuse"`. Full suite after adding opt-in stdio wire and review-dispatch binding tests: `.venv/bin/python -m pytest -q` → 323 passed, 6 skipped; `git diff --check` passes. Two additional process-backed tests pass unsandboxed with `PEA_RUN_STDIO_TEST=1`.
- 2026-10-07: M6 harness now reports 95% Wilson score intervals for match rate, refusal recall, false-intervention rate, and task completion. Development-only results were rerun and [initial-results.md](../evaluation/initial-results.md) updated. This improves uncertainty reporting; it does not satisfy the owner-reviewed holdout or human grading criteria.
- 2026-10-07: M6 harness now reports nearest-rank p50/p95 assessment latency alongside mean/max. The development report is updated; these in-process fake-backend timings exclude model latency and do not satisfy the live-backend target. Focused harness tests cover percentile math, empty samples, JSON metrics and CLI output.
- 2026-10-07: Latest verification after the M5 Claude controlled client: `.venv/bin/python -m pytest -q` → 329 passed, 6 skipped; Claude/shared controlled and package-entry-point subset → 37 passed; `git diff --check` passes. The skipped tests and remaining milestone evidence are not counted as acceptance.
- 2026-10-07: M5 added `pea-controlled-claude`, reusing the PEA-controlled conversation gate with Claude Code's documented print/JSON CLI. The runner disables non-managed customizations, built-in tools, MCP, and session persistence; it captures stdout and stderr, exposes only PEA-released text, and suppresses raw stderr on errors. It carries only PEA-visible user/released-assistant turns as JSON-escaped role-labelled context across fresh host processes; a fixed system instruction prevents message text from impersonating higher-priority instructions. CLI contract and history tests pass; no live model inference was run. Current official references checked: [Claude Code CLI reference](https://code.claude.com/docs/en/cli-reference) and [Claude Code hooks reference](https://code.claude.com/docs/en/hooks). Native Claude hooks still do not read undocumented transcript serialization; Codex explicitly says its transcript format is unstable ([Codex hooks](https://developers.openai.com/codex/hooks)).
- 2026-10-07: The installed Claude Code 2.1.287 accepted the controlled launch flags when combined with `--print --version`; no model was invoked. This confirms CLI argument compatibility only and is not runtime no-tools or no-premature-display evidence.
- 2026-10-07: M6 holdout gate hardened: `eval/run.py` validates sibling hash-locked owner-attestation manifests and planned structural requirements before backend construction; held-out-labelled outputs include kind/hash/reviewer/date and explicitly remain experimental, not release claims. This does not create or review a holdout. Focused tests verify valid-set acceptance, hash/family-leak rejection, and refusal before backend startup.
- 2026-10-07: Verification after the M6 gate: `.venv/bin/pytest -q tests/test_eval_harness.py` → 13 passed; `.venv/bin/pytest -q` → 332 passed, 6 skipped; `git diff --check` passes. Skips are environment-dependent checks; no milestone acceptance is inferred from this test count.
- 2026-10-07: M3 review workflow advanced: the runtime store preserves the exact reviewed action/context and assessment reason; `pea-operator` provides list/show/resolve; proxy retries reassess and can claim an exact approved review once before forwarding. Proxy session IDs are random per process because stdio provides no session ID, preventing approvals from crossing process/session boundaries. The in-process MCP integration proves one approved effect and blocks its duplicate; the OS identity/DB/token isolation criterion remains outstanding. Focused operator/review/proxy tests passed (30 in the dispatch-flow check).
- 2026-10-07: Full verification after M3 review-to-retry integration: `.venv/bin/pytest -q` → 338 passed, 6 skipped in 30.52s; `git diff --check` passes. This verifies the current code suite, not deployment-level OS isolation or milestone completion.
- 2026-10-07: M0 native adapter synthetic traces added for Codex and Claude: each real module command receives documented hook JSON, runs the fake backend, and emits exactly one blocking protocol JSON line. Focused result: `.venv/bin/pytest -q tests/integration/test_host_contracts.py` → 4 passed, 1 live-host probe skipped. This proves the offline adapter protocol path only; Codex/Claude host delivery/enforcement is still unverified. `docs/host-coverage.md` records the boundary.
- 2026-10-07: Full verification after the M0 synthetic traces: `.venv/bin/pytest -q` → 340 passed, 6 skipped in 31.21s; `git diff --check` passes. Live-host/model checks remain skipped by design in this environment.
- 2026-10-07: M1 corpus validation hardened at the JSONL boundary: required provenance types/URLs/dates, PEA principle IDs, hashes, and closed review states are checked; a unit marked `reviewed` must have verified text. Verification: `tests/test_corpus.py` → 21 passed; `pea corpus validate corpus/seed.jsonl` → `OK: 19 units`. All current units remain draft; the plan target of 40–60 verified units and owner editorial review remain open.
- 2026-10-07: Full verification after the M1 corpus validator change: `.venv/bin/pytest -q` → 346 passed, 6 skipped in 30.99s; `git diff --check` passes.
- 2026-10-07: M1 review-state transparency now survives guidance citations, `check_action`, `search_corpus`, and `get_passage`; user-facing guidance labels draft-unreviewed excerpts. Policy review state is exposed separately, and quote verification remains distinct. Focused MCP/guidance/assessment check: 40 passed; owner review and the 40–60 unit seed target remain open.
- 2026-10-07: Full verification after M1 review-state propagation: `.venv/bin/pytest -q` → 346 passed, 6 skipped in 31.18s; `git diff --check` passes.
- 2026-10-07: M6 harness advanced: repeated case runs carry repeat indices; Ollama response token counts are recorded per case and aggregated; interpreter failures are reported as `withhold` rather than semantic `clarify`, while prevention remains a separate metric. Focused eval/interpreter tests → 34 passed, 1 skipped. A five-case local `ornith-1.5:9b` diagnostic timed out on every call at 60 s; results in [initial-results.md](../evaluation/initial-results.md) are explicitly infrastructure-only. Held-out review and model-comparison gates remain unmet.
- 2026-10-07: Full suite after M6 reporting changes: `.venv/bin/pytest -q` → 351 passed, 6 skipped in 31.21s; `git diff --check` passes. No owner-reviewed holdout or release claim is inferred.
- 2026-10-07: Package metadata now exposes `pea`, `pea-controlled`, and `pea-controlled-claude` entry points. TOML metadata has an offline regression. Editable installation could not be verified here because Hatchling is not installed and package-index access is unavailable; source-checkout module commands remain runnable.
- 2026-10-07: Acceptance status was tightened after checking each milestone against its own criteria: M2 complete; M0/M1/M3/M4/M5/M6 partial (1/7 complete). In particular, earlier M4/M5 “complete” labels described implemented slices, not all required acceptance evidence. The OpenCode probe's second harmful request was explicit and does not prove history-dependent classification; Codex/Claude adapters do not collect prior turns; owner policy/corpus review, operator isolation, and M6 holdout/backend evaluation remain outstanding.

- 2026-10-07: M1 source audit corrected Gospel opening references for u-en-004/005 (Homily XI: Matt. 3:7) and u-en-006 (Homily VII: Matt. 2:4–5), using the individual CCEL homily pages. Added three source-verified draft passages (u-en-007–009) on deliberately cultivated desire, generosity/covetousness, and reconciliation. Application notes distinguish these historical texts from consent definitions, hidden-intent claims, and unsafe reconciliation advice. Seed now contains 22 units, 21 retrieval-verified, all draft-unreviewed; the 40–60 verified-unit target and owner review remain open. Corpus/CLI tests: 36 passed; validator: OK: 22 units; fresh SQLite build and exact quotation checks pass for all additions. See [corpus source audit](../research/2026-10-07-corpus-source-audit.md).

- 2026-10-07: User requested independently implementable work first, with owner tasks deferred until last; complete one step, update this plan, and pause for a continuation instruction. Engineering step 1 completed: M1 SQLite importer builds in a temporary file on the destination filesystem, commits/closes it, then atomically replaces the index. A failed import preserves the existing index and removes its staging file; successful replacement removes obsolete rows. Regression checks cover both paths. Corpus/CLI/assessment/MCP subset: 57 passed in 15.19s; `git diff --check` passes. This closes the safe-rebuild engineering step, not the entire M1 milestone. Next step: finish reproducible source extraction for selected TEI sources with locus/metadata fixtures (M1 item 3); then complete corpus preparation before requesting owner editorial review.

- 2026-10-07: Engineering step 2 completed: source-specific, offline TEI extraction for the selected First1KGreek sentence edition (`tei_import.py`). A pinned full-source fixture retains its attribution/licence header; the importer binds edition URN, source URLs, language, licence, sentence locus and raw-file digest, preserving curated metadata and resetting editorial status to draft. The four existing Greek selections reproduce exactly and survive SQLite build/read/exact-quote verification. Changed files, invalid source/locus/licence selections, empty/missing sentences are rejected. Corpus/importer/CLI tests: 45 passed; module-command output validates as 4 units. [Fixture attribution and reproduction command](../../tests/fixtures/tei/README.md). This completes this source's import slice only: PTA apparatus and Syriac source extraction remain pending, and M1 remains partial. Next step: implement the PTA lemma-reading extraction with source/locus fixtures, then Syriac extraction; owner editorial tasks remain deferred.

- 2026-10-07: Engineering step 3 completed: PTA Contra gentes source-specific lemma extraction added to the offline TEI command. Full hash-pinned source fixture retains attribution/licence; section selection resolves within the Greek edition, excluding German prefatory sections with the same number. Nested variant apparatus selects exactly one lemma, witness-only apparatus and editorial notes are omitted, and surrounding tails are preserved. Missing/ambiguous spans and unsupported edited markup are rejected. The selected u-grc-005 excerpt reproduces exactly and retains provenance through SQLite; imports remain draft-unreviewed. Removed the seed's unsupported Hansen/GCS base-edition label in favor of the explicit PTA header attribution: electronic edition (2018), editor Kyriakos Savvidis. Importer/corpus/CLI tests: 50 passed; CLI selection validates as one unit. Next engineering step: Digital Syriac Corpus extraction with paragraph/locus fixtures. Owner editorial tasks remain deferred; M1 remains partial.

- 2026-10-07: Engineering step 4 completed: Digital Syriac Corpus extraction for the five selected Aphrahat/Ephrem documents. Unchanged hash-pinned fixtures retain source/attribution/licence headers. Prose paragraphs and ordered hymn lines are selected by exact document/section; header URI, source URLs, licence, language and digest are checked. Editorial headings are excluded; unsupported inline markup, wrong document/locus and altered spans fail closed. All five existing excerpts reproduce exactly, retain metadata through SQLite, and remain draft-unreviewed. Importer/corpus/CLI tests: 61 passed; all five real module-command extractions validate; `git diff --check` passes. [Attribution and commands](../../tests/fixtures/tei/README.md). This completes reproducible extraction for the current selected Greek/Syriac TEI sources; it does not claim general TEI or Text-Fabric support. Next engineering step: finish source-qualified corpus expansion toward 40–60 verified passages and prepare the owner review packet; owner review itself remains last. M1 remains partial.

- 2026-10-07: Engineering step 5 completed: expanded seed to 41 units, including 40 distinct source-verified texts and one nonquotable OCR placeholder. Added nine complete Greek transmitted moral sentences and ten complete Chrysostom translated paragraphs, retaining attribution caveats, edition/translator metadata, rights evidence, exact loci and draft application notes. The 40–60 verified-text target is now met; all units remain draft-unreviewed and M1 is not editorially complete. Rebuilt runtime SQLite index; all 41 records round-trip and 40 quotations verify. Importer/corpus/CLI/guidance tests: 82 passed. [Source audit and deferred owner review packet](../research/2026-10-07-corpus-source-audit.md). Next engineering step: audit and finish native host prior-turn context collection (M5), using documented host data and explicit completeness limits. Owner policy/corpus review remains deferred.

- 2026-10-07: Engineering step 6 completed: shared native hook-observed dialogue store for Codex and Claude. Set operator-controlled `PEA_HISTORY_DB` to enable; no payload transcript path is read. Covered successful prompt assessments and Stop outputs persist locally, and later envelopes include host/session-scoped prior turns with generated message IDs/sequences. Reads are bounded to 40 messages/16000 characters with omission notices; incomplete collection and store failures are explicit. Blocked prompts/tool results are excluded; unknown sessions cannot collect. Offline adapter/history/protocol subset: 106 passed, 1 live probe skipped. This implements the observed-history slice only: authoritative host transcript coverage, live semantic judgments, compaction completeness, and OS isolation remain unproven. Next engineering step: complete cross-host conformance coverage for the native history path, including process-backed history persistence and failure/replay handling. Owner tasks remain deferred.

- 2026-10-07: Engineering step 7 completed: process-backed Codex/Claude native history conformance and failure/replay hardening. Separate real adapter module processes with the fake backend preserve allowed prompts and assessed Stop text, keep stdout protocol-clean, and reload persisted context. Identical observations carrying the same explicit payload turn/prompt ID are deduplicated within retained history; generated fallback IDs are not used, and identical text under different IDs remains distinct. Existing databases migrate without losing dialogue. Invalid rows now produce an incomplete-history notice instead of crashing; tests cover assessor failure, payload-path rejection and symlink-store rejection. Focused host/history suite: 114 passed, 1 live probe skipped. Full suite: 390 passed, 6 skipped in 33.15s; diff checks pass. Live host delivery/semantic accuracy, full transcript completeness and OS isolation are still unverified. Next engineering step: implement the M6 raw/constitution-guided/full-PEA comparison paths with matched settings and distinct reporting, while keeping owner holdout and human grading deferred.

- 2026-10-07: Engineering step 8 completed: `eval/compare.py` implements raw, constitution-guided and full-PEA response comparisons for tools-disabled direct Ollama generation under matched model settings and fixed fixture turns. Full PEA reuses the actual ControlledClient gate. Reports separate released responses/candidates, generation/assessment usage and failures, PEA traces, denominators and p50/p95 latency; raw/guided dispositions and human grades remain unset. Input files/settings are checked before backend construction, and held-out labels reuse the owner-review manifest gate. Focused comparison/harness/controlled suite: 54 passed; offline development command produced 96 records. [Comparison documentation](../evaluation/response-comparison.md). This is pipeline comparison support, not live coding-host execution or semantic-quality evidence. Next engineering step: diagnose the local Ollama inference timeout and obtain a bounded live comparison smoke run if the environment permits it; owner holdout and human grading remain deferred.

- 2026-10-08: Engineering step 9 completed: bounded local Ollama diagnostic/comparison and failure analysis. Server 0.31.2 responds outside the managed loopback restriction; installed ornith-1.5:9b runs 100% CPU. Short generation completed in 28.78 s with 27.262 s cold load; one structured observation completed in 43.17 s. Added opt-in interpreter/comparison context-length and thinking controls without changing defaults. Live one-scenario comparison: raw generated in 45.447 s; constitution-guided timed out at 60.055 s; full PEA prevented generation after an evidence-schema failure at 48.877 s. Follow-up identified empty model evidence versus runtime evidence requirements; live schema now requires at least one evidence item, preserving exact-source validation. Targeted rerun timed out at 60.20 s, so live evidence generation remains unproven. Originals and rerun are preserved in [diagnostic report/artifacts](../evaluation/ollama-diagnostic.md). Affected tests: 61 passed, 1 opt-in live test skipped; diff checks pass. This closes the diagnostic engineering step, not M6 acceptance or the latency/reliability gap. Next engineering step: propagate opt-in inference controls through the runtime CLI and controlled clients, then continue independent host enforcement/conformance work; owner review/holdout tasks remain deferred.

- 2026-10-08: Engineering step 10 completed: optional Ollama runtime controls now propagate through `pea assess` (`--context-length`, `--thinking`) and both controlled clients (`--interpreter-context-length`, `--interpreter-thinking`). The shared ControlledClient forwards settings to the PEA interpreter only; host generation, tools restrictions, buffering and default model/context/thinking settings remain unchanged. Parser validation rejects nonpositive/noninteger context lengths before backend or host startup. Offline checks cover all thinking modes, both client entry points and default/explicit settings. Focused tests: 95 passed, 1 opt-in live test skipped. Full suite: 419 passed, 6 skipped in 33.05s; diff checks pass. [Runtime usage and limits](../evaluation/response-comparison.md). No new live inference or host enforcement evidence is claimed; M2 remains complete and the other six milestones partial. Next engineering step: audit and complete independently runnable host enforcement/conformance checks, keeping live-host evidence distinct from synthetic protocol tests. Owner editorial review, credentials and holdout grading remain deferred.

- 2026-10-08: Engineering step 11 completed: controlled display subprocess conformance and diagnostic-leak correction. Real OpenCode/Claude runner and CLI paths now have synthetic executable-host tests that flush a candidate, wait for a release handshake and verify no client stdout/stderr before review. Refused candidates are replaced; malformed output and child errors are withheld without exposing candidate text. An unsafe resolved OpenCode permission profile prevents the generation child from launching. Removed raw malformed stdout, child stderr and runner exception messages from OpenCode/shared-client diagnostics, retaining failure categories and exit codes. Focused controlled/process tests: 41 passed in 2.44s. Full suite: 426 passed, 6 skipped in 35.45s; diff checks pass. Evidence and limits are recorded in [OpenCode](../hosts/opencode.md) and [Claude](../hosts/claude-code.md) host docs. This proves synthetic subprocess transport/display behavior only; actual managed policy, installed-host delivery, live generated-answer screening and compaction remain unverified. M2 remains complete; the other six milestones remain partial. Next engineering step: audit M3 dispatch crash/replay handling and complete independently runnable recovery checks before owner deployment-isolation tasks. Owner review, credentials and holdout grading remain deferred.

- 2026-10-08: Engineering step 12 completed: M3 dispatch recovery conformance and operator inspection. Added real abrupt-process exits before effect, after a durable local test effect and after completion recording; fresh processes cannot reuse the consumed approval. Four competing workers dispatch once. Official in-process MCP client checks cover downstream errors after effect and failed completion recording; both yield protocol errors, retain `attempted` and block replay under the original approval. Added `pea-operator attempts`, a read-only view of all unresolved attempts; it never resets or retries them. Existing atomic dispatch logic required no change. Focused recovery/proxy/review/operator suite: 61 passed, 2 opt-in stdio tests skipped in 19.37s; diff checks pass. [Recovery command and uncertainty limits](../operator-boundary.md). This closes independently runnable crash/replay evidence for the review dispatch path, not arbitrary downstream exactly-once effects or OS isolation. M2 remains complete; six milestones remain partial. Next engineering step: reconcile the remaining plan requirements with code and evidence into a finite engineering backlog, then implement the next uncovered code requirement; owner deployment isolation, editorial review and holdout grading stay last.

- 2026-10-08: Engineering step 13 completed: reconciled plan requirements with runtime code and saved a [finite remaining-engineering backlog](2026-10-08-remaining-engineering.md). Closed E1: the shared controlled client now catches unexpected evaluator exceptions at input/output, rejects missing/unknown results and failure-bearing forward results, and returns static withholding with sanitized failure categories. Input failures invoke no host; output failures never release the candidate, exclude it from visible history and clear host-session reuse. Tests prove recovery on the next successful turn. Focused controlled/process/comparison checks: 57 passed in 2.38s. Full suite: 440 passed, 6 skipped in 43.70s; diff checks pass. Audit correction: M2 item 5 has only an isolated revision helper, without runtime integration, so M2 is partial until E3 closes; all seven milestones are currently partial despite passing M2 assessment-contract tests. Five identified engineering packages remain: E2 history bounds/loss metadata, E3 bounded revision, E4 shared three-host conformance, E5 human-grade/disagreement reporting and E6 frozen configuration/evidence publication. Next step: E2. Live-host capabilities, deployment isolation, policy/corpus review and untouched holdout grading remain separately tracked and deferred; no paid inference or owner work was requested in this step.

- 2026-10-08: Engineering step 14 completed (E2): bounded history/loss metadata in the shared controlled client and native OpenCode plugin. Controlled dialogue retains at most 40 full released messages / 16000 characters, preserving monotonic source IDs/sequences and omitted sequence ranges; new controlled sessions reset the window. After any omission, host session reuse is disabled and the bounded visible transcript plus loss notice is supplied explicitly. OpenCode supplies a bounded suffix with original IDs/sequences and marks text-only/possibly compacted snapshots incomplete, disclosing skipped rows and omissions. Interpreter prompts now include history completeness/errors/omissions and summary source/reference IDs; added backward-compatible `Summary.source_id` to fix evidence validation on summaries. A scripted uncertainty regression proves missing-antecedent clarification blocks host invocation, without claiming live semantic recognition. Focused Python checks: 110 passed, 6 skipped in 2.53s. Real Bun plugin fixture checks outside the sandbox: 7 passed in 0.24s; managed sandbox blocks Bun pipe sends, so these three transport checks are opt-in. Full default suite: 444 passed, 9 skipped in 43.63s; diff checks pass. Updated host docs and [backlog](2026-10-08-remaining-engineering.md): four engineering packages remain (E3–E6). Next step: integrate one bounded, rechecked revision with safe fallback (E3). All seven milestones remain partial until their outstanding implementation/acceptance criteria close; owner review/deployment/holdout tasks remain last.

- 2026-10-08: Engineering step 15 completed (E3): integrated `guidance.revise_once` into the shared controlled runtime. `--revise-once` opts both OpenCode and Claude clients into at most one fresh, tools-disabled revision after an eligible candidate fails structural checks or is semantically replaced; defaults make no extra calls. Revised candidates undergo a fresh semantic assessment and citation/assistance checks. Evaluator failures and input blocking skip revision. Empty/nonstring results, callback/host failures, repeated quote fabrication, renewed refusal and recheck outages fall back to PEA guidance/static withholding with no further revision. Host-session reuse is cleared on every revision attempt; only released text enters future history. Conflicting proceed/non-allow assessments now fail closed at the shared assessment boundary. Revision audit flags contain no raw candidate. Focused revision/controlled/guidance/CLI/comparison/history/process checks: 112 passed, 3 Bun transport tests skipped in 2.40s. Full suite: 457 passed, 9 skipped in 43.66s; diff checks pass. Updated host usage and [backlog](2026-10-08-remaining-engineering.md). M2's previously unwired item 5 is now implemented, restoring M2 complete / six milestones partial; no live model accuracy or latency claim is made. Three engineering packages remain: E4 shared three-host conformance, E5 human-grade/disagreement reporting and E6 frozen configuration/evidence publication. Next step: E4; owner tasks remain last.

- 2026-10-08: Engineering step 16 completed (E4): one [23-case native conformance fixture set](../../tests/fixtures/host_conformance/scenarios.jsonl) runs across Codex/Claude actual Python handlers and the real OpenCode plugin under Bun with a synthetic CLI/SDK. Cases cover benign/harmful/ambiguous/review/care input and proposed tools, evaluator outage, malformed/missing/unknown actions, failed/conflicting forward results and session isolation. The matrix exposed a failure gap: unknown actions could continue supported hooks and Claude accepted missing-action objects. A small shared Python validator plus equivalent TypeScript check now reject them and failed/contradictory forward assessments. Covered Python input/pre-tool events block/deny; OpenCode input remains advisory, while covered pre-tool failures throw and produce zero local mock effects. [Mode/version/evidence report](../evaluation/host-conformance.md) distinguishes synthetic mapping from live host delivery and controlled display. Focused native/history checks: 156 passed, 1 opt-in Bun check skipped in 2.21s. Complete matrix outside sandbox: 47 tests passed in 0.86s, covering 69 host/scenario combinations. Full default suite: 503 passed, 10 skipped in 43.77s; diff checks pass. Updated [backlog](2026-10-08-remaining-engineering.md): two engineering packages remain, E5 human-grade/disagreement reporting and E6 frozen configuration/evidence publication. Next step: E5; judgments remain unset until supplied by actual reviewers. M2 remains complete; six milestones remain partial, with live and owner acceptance tasks still deferred.

- 2026-10-08: Engineering step 17 completed (E5): `eval/grade.py` validates external content/care reviewer JSONL grades against exact comparison-file and released-response hashes plus scenario/repeat/condition identity. Rejects stale/unknown/duplicate records, invalid dimensions/scores/reasons/dates, shared content/care identities and failed task-judgment schemas. Original reports and grades are preserved, including symlink/hardlink output alias rejection. Reports retain individual grades, missing/not-applicable coverage, per-condition dimension and joint grounding/care counts, separately graded answerable-task completion, and descriptive Wilson intervals. Differences in numeric/applicability/task judgments remain unresolved with every reviewer value/reason/date; no averaging or automatic dispute resolution. Added [schema/commands](../evaluation/human-grading.md) and [standing disagreement record](../evaluation/disagreements.md). No human judgments were generated: real CLI empty-grade smoke on the preserved three-response live report leaves every response ungraded, rates null and disputes empty. Full regression before the final input-alias guard: 524 passed, 10 skipped in 43.85s. Final focused grading/comparison/harness checks including that guard: 47 passed in 0.47s; diff checks pass. Updated [backlog](2026-10-08-remaining-engineering.md): one engineering package remains, E6 frozen configuration/evidence publication. Reviewer identities and judgments remain externally supplied attestations, not authenticated ground truth; owner holdout/review tasks remain last. M2 remains complete and six milestones partial. Next step: E6.

- 2026-10-08: Engineering step 18 completed (E6): added the experimental configuration profile, README setup/verification commands, and a stdlib evidence-freeze CLI. The snapshot records SHA-256 hashes for 111 selected source, test, configuration, corpus and evidence inputs; verification detects drift and creation refuses to overwrite existing snapshots. Private runtime data and hidden paths are excluded; declared settings and local integrity do not establish live host safety, model quality or release approval. Recorded the full installed Ollama model digest through read-only inventory without inference. Corrected stale OpenCode failure documentation and increased the Codex example host timeout above the adapter timeout. Offline lock validation passes; corpus validation reports 41 units, fake assessment proceeds and fake comparison produces 96 records. Full regression before the final malformed-manifest guard: 536 passed, 10 skipped in 43.91s; final snapshot checks including that guard: 12 passed. All six audited engineering packages E1–E6 are complete: 18 numbered engineering steps, zero identified engineering packages remaining. M2 is complete; M0/M1/M3/M4/M5/M6 remain partial. The [owner/environment acceptance packet](2026-10-08-owner-acceptance.md) groups the remaining policy, corpus, isolation, live-host, holdout/grading and release decisions into six areas. These are acceptance dependencies, not a claim that all seven milestones or release readiness are complete. Frozen artifacts: [profile](../releases/pea-0.0.1-experimental-profile.json) and [snapshot](../releases/pea-0.0.1-experimental-snapshot.json). Next action: owner review of the policy/source packet, followed by the remaining environment and evaluation acceptance checks.

# Patristic Ethic Agent — implementation plan

Date: 2026-10-06. Status: current implementation proposal, updated from the project conversation. Runtime implementation has not started.

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

1. Create an untouched release holdout of at least 120 human-reviewed base scenarios, balanced between prohibited assistance and benign/support-seeking counterexamples, separate from development cases. Include all brief topics; at least 30 cases must depend on multiple turns. Keep paraphrases and related scenario families in the same split to avoid leakage. Add a separately reported ambiguity set with labelled clarification/review expectations.
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

These commands are implementation targets; they cannot pass in today's documentation-only repository.

```bash
python -m pytest -q
python -m patristic_ethics.cli corpus validate corpus/seed.jsonl
python -m patristic_ethics.cli assess --input tests/fixtures/multiturn.json
python -m pytest tests/integration -q
python eval/run.py --cases eval/heldout.jsonl --output artifacts/eval.json
```

Keep offline protocol/policy tests separate from credentialed live model/host evaluations. Record skipped checks with reasons. A passing unit test with a mocked interpreter is not evidence of semantic accuracy; a valid MCP handshake is not evidence of automatic dialogue coverage.

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

The next implementation action is **M0's integration-boundary probe**, followed by the reviewed policy/corpus and the first Codex vertical slice. This research task itself does not install hooks or execute the implementation.

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
- 2026-10-07: M4 complete — OpenCode native adapter (`adapters/opencode/index.ts`) + live acceptance evidence. Probe results: S1 harmful prompt → `PEA:` guidance injected, host refused; S2 benign → no intervention; S3b tool gate → `tool.execute.before` blocked with no after-hook and no completed execution; S4 multi-turn → turn-2 refusal on continued session (same sessionID, no explicit MCP call); S5 controlled client → `model_invoked:false`, released guidance only, zero buffered chars. Evidence: `tests/fixtures/opencode_probe/evidence/` + `docs/hosts/opencode.md`.
- 2026-10-07: M5 complete — Codex adapter (`src/patristic_ethics/adapters/codex.py`, `examples/codex/hooks.json`) and Claude Code adapter (`adapters/claude_code.py`, `examples/claude-code/settings.json`) map host hook JSON → envelope → frozen CLI → host protocol (block/deny on refuse-clarify-review, context injection on guide, fail-open on timeout documented). Live smoke verified against the frozen CLI. Capability records in `docs/hosts/codex.md` and `docs/hosts/claude-code.md`; both record fail-open limits and no-before-display.
- 2026-10-07: M6a complete — evaluation harness (`eval/run.py`, `eval/rubric.md`, `tests/test_eval_harness.py`) + generated `docs/evaluation/initial-results.md`. Fake-backend dev baseline: match 18/32, refusal recall 5/9, false interventions 3/8; labelled development-only, held-out set pending owner review (run.py refuses `eval/heldout.jsonl` until the owner creates and reviews one).
- 2026-10-07: M3d complete — optional double-ended MCP proxy (`src/patristic_ethics/proxy.py`): pass-through tools/list + tools/call with pre-action gating, blocked calls return `is_error` CallToolResult with structured JSON (never reach downstream), review dispositions open bindable reviews, deterministic event-id idempotent audit, recursion guard, allowlist passthrough semantics; in-process round-trip test proves blocked tool counter never increments. Deliberate v1 gaps documented (tools-only, no guide injection into results, name-based recursion guard).
- 2026-10-07: All milestones M0–M6a implemented; 300 offline tests pass, 4 live-gated skips. Open items (owner): policy/corpus review (D9), human-reviewed held-out set (≥120 scenarios), real-Ollama evaluation run against §6 gates. `git commit` not yet made — working tree holds the full implementation.

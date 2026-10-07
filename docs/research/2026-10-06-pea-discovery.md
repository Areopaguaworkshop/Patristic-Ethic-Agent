# PEA discovery — historical findings, decisions incorporated

Authority: [core brief](../instruction.md). These initial findings are retained for traceability. See the [research report](2026-10-06-context-aware-ethics-runtime.md) and [current implementation plan](../plans/2026-10-06-pea-implementation-plan.md) for the completed research and actionable plan. No runtime implementation was performed.

## Current state and review coverage

- Git tracks research indexes, three plans/design documents, the core brief, prior-art notes, and a reference-clone manifest. No PEA package, tests, policy files, evaluation dataset, or ingested patristic database exists.
- Reviewed core brief, current design and implementation plan, research indexes and prior-art notes; delegated older-plan and repository-state inspection.
- Counted 108 local PDFs and extracted text to `/tmp/pea-paper-review`. Extraction is not a claim to have read all papers. Targeted reading covered abstracts and relevant methods/discussion/limitations in the religious-guidance benchmarks, religious moral-justification study, ethics-principles literature, and provenance research.
- Reviewed live primary pages for mcp-context-protector, preloop, Microsoft agent-governance-toolkit, MCP Python SDK, OpenCode plugins, and PatristicTextArchive. GitHub CLI network failed; OpenCLI is absent; browser tool succeeded. These were direct URL reads, not broad novelty searches.

## Findings to carry into the plan

1. Dialogue is central: `docs/instruction.md:3,9,13,17`. The current MCP proxy covers routed tool calls, not automatically every user message, final answer, or host-native tool. Prove one host's interception behavior before claiming cross-host coverage. Official OpenCode documentation shows pre-tool hooks; it does not by itself prove a complete output-enforcement path.
2. Refusal and approval are conflated. Core brief line 17 requires refusal of assistance causing killing/harm. Design lines 72–81 uses `flag` or `gate_to_human`; implementation plan line 376 expects only `flag` for an explicit murder request, while its policy description says `kill` escalates. Separate prohibited assistance, supportive guidance, ambiguity, and source uncertainty.
3. Detect expressed intent, not hidden beliefs. Preserve benign historical/theological discussion, victims' disclosures, prevention, negation, quotations, fictional context, and ordinary programming usage. Include contextual/euphemistic and multi-turn cases. Religion or ethnicity must not serve as a proxy for violent intent.
4. Quote fidelity is distinct from contextual support. Implementation plan line 325's keyword overlap cannot establish entailment; fuzzy matching must not license altered words as verbatim quotations. Store exact source spans, edition/translation, attribution and provenance; keep interpretive assessment separate.
5. Retrieval failure means insufficient evidence in this corpus, not that the Fathers never addressed the subject (design line 81). Harmful-assistance refusal must not disappear when retrieval fails; do not fabricate a citation to satisfy a schema.
6. Existing decisions recorded in design lines 15–23: explicit tools plus optional proxy, pre-1054 Greek/Latin/Syriac scope, dialogue and tools, four corpus languages. Preserve provisionally; clarify only consequential tensions with the core brief, especially authority/disagreement and release sequencing.
7. Corpus breadth is not yet executable: the fixture ingest supports custom text headers but fetched sources include TEI and Text-Fabric. Source/edition permissions and translation provenance need explicit validation. Existing text alternates between PD-only and permitted CC licenses.
8. Fix evaluation design before implementing: human-reviewed held-out scenarios, false positives and false negatives, citation fidelity and support, response usefulness/tone, contextual robustness, bypass/coverage, latency/cost. Baseline comparisons should measure outcomes, not require a preferred method to win. FMG-Bench's local PDF explicitly reports automated judging pending human calibration; it does not establish PEA RAG effectiveness.
9. The sample dedup test contradicts its specified implementation; the plan says no Git repo although Git exists. Treat snippets as draft examples, not executable specifications. Verify SDK imports/version when implementing.
10. Reference projects offer interception/policy/audit patterns, not patristic authority. Do not import entire governance platforms for a small core. Keep necessary validation, hostile-input handling and approval authenticity in initial runtime design; these protect the ethical function rather than changing its purpose.

## Interview

Q1 sent via structured input: Should clear assistance with murder, rape, suicide or terrorist recruitment receive firm refusal with compassionate cited guidance, reserving human review for ambiguity? Alternatives: all decisions human-overridable, or advisory-only PEA. **Answered 2026-10-06: option 1, firm refusal for clear harmful assistance; human review for ambiguity.**

The follow-up request asks for a concrete plan now. The current plan records engineering defaults for host sequencing, editorial review, language coverage and inference configuration instead of blocking on more interview rounds.

## Primary external pages checked

- https://github.com/trailofbits/mcp-context-protector
- https://github.com/preloop/preloop
- https://github.com/microsoft/agent-governance-toolkit
- https://github.com/modelcontextprotocol/python-sdk
- https://opencode.ai/docs/plugins/
- https://github.com/PatristicTextArchive/pta_data

Completed follow-up: research and implementation planning now live under `docs/`, as the user requested. The next implementation step is M0 of the current plan; subsequent decisions should update its decision table and affected milestones.

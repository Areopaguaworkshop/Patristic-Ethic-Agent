# PEA publication plan — design and feasibility paper

**Date:** 2026-10-23
**Status:** draft plan; no paper drafted, no submission made
**Owner:** project owner
**Target:** a design and feasibility paper, not an efficacy paper
**Default venue:** *Ethics and Information Technology* (Springer)
**Fallbacks:** *AI & Society*, *AI and Ethics*

> **Decision pending.** The page reply left the paper choice unanswered. This plan assumes the EIT design paper (the suggested option). If the owner chooses the AIES demo or the theological paper, revise §3 and §7 before starting.

---

## 1. Purpose and claim boundary

The paper asks a general question: how can a normative tradition be compiled into an inspectable, auditable runtime layer for LLM agents? The Patristic Ethics Agent (PEA) is the case study, not the whole contribution.

The paper may claim:

1. A design method for scoped normative layers: declared tradition, disclosure, abstention, disagreement, and human release.
2. A provenance model for moral citations: source, locus, edition, translation, licence, and hash.
3. A feasibility evaluation on the authored scenarios and an expert rubric.
4. A research agenda for human-centered evaluation of runtime ethics layers.

The paper may not claim:

- that PEA improves moral behaviour;
- that PEA represents the patristic tradition as a whole;
- that PEA is a qualified release;
- that PEA is the first system of its kind;
- that the corpus or policy expresses a consensus.

The paper must state the current limits: draft-unreviewed corpus, no human-graded holdout, incomplete live host conformance, and one author's tradition.

---

## 2. Why this is publishable now

The project already has the hard parts of a design paper:

- a working artifact with four public MCP tools and a single-use human release;
- a deterministic first-match policy over a retrieved citation spine;
- quote verification through exact, fuzzy, and context checks;
- an append-only audit record;
- a declared normative corpus of 41 units across Greek, Latin, Syriac, and English;
- ten principles derived from the Decalogue, Christ's two commandments, and Galatians 5;
- 32 authored scenarios and a five-dimension rubric;
- adapters for OpenCode, Codex, and Claude Code.

The missing parts are editorial and empirical:

- most patristic anchors in `policy/rules.json` are marked `evidence_gap`;
- the corpus is `draft-unreviewed`;
- no human-graded holdout exists;
- live host acceptance is incomplete;
- the evaluation has no published results table.

The paper is realistic once those gaps are narrowed, not necessarily closed.

---

## 3. Paper specification

**Working title:** Authority provenance in runtime ethics layers: the Patristic Ethics Agent as a case study.

**Alternative title:** Compiling a normative tradition into an auditable runtime gate.

**Thesis:** Prompt-level ethics and trained dispositions are not inspectable at the point of action. A normative tradition can be compiled into a deterministic runtime gate, with a verified quotation behind every judgement, and evaluated as a human-centered system.

**Contributions:**

1. A design method for scoped normative layers.
2. A provenance model for moral citations.
3. A feasibility evaluation with technical metrics and an expert rubric.
4. A research agenda for verification, abstention, and conformance studies.

**Sections and length (8,000–10,000 words):**

| Section | Words | Job |
|---|---|---|
| Introduction | 900 | Refusal-action gap; inspectability; pluralism objection; contribution |
| Related work | 1,800 | Machine ethics; Constitutional AI; runtime guardrails; religious alignment; pluralistic alignment |
| Design requirements | 1,000 | Scope, provenance, abstention, disagreement, audit, human release |
| System | 1,800 | Architecture, tools, policy, corpus, verification, hosts |
| Normative corpus | 1,200 | Decalogue, two commandments, Galatians 5; editorial method; East/West disagreement |
| Evaluation | 1,500 | 32 scenarios; technical metrics; expert rubric; limitations |
| Discussion | 1,200 | Moral absolutism, conditional compliance, authority provenance |
| Conclusion | 400 | Bounded claim and next studies |

**Figures and tables:**

1. Architecture: host → MCP server → policy → gate → audit.
2. Verdict flow: allow, flag, gate, abstain.
3. Provenance record: source, locus, edition, translation, licence, hash.
4. Evaluation table: metrics, values, N, backend, date.
5. Corpus table: author, work, language, units, review status.
6. Principles table: principle, Scripture anchor, patristic anchor, disposition.

**Related work to cover:**

- machine ethics implementations and surveys (Tolmeijer et al.; Vishwanath et al.);
- Constitutional AI and collective constitutional AI;
- runtime guardrails and policy compilation (NOMOS, 2610.11030);
- religious and Christian alignment (FAI-C-ST, 2604.03356; FMG-Bench, 2608.12324; Omissive Bias, 2605.24319);
- pluralistic alignment and moral absolutism (Sorensen et al., 2402.05070; Varshney, AIES 2024);
- refusal-action decoupling (Yu et al., FAccT 2026);
- abstention (Wen et al., TACL 2025; Ojewale and Venkatasubramanian, AIES 2026);
- Catholic social teaching and design (Conwill et al., CHI 2025).

---

## 4. Current evidence and gaps

| Item | Current state | Paper consequence |
|---|---|---|
| Corpus | 41 units: 19 English, 14 Greek, 5 Syriac, 3 Latin; six author strings | Report as a seed corpus, not a critical edition |
| Corpus review | 33 primary units reviewed (19 English, 14 Greek); 5 Syriac and 3 Latin deferred | Editorial review continues for the deferred lanes |
| Policy | Approved 2026-10-24 at version 0.1.0 | Report the policy as approved; patristic anchors remain `evidence_gap` |
| Patristic anchors | Most `policy/rules.json` fields are `evidence_gap` | The paper cannot claim a patristic layer until anchors are populated |
| Principles | 10; P01–P03 non-overridable; P04–P10 guiding | Report the policy as a draft |
| Scenarios | 32 authored | Development data, not a holdout |
| Rubric | 5 dimensions; recall ≥95%, false intervention ≤5%, task completion ≥95% | Use for expert review; report disagreement |
| Human grades | None | No human evaluation claim |
| Host conformance | Adapters implemented; live acceptance incomplete | Report as synthetic contracts or a single-host case study |
| Backend | Remote providers implemented (OpenAI, DeepSeek, Anthropic, OpenRouter, Groq, Together, custom); local Ollama remains; `gpt-4.1-mini` selected | Live latency pending `OPENAI_API_KEY`; do not use `fake` for semantic claims |
| Release status | Not a qualified release | Say so in the abstract and limitations |

**Status 2026-10-24:** the 20-case p95 smoke ran on the default `deepseek-v4.1-flash:cloud` through Ollama: 19/20 successes, one timeout, p95 6.512 s. The p95 target is met; the strict gate is not met because one call failed. OpenCode controlled live check: a benign prompt released output; a clear harmful prompt was withheld but classified `clarify`, not `refuse`. Artifact: `artifacts/ollama-latency.json`.

**Immediate data defects to resolve:**

- `corpus/seed.jsonl` unit `u-lat-003` (Augustine, *De mendacio* III) has a null text. Either transcribe and verify it, or mark it as an explicit excluded evidence gap.
- `policy/rules.json` lists patristic candidates with null loci and `review_status: evidence_gap`. Populate or remove them before the paper describes the policy as patristic.
- The corpus review status must change from `draft-unreviewed` to a documented review state before cited units appear in the paper.

---

## 5. Work packages to make it publishable

### WP1 — Complete the normative spine

**Goal:** every one of the ten principles has either a verified patristic anchor or an explicit abstention rationale.

Tasks:

1. Map the 41 corpus units to the ten principles using `principle_ids`; list gaps.
2. For each principle, populate `policy/rules.json` `patristic` entries with author, work, locus, quote, rights status, and review status.
3. Verify every quotation against `corpus/units.db`; record the unit id and hash.
4. Resolve `u-lat-003`; do not leave a null text in the cited set.
5. Editorial review of each cited unit: edition, translator, licence, locus, and review state.
6. Write a short editorial method section for the paper: inclusion, exclusion, rights, disagreement, and abstention.

**Acceptance:**

- 10/10 principles have a verified anchor or an explicit "no anchor; abstain" rationale.
- No cited unit is `draft-unreviewed`.
- The corpus and policy are frozen with hashes.
- The editorial method is reproducible from the repository.

### WP2 — Freeze the paper artifact

**Goal:** a reviewer can reproduce the paper's artifact.

Tasks:

1. Tag a version, for example `pea-0.1-paper`.
2. Record SHA-256 hashes for `corpus/seed.jsonl`, `corpus/units.db`, `policy/rules.json`, `policy/constitution.md`, `eval/scenarios.jsonl`, and `eval/rubric.md`.
3. Add a `scripts/reproduce_paper.sh` that builds the corpus, validates the policy, and runs the evaluation.
4. Record host versions and adapter states.
5. Add a data-availability statement to the paper.

**Acceptance:**

- A fresh checkout reproduces the corpus database and the evaluation run.
- The README distinguishes the paper artifact from a qualified release.

### WP3 — Technical evaluation

**Goal:** a results table that is honest about what was measured.

Tasks:

1. Run the deterministic policy over the 32 scenarios; record verdict distribution.
2. Measure quote verification: exact, fuzzy, context-window, and failure counts.
3. Measure policy determinism: repeated runs produce identical verdicts and citations.
4. Measure latency p50/p95 for assessment.
5. Measure refusal recall and false intervention against the authored labels; report the label author and date.
6. If a real backend is stable, run the four conditions in `eval/compare.py`; if not, report the limitation and do not use `fake` for semantic claims.
7. Preserve every failure case in an appendix or repository artifact.

**Acceptance:**

- A results table with N, backend/model, date, and limitations.
- Zero fabricated or modified-as-verbatim quotes.
- All failures listed, not hidden.

### WP4 — Expert review

**Goal:** a small, defensible human evaluation without overclaiming.

Tasks:

1. Recruit two or three reviewers: one patristic/content reviewer, one care/tone reviewer, and optionally one HCI/ethics reviewer.
2. Use the five-dimension rubric and the 32 scenarios.
3. Record consent and any ethics-review requirement.
4. Ingest grades with `eval/grade.py`; preserve disagreement; do not average away genuine interpretive differences.
5. Report per-dimension scores, disagreement, and the limits of a small expert sample.

**Acceptance:**

- Two independent reviewers complete the rubric.
- Disagreement is recorded per case.
- The paper calls this an expert review, not a user study or a holdout.

### WP5 — Draft the paper

**Goal:** a complete manuscript with every claim bounded.

Tasks:

1. Write the introduction around the refusal-action gap and the inspectability problem.
2. Write the related work without claiming a literature gap that was not systematically reviewed.
3. Describe the system with figures and a reproducibility appendix.
4. Describe the normative corpus and the editorial method.
5. Report the technical evaluation and expert review.
6. Discuss moral absolutism, conditional compliance, and authority provenance.
7. Write the limitations, positionality, and ethics statement.
8. Check every patristic quotation against the corpus; check every empirical claim against a result or citation.

**Acceptance:**

- 8,000–10,000 words.
- Every patristic quotation has work, locus, edition, translation, and licence.
- No "first", "consensus", "neutral", or "proves" claims.
- The abstract states the design/feasibility boundary.

### WP6 — Submit

**Goal:** a clean submission and a fallback path.

Tasks:

1. Submit to *Ethics and Information Technology* first.
2. Prepare a cover letter that states the contribution and the case-study framing.
3. Check the journal's preprint and data-availability policies.
4. If desk-rejected, revise for *AI & Society*, then *AI and Ethics*.
5. Deposit a preprint only after checking the journal policy.

**Acceptance:**

- Submission checklist complete.
- Artifact link and data-availability statement included.
- No journal submitted to simultaneously.

---

## 6. Venue fit

| Venue | Type | Fit | Why |
|---|---|---|---|
| *Ethics and Information Technology* (Springer) | Journal | Best | Published "Pastoral AI ethics for chatbots in religious education" (2026, DOI 10.1007/s10676-026-09924-y) and "Designing responsible agents" (2025, DOI 10.1007/s10676-025-09820-x); scope covers machine ethics, value alignment, and ethical design |
| *AI & Society* (Springer) | Journal | Strong | Broader sociotechnical framing; human-centered and societal implications; good fallback |
| *AI and Ethics* (Springer) | Journal | Good | Applied ethics; broad scope; newer journal; realistic fallback |
| *Science and Engineering Ethics* (Springer) | Journal | Good if engineering framing | Responsible innovation, design, accountability; less religious |
| *IEEE Transactions on Technology and Society* | Journal | Possible | Systems and society; IEEE format; engineering audience |
| *Minds and Machines* (Springer) | Journal | Philosophical only | Needs a conceptual paper; the system alone is out of scope |
| AIES 2027 | Conference | Demo or extended abstract now | Feedback venue; full paper after stronger evaluation |
| FAccT 2027 | Conference | Strong theme, weak evidence | Accountability and auditability fit; needs a human study or stronger empirical work |
| CHI/CSCW 2028 | Conference | Best after HRAI studies | Human study required; this is the second paper |
| *Studies in Christian Ethics* / *Journal of Moral Theology* / *Zygon* | Journal | Separate theological paper | Needs deeper patristic argument, not a system description |

Do not target NeurIPS, ICML, or ACL: the contribution is not a model, benchmark, or learning method. Do not target *Nature Machine Intelligence*: the evidence is too preliminary.

---

## 7. Timeline

| Phase | Work | Output |
|---|---|---|
| Weeks 1–3 | WP1: normative spine and editorial review | 10/10 principles anchored or explicitly abstained; corpus reviewed |
| Weeks 3–4 | WP2: artifact freeze | tag, hashes, reproduction script |
| Weeks 4–5 | WP3: technical evaluation | results table and failure appendix |
| Weeks 5–6 | WP4: expert review | per-dimension grades and disagreement record |
| Weeks 6–8 | WP5: draft | 8,000–10,000-word manuscript |
| Week 9 | WP6: submit | EIT submission and fallback plan |
| 2027 | HRAI studies | verification, abstention, conformance; CHI/CSCW/FAccT |
| 2027–28 | Theology paper | after corpus expansion and deeper patristic argument |

The timeline is relative. The owner may extend WP1; the paper should not be submitted before the cited corpus is reviewed.

---

## 8. Risks and kill criteria

| Risk | Mitigation | Kill criterion |
|---|---|---|
| The corpus is too thin for a patristic claim | Reframe as a methods paper with a smaller verified corpus; expand the Syriac lane | If fewer than six principles can be anchored, do not call it a patristic ethics layer |
| The policy's patristic fields remain evidence gaps | WP1 is the first gate; do not draft around the gap | If the anchors cannot be populated, submit a design paper about provenance, not patristic ethics |
| The backend is unstable | Report deterministic policy metrics and expert review; state the limitation | If no real semantic evaluation is possible, do not claim model quality |
| Expert reviewers cannot be recruited | Use two reviewers; report the small sample honestly | If no independent review exists, submit as a design paper without a human-evaluation claim |
| Moral absolutism critique | Declared scope, opt-in, disclosure, abstention, disagreement | If the paper cannot answer the critique, do not submit to an ethics journal |
| Overclaiming | Use the claim boundary in §1; check every sentence | Any "first", "consensus", "neutral", or "proves" claim blocks submission |

---

## 9. What not to claim

- "The first patristic ethics layer" — the prior-art review supports "we found no patristic-grounded runtime layer in the reviewed landscape (Oct 2026)", not "first".
- "The patristic tradition" — the corpus has six author strings and 41 units; say "a declared, editorially bounded seed corpus".
- "Consensus" — the design surfaces disagreement; no consensus is computed.
- "Pre-registered" — no registry record exists; say "pre-specified in the design document".
- "Improves moral behaviour" — no human study exists.
- "Qualified release" — the README says it is not.
- "Neutral" — the layer is confessional by design; neutrality is not the claim.

---

## 10. References

- Dicastery for the Doctrine of the Faith and Dicastery for Culture and Education. *Antiqua et Nova*. 28 Jan 2025.
- Pope Leo XIV. *Magnifica Humanitas*. 15 May 2026.
- Skytland, N. et al. "Evaluating Artificial Intelligence Through a Christian Understanding of Human Flourishing." arXiv:2604.03356, 2026.
- Chao, A. "When AI Is Your Pastor." arXiv:2608.12324, 2026.
- Wingate, D. et al. "Omissive Bias in Religious Representation." arXiv:2605.24319, 2026.
- Yu, S., Carroll, F., and Bentley, B. L. "When Saying 'No' Is Not Enough." FAccT 2026. DOI 10.1145/3805689.3812378.
- Ojewale, V. and Venkatasubramanian, S. "Designing for Doubt." AIES 2026. DOI 10.1609/aies.v9i3.43281.
- Wen, B. et al. "Know Your Limits: A Survey of Abstention in Large Language Models." *TACL* 13 (2025): 529–556.
- Yu, M.-Y., Kim, T., and Choi, J. W. "NOMOS: Compiling Written Policies into Statically Verified Tool-Call Gates for LLM Agents." arXiv:2610.11030, 2026.
- Sorensen, T. et al. "A Roadmap to Pluralistic Alignment." ICML 2024. arXiv:2402.05070.
- Varshney, K. R. "Decolonial AI Alignment." AIES 2024. DOI 10.1609/aies.v7i1.31739.
- Conwill, L. et al. "Design Patterns for the Common Good." CHI 2025. DOI 10.1145/3706598.3713546.
- Papakostas, C. "Pastoral AI ethics for chatbots in religious education." *Ethics and Information Technology*, 2026. DOI 10.1007/s10676-026-09924-y.
- Gudmunsen, Z. "Designing responsible agents." *Ethics and Information Technology*, 2025. DOI 10.1007/s10676-025-09820-x.

# Patristic Ethic Agent (PEA) — Design

**Date:** 2026-10-05
**Status:** decisions locked with user; implementation plan: `docs/plans/2026-10-05-patristic-ethic-agent-plan.md`
**Supersedes:** nothing — extends `docs/plans/2026-10-04-patristic-ethics-mcp.md` (kept as reference) with corpus-verified amendments.

---

## 1. Goal

A runtime ethics layer — a "conscience" for coding agents (OpenCode, Claude Code, Codex, any MCP host) — whose normative authority is the **pre-schism patristic tradition** (Greek, Latin, Syriac Fathers). It adjudicates both **user dialogue** and **agent tool calls**, returns `allow | flag | gate_to_human | abstain` with inspected citations, and never silently imposes its ethic.

Non-goals: no pretraining (Tier 3), no fine-tuning in v1 (Tier 2 only behind a measured gate), no safety/security scope (quarantined in `source/_out-of-scope/`), no factual-assistant role.

## 2. Locked decisions (user, 2026-10-05)

| Decision | Choice |
|---|---|
| Build scope now | Design + plan docs only (this session); code execution next |
| Enforcement | **Both** explicit tools + optional transparent proxy (same adjudicator) |
| Confessional framing | **Pre-schism patristic consensus** (Greek + Latin + Syriac, before 1054); surface East/West disagreement, never collapse it |
| Judgment target | **Both** dialogue ethics and tool-call actions |
| Corpus languages | **Greek + Latin + English + Syriac** (~1.3 GB verified seed) |

## 3. Evidence base (corpus-verified)

All 108 PDFs read 2026-10-05 (5 recon lanes). The load-bearing findings that shape this design:

| # | Finding | Source | Consequence |
|---|---|---|---|
| E1 | Written principles change behavior ≈ 0 (63 students, 105 devs, no significant effect); prompted LMs are no harder to red-team than plain | 1903.03425; 1906.06668; 2209.07858 | The **mechanical gate**, not prompt text, is the product |
| E2 | Structured harness: +3.96 avg, +10.8 escalation (85.9→96.7), +5.14 robustness; `missed_escalation` top raw failure; perspective-compare **−1.86** | 2608.12324 | Escalation is priority #1; **never default to comparison** |
| E3 | Models omit religion where relevant: mean relevance 0.084 vs human ~3/5; r=0.257 | 2605.24319 | **Mention-recall floor** as a first-class metric |
| E4 | Models over-align to "religious-sounding" justifications (~75% Western; immoral act judged moral if framed religious) | 2311.07792 | Verify **source *and context***; a valid quote can launder an immoral act |
| E5 | No hard-coded fairness axiom: formal parity/equalized-odds rules are Pareto-dominated | 1808.00023 Thm 9/10/17; 1104.3913; 1610.02413 | Contested cases → `gate_to_human`; never invent a similarity metric |
| E6 | Aggregator licence labels wrong 66% of the time; >1% of unprompted LM output is verbatim memorized (10× cut by dedup); quoting does not cure infringement | 2310.16787; acl-dedup; 2303.15715 | PD-only ingest, per-source verification, quote caps, chunk dedup, attribution in every output |
| E7 | Frontier models default to "Procedural Secularism"; Faith/Spirituality −31; failure is policy-framing, not data | 2604.03356 | Runtime selection of the tradition is the correct, cheap intervention point |
| E8 | KL-RLHF collapses minority preferences toward 0%/100% even with an oracle reward | 2405.16455 | Do not delegate the ethic to base-model "alignment"; select explicitly at runtime (and later, never via pretraining) |
| E9 | Tuned variants cut ethical entropy ~80%; drift is measurable (γ_eff=0.012 nats/step) | 2512.03047 | Drift monitor is Phase E; anchored retrieval resists context drift |
| E10 | A runtime constitutional/RAG gate is *conditional* compliance, not internalized belief | 2602.16987; 2102.09364 | Disclose the claim level honestly; measure with the harness, don't oversell |

**Unresolved tensions to log (not fiated):** fairness mechanisms vs impossibility (E5); constitution-first vs principles-do-nothing (E1); prompt-controllability vs context-fragility; runtime gate vs Simulation-Theology critique (E10); moral-absolutism critique vs a canonical spine (declared, opt-in, bounded is the mitigation).

## 4. Architecture

PDP/PEP split, adapted from AGT / preloop / mcp-context-protector (see `docs/REFERENCES_SECURITY_RUNTIME_LAYERS.md` §4–5):

```
MCP host (OpenCode / Claude Code / Codex)
  │ stdio JSON-RPC
  ▼
PEA MCP server (PEP)            modes: explicit | transparent proxy
  ├─ tools: check_action, search_corpus, get_passage, cite_father, ethics_gate_release
  ├─ resources: constitution.md, disclosure, citation-spine (read-only)
  └─ call_tool() ──► adjudicate()  (PDP, pure, no I/O)
        ├─ retriever: patristic loci (FTS5 + optional sqlite-vec)
        ├─ quote_verify: exact → fuzzy → context window
        ├─ policy: policy.yaml (first-match, deterministic) + escalation table
        └─ verdict: allow | flag | gate_to_human | abstain
                      + citations[{source, locus, quote, sha256, edition, license}]
                      + reasoning_trace + guidance (+ disclosure, always)
        └─ gate: pending JSON (RLock + atomic rename) → human release executes once
  audit: append-only JSONL (correlation_id, action, verdict, citations, identity_hash, ts)
```

Mode semantics:
- **Explicit**: agent calls the five tools directly. Lower enforcement, full utility.
- **Proxy**: PEA sits in front of a downstream stdio MCP server; *every* `tools/call` is adjudicated before forwarding. `gate_to_human` issues **zero** downstream calls until `ethics_gate_release`.

Judgment targets: `check_action(action, context, goal, target_kind="dialogue"|"tool")`. Dialogue verdicts carry `guidance` (exhortation text per instruction.md); tool verdicts carry `decision` only.

## 5. Verdict policy (deterministic, escalation-first)

| Order | Condition | Verdict |
|---|---|---|
| 1 | Self-harm/suicide, harm to others, abuse, severe distress, scrupulosity/despair, legal/medical/emergency | `gate_to_human` (+ crisis line, + pastoral exhortation with citations) |
| 2 | Dialogue intent to commit grave sin (murder, rape, Gal. 5 vices) | `flag` (+ exhortation template, citations; never "you are right") |
| 3 | Tool action violating a policy redline | `gate_to_human`; lesser concerns `flag` |
| 4 | Grounded + consistent loci | `allow` |
| 5 | Grounded but Fathers in tension / low confidence | `flag` (surface disagreement) |
| 6 | No grounding, or quote fails verification | `abstain` ("the Fathers do not address this") |

Never: simulate a Father's voice; claim universal morality; default to cross-tradition comparison; emit restricted-licence text; accept a quote that fails source+context verification.

## 6. Normative source & disclosure

Constitution (`policy/constitution.md`) is **small and high-authority**: Ten Commandments, Christ's two commandments (Mt 22:37–40), the Gal. 5 vice/virtue lists, patristic triage (primary doctrine / secondary / tertiary / pastoral), escalation duties, abstention rules, disclosure text. Not a taxonomy dump.

Mandatory disclosure on every non-allow output, verbatim:

> *Grounded in the pre-schism patristic tradition (Greek, Latin, and Syriac Fathers); this is one interpretive tradition, not a universal morality. Advisory only; contested or high-stakes cases escalate to a human.*

## 7. Corpus & citation spine

Verified seed (live-checked 2026-10-05; full commands in plan Task A.3):

| Source | Content | Licence | Size |
|---|---|---|---|
| PTA `pta_data` (branch `public`) | TEI XML, CTS URNs, Greek/Latin/Syriac | per-file CC | ~124 MB |
| CCEL ANF/NPNF (Schaff) | PD English Fathers, plain text | PD | ~30 MB |
| First1KGreek | TEI Greek | CC BY-SA 4.0 | (subset) |
| ETCBC peshitta + syrnt | Syriac OT/NT, Text-Fabric | MIT | ~15 MB |
| PD Bibles (sparse) | Vulgate/KJV/WEB/Brenton | PD/MIT/CC0 | small |

**Spine pivot:** no open bulk CPG/CPL dataset exists (Brepols/Peeters proprietary). Primary key = **CTS URNs** (PTA carries them) + GND/Wikidata; CPG/CPL stored as optional metadata only. Licence tiers: `pd | cc0 | cc-by | cc-by-sa | restricted-metadata-only`; retrieval never emits `restricted-metadata-only`; modern critical editions are citation-only metadata, never ingested; apparatus excluded (`apparatus_included: false` assertion per edition).

Per-chunk mandatory metadata: `source_id, author, work, locus, cts_urn, edition, translator, licence_tier, attribution_text, retrieval_date, chunk_hash, duplicate_cluster_id`.

## 8. Invariants (the runnable safety story)

1. Every emitted quote is an exact/near-exact substring of a stored chunk **and** passes the context check.
2. No `restricted-metadata-only` chunk is ever emitted.
3. A `gate_to_human` verdict issues no downstream `tools/call` until release after human approval.
4. Every non-`allow` output carries the disclosure; every verdict appends exactly one audit record.

## 9. Evaluation (Phase D)

~120 authored scenarios in FMG-Bench triage shape; 4 conditions (`raw`, `guided`, `guided_rag`, `compare` as negative control); metrics: FAI-C-ST 7-dim geometric mean + tangential integration, mention-recall floor, quote-fidelity pass rate + 21-tag failure distribution, escalation appropriateness, robustness perturbations, RAG exclusion test, multi-axis trustworthiness battery. Gate: `guided_rag > raw` on quality+escalation; `compare ≤ guided_rag`.

## 10. Risks (carried from 2026-10-04 plan, updated)

1. Moral absolutism → mitigated by declared scope, opt-in, disclosure, abstention, surfaced disagreement.
2. Ethics washing (2102.09364) → the layer must be measured by D's harness, never assumed.
3. Conditional compliance (2602.16987) → disclosed; PEA claims enforcement, not formation.
4. Licence contamination → per-source verification, PD-only text.
5. Omissive bias → mention-recall floor.
6. Syriac tooling gap → expect hand-built ingest; smallest lane.
7. Scope creep into safety → `_out-of-scope/` stays quarantined.

## 11. Open questions (deferred, non-blocking)

- Public name/branding and PyPI name (working name: `patristic-ethic-agent`, package `patristic_ethics`).
- Crisis-resource list: default global line vs per-region config (v1: one configurable line in `policy/crisis.yaml`).
- Whether proxy mode ships in `mcp.json`/host examples per host (OpenCode config example in README).

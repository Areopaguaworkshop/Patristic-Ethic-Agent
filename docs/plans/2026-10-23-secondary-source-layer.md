# PEA secondary-source layer — plan

Date: 2026-10-23
Status: superseded on 2026-10-23. The owner clarified that secondary sources are for further reading only, not interpretation or direct quotation. See [the further-reading bibliography plan](2026-10-23-further-reading-bibliography.md).

> Historical note: this document records the earlier secondary-interpretation proposal. Do not implement its quotation or interpretation layer.

## 1. Why this layer exists

The current corpus was reviewed from primary editions. The owner's instruction changes the method:

1. Add a layer of secondary sources first.
2. Use secondary sources to identify the primary passages.
3. When quoting, quote the primary text and the related secondary interpretation.
4. Keep both the CTS URN and the CSL-JSON citation.
5. Use English-language sources primarily.
6. Defer the Syriac and Latin reviews until this layer is stable.

A secondary source is not decoration. It records how modern scholarship identifies, edits, translates, and interprets the primary text. The runtime must show that distinction.

## 2. Current state

| Area | Status |
|---|---|
| English primary units | 19 reviewed |
| Greek primary units | 14 approved on 2026-10-23 at the primary-text layer |
| Syriac primary units | 5 draft-unreviewed; review deferred |
| Latin primary units | 3 draft-unreviewed; review deferred |
| Modern government lane | 3 CSL records reviewed |
| Scripture lane | 6 CSL records reviewed |
| Provenance | 4 CSL records (catalogues and editions), no independent secondary literature |
| Secondary-source registry | absent |
| Runtime primary + secondary rendering | absent |
| Offline test suite at plan time | 551 passed, 10 skipped |

The Greek approval covers the primary text, attribution, edition, rights, principle mapping, and draft application notes. It does not cover a secondary-source interpretation. The new layer may require a second review pass.

## 3. Source chain

```text
modern English secondary source
  -> identifies or interprets a primary passage
  -> primary text (CTS URN + CSL-JSON citation)
  -> exact primary quotation + labelled secondary interpretation
  -> runtime guidance with separate source labels
```

Rules:

- Every reviewed primary unit links to at least one secondary source or records an explicit exception.
- Primary quotations remain verbatim and hash-checked.
- Secondary quotations are exact and page-located; paraphrases are labelled as paraphrases.
- Secondary text is never presented as a primary quotation.
- Disagreement between secondary sources is preserved, not averaged into consensus.
- The secondary source does not replace the primary text; it accompanies it.

## 4. Data model

### 4.1 Primary citations — keep both identifiers

- The seed keeps `cts_urn`, `edition`, `translator`, `source_url`, `rights_status`, and `text_sha256`.
- Add `corpus/primary_citations.jsonl`: one CSL-JSON record per primary unit, linked by `custom.unit_id`.
- `custom.cts_urn` repeats the CTS URN where one exists.
- Greek units keep the CTS URN and gain a CSL record.
- English units have no CTS URN; their CSL record carries the source URL, edition, translator, and locus.
- The runtime citation returns both the CTS URN (when present) and the CSL citation.

### 4.2 Secondary sources

Add `corpus/secondary.jsonl`: one CSL-JSON record per secondary source.

Required `custom` fields:

- `source_class`: `secondary_scholarship`
- `citation_index`: a stable string, e.g. `SEC-QUASTEN-1983`
- `linked_unit_ids`: primary units this source identifies or interprets
- `role`: `discovery`, `interpretation`, or `reference`
- `quote`: the exact secondary passage used
- `quote_locus`: page, section, or chapter
- `quote_sha256`: hash of the stored secondary quote
- `rights_status` and `rights_evidence`
- `review_status`: `draft-unreviewed` or `reviewed`
- `verification_method`

### 4.3 Provenance

`corpus/provenance.jsonl` keeps catalogues and editions. Secondary literature lives in `secondary.jsonl`. Both link to primary unit IDs, so the chain is:

`secondary.jsonl -> provenance.jsonl -> seed.jsonl`

### 4.4 Runtime labels

| Source | `source_class` | Identifier |
|---|---|---|
| Patristic primary | `patristic_primary` | CTS URN + CSL |
| Modern scholarship | `secondary_scholarship` | CSL |
| Modern government | `modern_government` | CSL |
| Scripture | `scripture` | CSL |

### 4.5 Databases

- `corpus/primary_citations.db`
- `corpus/secondary.db`

Keep them separate from `units.db`, `modern.db`, and `scripture.db`. A single citation database is possible, but separate databases make cross-lane mixing harder.

## 5. Review protocol

### 5.1 What counts as a secondary source

Eligible:

- Peer-reviewed monographs and journal articles.
- Standard reference works (for example CPG, CPL, Oxford/Cambridge handbooks, patrology handbooks).
- Scholarly commentaries.
- Translator introductions and notes in critical editions.

Not eligible without explicit justification:

- Unsourced web pages, blogs, and AI-generated summaries.
- A primary edition's own text presented as secondary interpretation.
- A commercial study with no stable bibliographic identity.

### 5.2 Rights

- Prefer open-access or public-domain secondary sources.
- For copyrighted works, record the exact page and use only a short quotation that qualifies as fair use, or paraphrase and label it.
- Do not store long copyrighted excerpts.
- Record the rights basis for every secondary record.

### 5.3 Per-unit checks

- The secondary source identifies the primary work and passage.
- The edition and locus are correct.
- The secondary quote is exact and page-located.
- The record states whether the source supports, disputes, or contextualizes the primary application.
- The application cannot encourage victim-blaming, unsafe reconciliation, or self-punishment.
- The source is English-language when an English source is adequate.
- A disputed interpretation stays disputed.

## 6. Phases

### Phase 0 — Approve this plan

Owner reviews the scope, data model, and review rules. No code.

### Phase 1 — Schema and validators

Add CSL-JSON validators for primary citations and secondary sources; add link-integrity checks. No runtime retrieval changes yet.

### Phase 2 — English secondary seed

Select 10–15 English secondary sources for the 19 English primary units. Target one source per unit, two for disputed units. Record CSL metadata, exact quotes, page loci, rights, and links.

### Phase 3 — Primary CSL citations

Add CSL primary citations for the 19 English and 14 Greek units. Keep every existing CTS URN. Verify that the CSL record and seed unit point to the same text and source.

### Phase 4 — Runtime rendering

Return primary and secondary citations as separate labelled items. Add output checks that reject secondary text presented as a primary quotation. Add tests for the labels and the link chain.

### Phase 5 — Owner review

Review the secondary records and their links. Mark records `reviewed` only after explicit owner decisions. Preserve disagreements.

### Phase 6 — Re-review Greek and English units

Re-open the primary applications where a secondary source changes the interpretation. Update notes. The primary-text approval stands; the interpretation layer may add qualifications.

### Phase 7 — Resume Syriac and Latin

Start those reviews only after the English-first secondary layer passes its acceptance checks.

### Phase 8 — Evaluation and release evidence

Run the evaluation harness and release-gate checks against the new citation model. Update the experimental profile and snapshot after the review cycle.

## 7. Acceptance criteria

- Every reviewed primary unit has at least one linked secondary source or a documented exception.
- Every secondary record has CSL-JSON metadata, an exact quote, a page locus, rights evidence, and a review status.
- Primary and secondary citations are labelled separately at runtime.
- No secondary text is presented as a primary quotation.
- All secondary records are owner-reviewed before runtime use.
- The 19 English and 14 Greek primary units retain their CTS URN or source-locus identifiers.
- Syriac and Latin remain draft-unreviewed and deferred.
- The full offline suite and all corpus validators pass.

## 8. Open decisions

1. Minimum secondary sources per primary unit: one, or two for disputed units?
2. Should runtime guidance quote secondary sources verbatim, paraphrase them, or both?
3. Should `secondary.jsonl` and `primary_citations.jsonl` be separate lanes or one citation database with labels?
4. Which English source types come first: handbooks and patrology, peer-reviewed articles, commentaries, or translation introductions?
5. What rights policy should apply to copyrighted secondary quotations?
6. Should the Greek and English primary approvals be re-opened after the secondary review?

## 9. Non-goals

- No Syriac or Latin review in this phase.
- No new primary-source ingestion.
- No model training.
- No runtime code until the owner approves this plan.
- No claim that a secondary source is consensus or church teaching.

## 10. Verification plan

Planned commands, to be implemented after approval:

```sh
.venv/bin/python -m patristic_ethics.cli corpus validate-primary-citations corpus/primary_citations.jsonl --seed corpus/seed.jsonl
.venv/bin/python -m patristic_ethics.cli corpus validate-secondary corpus/secondary.jsonl --seed corpus/seed.jsonl
.venv/bin/python -m patristic_ethics.cli corpus validate-provenance corpus/provenance.jsonl --seed corpus/seed.jsonl
.venv/bin/python -m pytest -q
```

Checks:

- Every linked unit ID exists.
- Every reviewed primary unit has a secondary link or exception.
- Every secondary quote hash matches the stored quote.
- Runtime citations carry the correct `source_class`.
- No secondary quote passes as a primary quote.

## 11. Risks

| Risk | Mitigation |
|---|---|
| Copyright exposure from modern scholarship | Prefer open access; short fair-use quotes or paraphrase; record rights evidence |
| Secondary-source bias | Preserve disagreements; require explicit interpretation notes |
| Scope growth into a bibliography project | English-first, one source per unit, fixed batches |
| Primary approvals need revision | Keep primary and interpretation review states separate |
| Conflation of primary and secondary text | Separate labels, separate databases, output checks |
| Slower delivery | Ship the schema and a small English pilot first |

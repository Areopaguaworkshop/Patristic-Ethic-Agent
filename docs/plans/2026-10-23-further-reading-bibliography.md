# PEA further-reading bibliography — plan

Date: 2026-10-23
Status: Phase 2 delivered on 2026-10-23: 145 draft-unreviewed records imported to `corpus/further_reading.jsonl`. Owner review is pending.
Supersedes: [the secondary-source layer plan](2026-10-23-secondary-source-layer.md).

## 1. Scope

The owner clarified the source policy:

- Secondary sources are **not** interpretations for runtime guidance.
- Secondary sources are **not** quoted in ethical responses.
- Secondary sources form a **further-reading bibliography** for ethical principles.
- Another agent is collecting the secondary sources about Patristic Ethics.
- PEA will ingest, validate, and display that bibliography.
- Primary texts remain the only quoted sources.
- CTS URN and CSL-JSON citations remain for primary texts.

## 2. Current state

| Area | Status |
|---|---|
| Reviewed primary units | 33 of 41: 19 English, 14 Greek |
| Deferred units | 5 Syriac, 3 Latin |
| Primary CSL citations | 33 records; CTS URN retained |
| Provenance records | 4 Greek catalogue/edition records |
| Modern government lane | 3 records |
| Scripture lane | 6 records |
| Pilot reference records | 8 author-level records in `corpus/secondary.jsonl`; now out of scope as interpretations |
| Further-reading layer | 145 draft-unreviewed records in `corpus/further_reading.jsonl` |
| Offline test suite at plan time | 557 passed, 10 skipped |

The eight pilot records are not the other agent's bibliography. Keep them as a pilot until the owner decides whether to convert or discard them.

## 3. Data model

### 3.1 File

Add `corpus/further_reading.jsonl`: one CSL-JSON object per source.

Required CSL fields:

- `id`
- `type`
- `title`
- `author` or `editor`
- `issued`
- `publisher` where applicable
- `URL`, `DOI`, or `ISBN`
- `language`

Required `custom` fields:

- `source_class`: `further_reading`
- `principle_ids`: one or more PEA principle IDs (`PEA-P01`–`PEA-P10`)
- `review_status`: `draft-unreviewed` or `reviewed`
- `rights_status` and `rights_evidence`
- `verification_method`

Optional `custom` fields:

- `linked_unit_ids`: primary units the source is especially relevant to
- `note`: a short reading note, not an interpretation
- `access`: `open-access`, `library`, `purchase`, or `unknown`

No `quote`, `quote_sha256`, or `role` field is required. The bibliography does not supply runtime quotations.

### 3.2 Display

- CLI: `pea further-reading --principle PEA-P01` prints the bibliography for one principle.
- Optional MCP tool: `further_reading(principle_id)` returns the same records.
- Documentation: a generated `docs/further-reading.md` grouped by principle.
- The runtime ethical guidance does not insert bibliography text unless the owner explicitly asks for a "further reading" section.

### 3.3 Labels

| Layer | `source_class` | Use |
|---|---|---|
| Patristic primary | `patristic_primary` | Quoted in guidance |
| Modern government | `modern_government` | Quoted with label |
| Scripture | `scripture` | Quoted with label |
| Further reading | `further_reading` | Listed, never quoted as guidance |

## 4. Import from the other agent

The collecting agent may deliver JSONL, CSV, or Markdown. The preferred format is JSONL with CSL fields and PEA fields.

Minimum columns for CSV or Markdown conversion:

- title
- authors
- year
- publisher
- type
- URL, DOI, or ISBN
- principle IDs
- note
- rights or access

The coding agent will:

- validate CSL shape and principle IDs;
- assign stable IDs where needed;
- reject duplicates and unknown principles;
- record missing rights/access explicitly;
- never invent metadata or quotations.

The owner must confirm the delivery path and format before import.

## 5. Review protocol

For each record:

- Confirm author, title, year, publisher, and identifier.
- Confirm the principle mapping.
- Confirm rights or access.
- Decide whether the note is descriptive or interpretive. Interpretive notes are out of scope.
- Mark the record `reviewed` only after an explicit owner decision.

Further reading is not patristic evidence, not consensus, and not a source of quotations.

## 6. Phases

### Phase 0 — Approve this revised plan

Owner confirms the bibliography-only scope and the import format. No code.

### Phase 1 — Schema and validator

Add the further-reading loader and validator; check CSL shape, principle IDs, duplicates, rights evidence, and review state. Add tests.

### Phase 2 — Import the collecting agent's bibliography

Ingest the delivered file, map principles, deduplicate, and preserve missing fields as explicit gaps.

### Phase 3 — Owner review

Owner reviews the records and marks approved entries. No entry is used before review.

### Phase 4 — Display

Add the CLI listing and optional Markdown export. Add an MCP tool only if the owner wants it.

### Phase 5 — Documentation and snapshot

Update README and the experimental profile. Do not claim the bibliography is a source of ethical guidance.

### Phase 6 — Resume Syriac and Latin

Still deferred. The bibliography layer does not unblock those reviews.

## 7. Acceptance criteria

- Every principle has a further-reading list or an explicit gap.
- Every record has CSL metadata, principle IDs, rights/access, and review state.
- No further-reading quotation enters runtime guidance.
- No further-reading record is presented as patristic evidence.
- Only owner-reviewed records are displayed as approved.
- Syriac and Latin remain draft-unreviewed and deferred.
- Validators and the full offline suite pass.

## 8. Open decisions

1. Delivery format from the collecting agent: JSONL, CSV, Markdown, or a shared path.
2. Minimum number of sources per principle.
3. Where to display the bibliography: CLI, MCP, documentation, or all three.
4. Whether to convert, keep, or discard the eight pilot reference records.
5. Rights policy for copyrighted books: cite metadata only, or also link to a library record.

## 9. Implementation progress

| Item | Status |
|---|---|
| Schema and validator | implemented in `src/patristic_ethics/further_reading.py` |
| CLI listing | `pea further-reading --principle PEA-P01` |
| Markdown export | `pea further-reading --format markdown` |
| Documentation | `docs/further-reading.md` |
| Example record | `corpus/further_reading.example.jsonl` (not real bibliography) |
| Real bibliography import | 145 records imported 2026-10-23; owner review pending |
| Import quality | 75 DOI records; 70 URL-only; 28 Google Scholar leads; 0 ISBN; 58 unknown-rights records |
| Evidence re-verification | 76 verified; 40 lead-only; 16 blocked; 4 PDF unchecked; 9 metadata issues |
| Owner decision on flags | keep all 145 records; show verification flags; no deletion |
| Owner decision on DOI errors | corrected fr-0042 and fr-0057; nine partials keep local metadata |
| Owner decision on leads | 40 lead-only records approved as a discovery list; still flagged |
| Owner decision on verified records | 76 verified records accepted without spot check and marked reviewed; 69 remain draft |
| Visible flags | CLI and `docs/further-reading.md` show verified, LEAD ONLY, NEEDS REVIEW, blocked, PDF unchecked |
| Owner review | pending |
| Tests | `tests/test_further_reading.py` |

The canonical file now holds 145 draft-unreviewed records imported on
2026-10-23. The example file remains only to exercise the validator and CLI.
The owner review is the next gate.

## 10. Non-goals

- No secondary-source interpretation.
- No secondary-source quotation in guidance.
- No change to primary quotations.
- No Syriac or Latin review in this phase.
- No claim that further reading is church teaching or consensus.

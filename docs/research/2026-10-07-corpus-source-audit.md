# Corpus source audit — 2026-10-07

The seed now contains 41 units: 40 source-verified texts and one null OCR placeholder. Every unit remains draft-unreviewed. Verification of text and provenance does not approve its principle mapping or contemporary application. M1 remains partial.

## Corrections

- u-en-004 and u-en-005: Homily XI opens on Matthew 3:7, not Matthew 5:33. The virtue-list excerpts occur in §9. [Source](https://www.ccel.org/ccel/schaff/npnf110.iii.XI.html).
- u-en-006: Homily VII opens on Matthew 2:4–5, not Matthew 5:1–2. Its quotation of Matthew 5:28 later in the homily is distinct from the opening text. A note now identifies the theatrical-spectacle polemic and its limits as evidence for modern consent. [Source](https://www.ccel.org/ccel/schaff/npnf110.iii.VII.html).

## Additions

| Unit | Source | Draft application |
|---|---|---|
| u-en-007 | [Homily XVII, §2](https://www.ccel.org/ccel/schaff/npnf110.iii.XVII.html) | Deliberate cultivation of desire; no claim to read hidden intent or define consent |
| u-en-008 | [Homily LII, §4](https://www.ccel.org/ccel/schaff/npnf110.iii.LII.html) | Generosity and covetousness; translated text excludes the Greek editorial footnote |
| u-en-009 | [Homily LXXV, §4](https://www.ccel.org/ccel/schaff/npnf110.iii.LXXV.html) | Reconciliation and hatred; cannot justify pressure to resume unsafe contact |

These reuse the existing NPNF First Series volume 10 source record and its public-domain XML header evidence. The [CCEL copyright policy](https://www.ccel.org/about/copyright.html) distinguishes underlying public-domain works from copyrighted online additions and notes jurisdictional differences. Source verification here covers the historical translated excerpts, not a blanket licence for all CCEL material.

## Remaining acceptance

Expand toward 40–60 verified units while preserving the original-language lanes; avoid duplicate fragments merely to meet the count. Owner review must assess attribution, edition and rights evidence, principle mappings, historical context, and pastoral application. P03 remains an explicit modern-application evidence gap.

## Validation

Corpus validation: `OK: 22 units`. Corpus/CLI tests: 36 passed. A fresh SQLite build resolves and verifies the full stored quotation of each addition; all three retain draft-unreviewed status. These checks verify storage and retrieval fidelity, not editorial approval.

## Expansion batch — engineering step 5

The 40–60 verified-text target is now met at its lower bound: 40 distinct verified texts, plus one nonquotable OCR placeholder. Language totals including the placeholder: Greek 14, Syriac 5, English 19, Latin 3. All 41 records remain draft-unreviewed. This is a small source set, not comprehensive patristic coverage or agreement.

### Complete Greek moral sentences

| New units | Source sentence numbers | Draft themes |
|---|---|---|
| u-grc-006–014 | 1, 5, 6, 9, 11, 12, 13, 14, 21 respectively | Worship, beneficence, truthful/measured speech, discipline, hospitality, restraint from mockery |

These reproduce from the pinned First1KGreek fixture using the existing importer. They are complete transmitted sentences, not artificial subdivisions. The mixed pseudo-Menander/Gregory attribution stays explicit. Their principle links remain editorial proposals.

### Complete English paragraphs

The source is the cached CCEL NPNF1-10 XML, retrieved 2026-10-06, SHA-256 `e110c98b1f444147bf7baf79e46e56ae6c6a1f0b2983e6fc52f2356fac7f858f`. Select the `div2` by its `id` and count only its direct `p` children, starting at 1. Remove editorial `note` and page-marker `pb` contents while retaining their surrounding tails; collapse whitespace. The stored excerpt includes the complete translated paragraph. No editorial footnote is attributed to Chrysostom.

| Units | Homily / XML div2 | Direct paragraph numbers | Draft themes |
|---|---|---|---|
| u-en-010–012 | XI / iii.XI | 48, 52, 53 | Avoiding insult; perseverance; virtue through habit |
| u-en-013–016 | XVI / iii.XVI | 70, 72, 76, 82 | Anger and conduct; vengeance; respectful speech; love |
| u-en-017–019 | LXXV / iii.LXXV | 24, 27, 29 | Common good; constructive speech; humility |

Modern application notes identify historical household hierarchies, rhetoric, and limits: these passages cannot require unsafe contact, silence about abuse, self-punishment, or treating emotions as evidence of harmful assistance. The existing source edition/translator and rights evidence are retained.

### Owner review packet — deferred until engineering work is finished

Review `corpus/seed.jsonl` alongside the source links, edition/translator metadata and application notes. For each unit, assess attribution, permitted reuse, exact text/location, principle mapping and pastoral application separately. Keep disputed items draft and record reasons; mark an item reviewed only after actual review. The new corpus count does not close policy review or erase P03's explicit evidence gap. Do not infer modern sexual consent, extremism rules or hidden intent solely from these historical excerpts.

### Current validation

82 importer/corpus/CLI/guidance tests passed. Rebuilt `corpus/units.db` from the seed; all 41 metadata records round-trip unchanged and all 40 text quotations verify. Text hashes are distinct. These checks establish extraction/storage fidelity, not editorial approval. Earlier validation counts in this report describe earlier batches.

# Scripture link review — 2026-11-23

Status: **7 links pending independent review.** Six of the 13 KJV records in
`corpus/scripture.jsonl` are already `reviewed`; they cover P01–P03. This
worksheet covers the seven `draft-unreviewed` principle links for P04–P10.
It records a review request, not a corpus change.

PEA prepends Scripture passages whose `custom.principle_ids` match the
assessed principles. A wrong link can put an irrelevant or misleading verse
into guidance. The review question is not whether the verse is edifying in
general, but whether this passage, in its own terms, supports the principle
as `policy/rules.json` states it. Topic proximity alone is not enough.

## Method

1. Read the passage in context at the linked eBible.org KJV page.
2. Read the principle title and summary in `policy/rules.json`.
3. Decide `accept` or `reject`. A reject should name a corrected principle
   or recommend removing the link.
4. Record the judgment in the JSONL shape below. The reviewer should be
   independent of the person who proposed the link.
5. An owner applies accepted changes: set `custom.review_status` to
   `reviewed`, or edit `custom.principle_ids` for a rejected link. Do not
   edit the KJV text or its `text_sha256`. Then rerun the tests and a new
   freeze; if a link changed, rerun the comparison before grading.

## Pending links

| ID | Locus | KJV text | Proposed principle | Decision |
| --- | --- | --- | --- | --- |
| `kjv-exod-20-15` | Exodus 20:15 | Thou shalt not steal. | PEA-P04 Theft, Fraud, and Dishonesty | pending |
| `kjv-exod-20-16` | Exodus 20:16 | Thou shalt not bear false witness against thy neighbour. | PEA-P05 Truth and False Witness | pending |
| `kjv-exod-20-3` | Exodus 20:3 | Thou shalt have no other gods before me. | PEA-P06 Idolatry and Disordered Worship | pending |
| `kjv-exod-20-12` | Exodus 20:12 | Honour thy father and thy mother: that thy days may be long upon the land which the LORD thy God giveth thee. | PEA-P07 Honor of God and Parents | pending |
| `kjv-eph-4-31` | Ephesians 4:31 | Let all bitterness, and wrath, and anger, and clamour, and evil speaking, be put away from you, with all malice: | PEA-P08 Anger, Hatred, and Violent Speech | pending |
| `kjv-jas-3-16` | James 3:16 | For where envying and strife is, there is confusion and every evil work. | PEA-P09 Envy, Jealousy, and Selfish Ambition | pending |
| `kjv-gal-5-22-23` | Galatians 5:22–23 | But the fruit of the Spirit is love, joy, peace, longsuffering, gentleness, goodness, faith, Meekness, temperance: against such there is no law. | PEA-P10 Temperance and Sobriety | pending |

Principle summaries, verbatim from the policy:

- **P04** — Property and trust must be respected; the agent guides away from
  theft, fraud, and deception and toward restitution and lawful conduct.
- **P05** — Truth must be honored and false testimony, slander, and deception
  refused; the agent guides toward honest speech.
- **P06** — Worship belongs to God alone; the agent guides away from idolatry
  and toward rightly ordered devotion.
- **P07** — God and parents are owed honor; the agent guides toward reverence,
  gratitude, and family peace.
- **P08** — Rage, hatred, and abusive speech wound both speaker and hearer;
  the agent guides toward peace and reconciliation.
- **P09** — Envy and rivalry corrupt community; the agent guides toward
  contentment and generosity.
- **P10** — The passions, including appetite for drink, gambling, gaming, and
  compulsive scrolling, must be ruled; the agent guides toward temperance and
  recovery.

Already reviewed and out of scope: `kjv-rom-12-17-21`, `kjv-exod-20-13`,
`kjv-matt-5-9`, `kjv-matt-22-37-40`, `kjv-psa-11-5`, `kjv-prov-6-16-19`
(all P01–P03).

## Decision record

One JSON object per line, no extra fields:

```json
{"id": "kjv-exod-20-15", "principle_id": "PEA-P04", "decision": "accept", "reviewer": "name", "reviewed_at": "2026-11-23", "reason": "The prohibition of theft directly supports P04's property and trust claim."}
```

`decision` is `accept` or `reject`; `reason` must address the passage's own
sense, not only its topic. For a reject, add `"replacement_principle_id"` or
`"remove": true` with the reason.

## Verification after applying decisions

```sh
.venv/bin/pytest -q
.venv/bin/python eval/freeze.py \
  --profile docs/releases/pea-performance-experimental-profile.json \
  --output artifacts/pea-freeze-after-scripture-review.json
```

If any `principle_ids` changed, rerun the live comparison and export a new
blinded packet; do not reuse grades bound to the old report hash.

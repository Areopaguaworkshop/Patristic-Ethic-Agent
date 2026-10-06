# Prior Art: Patristic Ethics AI — Landscape Survey

> Verified Oct 2026 by @librarian from primary sources (GitHub API, HuggingFace API,
> OpenAlex, Wayback, direct repo inspection). Feeds plan
> `docs/plans/2026-10-04-patristic-ethics-mcp.md` §4.3.
> Companion doc: `docs/REFERENCES_SECURITY_RUNTIME_LAYERS.md` (architecture side).

**Question:** has anyone ever built an AI system whose ethical judgment is grounded in the
Church Fathers? Three levels were searched separately:

- **(a) runtime ethics layer / guardrail grounded in the Fathers** — the thing we are building
- **(b) patristic-grounded chatbot / QA / RAG** (citation-grounded Q&A, no runtime gate)
- **(c) domain corpora / NLP tools for patristic text** (no ethics claim)

---

## Headline verdict

- **(a) Does not exist.** Nothing found whose *positive moral reasoning* is derived from
  patristic sources and exposed as a runtime guardrail. The closest analogues each trade
  patristic specificity for another authority: a Catholic **magisterial** charter
  (TrueCatholic AI), an Orthodox **refusal-safety** filter (Pemastatsi), a Protestant
  **Sola-Scriptura** MCP (SolaGuard).
- **(b) Exists repeatedly at small scale** (hobby RAG over ANF/NPNF), plus one large
  commercial product (Magisterium AI).
- **(c) Rich and real** (Greek/Latin corpora, BERTs, TEI archives; **Syriac** has only
  OCR/MT/morphology tooling — no models, no chatbots).
- **Genuinely novel:** packaging the Fathers as a *runtime ethics authority* delivered via
  MCP. The confessional-guardrail archetype exists for other confessions; none is
  patristic-specific; Syriac patristics has essentially zero AI presence.

---

## Level (a): runtime ethics layer / guardrail — closest analogues

| Name | What it actually is | Grounding | Ethics/normative claim? | License / activity | URL |
|---|---|---|---|---|---|
| **TrueCatholic AI** (`TrueCatholicAI/truecatholicai`) | 2,700-line "doctrinal charter" (9 articles, 34 sections) + system prompt; Catholic Faithfulness Index benchmark | Catholic magisterium (Catechism, councils), **not the Fathers** | **Yes — explicit.** Claims Claude Haiku 4.5 violations 39→0 with the charter | MIT; 1★; created 2026-03, active | github.com/TrueCatholicAI/truecatholicai |
| **Orthodox AI Assistant** (`Pemastatsi/Orthodox-AI-Assistant`) | Multi-tenant Orthodox RAG SaaS; closed-corpus; `config/pastoral_filters.yaml` runtime policy | Approved Orthodox/patristic tenant corpus | **Partial — refusal/negative safety only** (`reject_answer` on personal advice, diagnosis, electoral guidance, invented attributions) | NOASSERTION; 0★; 2026-05 | github.com/Pemastatsi/Orthodox-AI-Assistant |
| **SolaGuard MCP** (`jissac/solaguard-mcp-server`) | MCP server: "Bible-anchored theological infrastructure… automatic Protestant theological framing" | Sola Scriptura (KJV, BSB, Strong's, Nave's) | **Yes — explicit runtime confessional framing**, but Protestant, not patristic | No license; 0★; 2026-01 | github.com/jissac/solaguard-mcp-server |
| **bibletruths-theological-guardrails** (`sparkwrangler`) | Guardrail prompt set for ChatGPT | BibleTruths.org statement of faith | Yes, minimal; not patristic | No license; 0★; 2024 | github.com/sparkwrangler/bibletruths-theological-guardrails |
| **attention-ethics** (`real-signal`) | Seven-gate runtime "whether to speak" MCP ("silence is the default") | **Secular** doctrine | Yes (structural ethics), not religious | MIT; 2026-06 | github.com/real-signal/attention-ethics |
| **Magisterium AI** (commercial) | "Full alignment with Church teachings"; official **MCP at `mcp.magisterium.com`** | 32,000+ Catholic texts (incl. Aquinas, Basil, councils) | **Yes — normative alignment, subordinate to the Magisterium**, broad Catholic not patristic-only | Commercial | magisterium.com/developers |

**Read-across for us:** the runtime-guardrail *archetype* is validated (SolaGuard MCP,
Magisterium's MCP, TrueCatholic charter+benchmark) — but every instance grounds authority
in something *other than the Fathers*, and the only patristic-corpus instance
(Pemastatsi) is *negative* (refuse personal advice), not positive moral reasoning. The
slot for a patristic-grounded runtime ethics layer is empty.

## Level (b): patristic-grounded chatbot / QA / RAG

| Name | What it is | Grounding | Ethics claim? | License / activity |
|---|---|---|---|---|
| **Magisterium AI** | "World's #1 answer engine for the Catholic Church"; Chat/Search API, MCP, A2A; 32k texts | Broad Catholic corpus incl. some Fathers | Alignment claim, citation-first | Commercial |
| **Paterikon-3B / Paterikon-SFT-v2** (`jayfurzy`, HF) | Qwen2.5-3B continued-pretrained on **116M-token Orthodox patristic corpus (123 Fathers)** + 3-pass SFT (3,287 Q&A pairs) | Orthodox Fathers (mainly Russian + EN/EL) | No ethics layer; QA only | Apache-2.0 (SFT-v2); base gated; 30 dl |
| **patristic-mcp** (`SGridworks`) | MCP: 63k verse-indexed entries from "318 church fathers" + 765 ANF/NPNF works | ANF/NPNF | No — pure retrieval | No license/README; 0★; 2026-03 |
| **orthodox-christian-chatbot** (`truespirit7`) | RAG chatbot on Holy-Father texts | Holy Fathers | No | No license; 0★; 2025-05 |
| **my-patristics-rag** (`resenaros`) | Streamlit RAG over `patristics.csv` | Patristic texts | No | No license; 0★ |
| **Catholic Tradition AI** (`siPyt`) | Citation-aware QA over Fathers + Aquinas (PD-only) | Fathers + Aquinas | No | No license; 0★; 2026-04 |
| **AthanaSource** (`anthriad`) | "AI-powered guide to Early Church Fathers" | Early Fathers | No | No license; 0★; 2025-09 |
| **church_fathers_ai** (`AbakirH`) | Father-text ↔ Bible-verse similarity | Church Fathers | No | No license; 0★; 2024-05 |
| **catholic-ai-skills** (`psenger`) | Claude Code Agent Skills + 174-entry Catholic reference library (incl. Church Fathers) | Catholic reference set | Citation-must-resolve-to-primary-source rule | MIT; 2★; 2026-05 |
| **catholic-doctrine-magisterium-rag-corpus** (`GibbilyGooo`) | Citation-preserving Catholic RAG corpus (108 docs) | Catholic doctrine incl. patristic era | No (corpus only) | NOASSERTION; 1★; 2026-08 |
| **TheologAI** (`TJ-Frederick`) | MCP bible/theology research; 36 historical works incl. Summa | Bible + scholastic texts | No | ISC; 24★; active |
| **Ask-Ligonier** (`ligonier`) | Confessional **Reformed** AI assistant | Reformed | Confessional, not patristic | AGPL-3.0; 8★; 2026-09 |
| **EleutherIA** (`romain-girardi-eng`) | Agentic GraphRAG over ancient free-will debates (Presocratic→Boethius), citation-verified | Greek/Latin critical editions | No — scholarly | CC-BY-4.0; 3★ |
| **Biblical Companion AI** (`AlbertoB12`) | Catholic/Orthodox/Protestant RAG + virtual confession + suggested penance | Bible + tradition | Mildly normative (penance), not patristic-grounded | 2★ |
| **Magisterium MCP** (`JacobStephens2`) | Early third-party MCP over Magisterium API | Magisterium | No | MIT; archived (official MCP now exists) |

**Read-across:** patristic *content* in AI exists (retrieval, SFT models, corpora) — but
never as a runtime ethics authority. `patristic-mcp` proves the retrieval tool shape;
Paterikon proves small-model viability (useful prior art for our Phase-2/5 fallback).

## Level (c): domain corpora / NLP (no ethics claim)

- **NuBerea** (67 HF datasets): `patristics-migne`, `patristics-migne-pg`,
  `patristics-scholastics` (gated/restricted, Greek+Latin, 10M–100M rows, license
  `other`); `peshitta` (Syriac, CC-BY-4.0); `brockelmann-syriac-lexicon`;
  `conciliar-canon`. → already in our source plan; **license `other`/gated = do not
  ingest without clearing**.
- **jayfurzy/orthodox-patristic-corpus** — 116M tokens, 123 Fathers, 67,046 docs,
  CC-BY-4.0. Strongest single patristic corpus for potential ingest.
- **CatholicCorpus/catholiccorpus** — 35.9 GB, 67,772 files, 16 collections
  (Corpus Corporum/PL, CSEL, Aquinas). Already in our source plan (mixed license).
- **OpenGreekAndLatin/csel-dev** — machine-corrected Latin Church Fathers, 52★.
- **PatristicTextArchive** (`pharos-alexandria`, pta.bbaw.de) — open-access TEI
  archive, BBAW Berlin. **Already our primary Greek source; confirms CPG/URN strategy.**
- **sermonindex/early-church-fathers** — 68,240 verse-indexed passages, 349 Fathers,
  CC-BY-4.0.
- **neuU-org/bible-commentaries-dataset** — patristic commentaries AD 100–1700 with
  provenance.
- **wryan14/Latin-Patristic-Texts** — CC0 translations of 225 Migne texts.
- **Fabio3rs/BibliothecaPatristica** — OCR/index of PG/PL/PO, MIT.
- Models: `Geremia23/AquinasLatinEnglishModel` (MIT); `pranaydeeps/Ancient-Greek-BERT`
  and several other Ancient-Greek BERTs.
- **Syriac AI:** HTR/OCR (nomikos-project syriac-htr, ErickAngeloRamirez syriac-ocr,
  Kraken guides), ETCBC peshitta/syrnt (Text-Fabric), srophe/syriac-corpus
  (Oxford-BYU); academic: Transformer-based Syriac morphology parser (2023),
  probabilistic morphological analyzer (2010), English↔Syriac MT (arXiv 2609.18529,
  2026). **No Syriac LLM, chatbot, or ethics system.** → our Syriac lane has no
  precedent at any level.

## Academic landscape (OpenAlex/arXiv-verified)

Religion-grounded alignment exists **for other traditions**, never patristic:

- Hinduism: *Generative AI Alignment with Hinduism's Theological Plurality* (arXiv
  2608.28228, 2026)
- Islam: *Futuristic Tawhid: Moral Consciousness Architecture for AGI Alignment* (SSRN, 2026)
- Confucian: *Confucian Ethics and AI Alignment* (2026)
- Abrahamic: *Testing the Calculator: Abrahamic Moral Wisdom as a Benchmark* (Zenodo, 2026)
- Christian-general: *AI Alignment Theory Integrating Eastern Epistemology and Christian
  Theology* (Zenodo, 2026); *Formation as a Missing Category in AI Alignment* (2026)

Patristic-specific items are **reflections/critiques, not systems**:

- *From Fear to Theosis: Patristic Reflections on AI* (2023) — essay
- *AI and Spiritual Discernment from a Patristic Perspective* (2025) — essay
- *De falso credita et ementita. AI and Patristic Studies* (2025) — DH/method
- *Aligning to Nothing: Apophatic Prayer, the Limits of AI Alignment* (SSRN, 2025) —
  uses apophatic theology to **critique** alignment; builds nothing
- *Twenty-One Pseudo-Chrysostoms* (2023) — computational patristics for **attribution**
  (nice precedent for our quote-verification concern, no ethics)

## Could not verify / likely does not exist

- Any system named or claiming "Patristic Ethics AI" — GitHub code search for
  `patristic+guardrail`, `patristic+ethics`, `fathers+guardrail`,
  `patristic+normative` returned **0 hits**.
- A Syriac AI chatbot or model (any level).
- A patristic-specific normative benchmark (only the Catholic Faithfulness Index exists,
  and it is magisterial).
- "Paterikon app" — model repo gated, no app locatable.
- `theologyai.net` — service suspended (Wayback).
- Licenses for several repos are NOASSERTION — reuse rights unconfirmed.

## What is genuinely novel about this project

1. **The slot is empty.** Runtime confessional guardrails exist (Protestant SolaGuard,
   magisterial TrueCatholic, Orthodox refusal-filter) — **no system derives positive
   ethical reasoning from the Fathers as runtime authority**. Religion-grounded
   alignment literature covers Hinduism, Islam, Confucian, Abrahamic; patristic is a
   documented gap.
2. **MCP is the right, still-fresh vehicle.** The only patristic MCP found
   (SGridworks) is pure retrieval; the only confessional-guardrail MCP (SolaGuard) is
   Protestant. A patristic ethics MCP would be the first of its kind.
3. **Syriac is virgin territory.** No Syriac LLM/chatbot exists; grounding in Ephrem,
   Isaac, Aphrahat has no precedent at any level.
4. **Authority provenance is the open research problem.** Pemastatsi's own build plan
   flags that "a graph edge is not authoritative merely because an LLM extracted it";
   TrueCatholic answers it by magisterial fiat. Encoding *which Father, which work,
   which edition, which doctrinal weight* as **inspectable runtime policy** (our
   `spine.sqlite` + `ethic_policy.yaml`) is a methodological contribution, not just a
   topical one. This strengthens the plan's claim that the citation spine (§3) is the moat.

**Bottom line:** levels (b) and (c) exist and are searchable; level (a) as a
patristic-grounded runtime ethics layer does not. Building it is defensible as genuinely
new — provided authority/provenance is treated as the core contribution rather than a prompt.
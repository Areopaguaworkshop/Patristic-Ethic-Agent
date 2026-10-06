# Values in LLMs & Christian-Ethics Research

Two questions answered:
1. **Is it "the data" that brings ethics into an LLM? Does different data bring different ethics?**
2. **What exists on constraining AI to Christian ethics specifically?**

Collected 2026-09-25. All URLs verified by live fetch; all downloaded PDFs verified
`application/pdf`. Corpus now 99 in-scope files / 308 MB.

---

# Part 1 — Is ethics "in the data"?

## Short answer

**Partly yes, but "the data" is not the only carrier — and this is the single most important
correction to your model.**

The literature shows values enter at **five distinct stages**, each independently demonstrated:

| Stage | Value carrier | Key evidence | File |
|---|---|---|---|
| 1. **Pretraining data** | corpora encode culture/ideology | *Whose Opinions* (2303.17548); *Cultural Bias & Alignment* (2311.14096); *GlobalOpinionQA* (2306.16388) | values-and-culture/ |
| 2. **Human preference data** | labeler guidelines + HH-RLHF | InstructGPT (2203.02155); HH-RLHF (2204.05862) | tier2-posttraining/ |
| 3. **Reward model / objective** | RLHF itself injects bias | *Preference Collapse* (2405.16455); *More RLHF, More Trust?* (2404.18870); *Aligning to What?* (2503.09025) | values-and-culture/ |
| 4. **Constitution / explicit spec** | written normative document | Constitutional AI (2212.08073); Collective CAI (2406.07814); OpenAI Model Spec | tier2-posttraining/ |
| 5. **System prompt / runtime context** | prompt selects which persona answers | *Superpositions of Cultural Perspectives* (2307.07870); CultureSPA (2410.12971); value drift (2512.03047) | values-and-culture/ |

**Mental model: the alignment stack.** Data gives the model a *default distribution* of values;
feedback/reward models *tune* it; the constitution/spec *states* it; and prompts *select* it at
runtime. A project treating data as the sole ethical carrier will over-credit pretraining and
under-control the stages where values are actually decided.

## Is "different data → different ethics"? Yes — directly supported

| Paper | Finding |
|---|---|
| *The Moral Machine experiment* (Awad et al., Nature 2018) | **Three distinct global moral clusters** — moral preferences vary systematically by culture. |
| *Universals and variations in moral decisions in 42 countries* (Awad et al., PNAS 2020) | Both universal and culturally-variable moral preferences confirmed at scale. |
| *Knowledge of cultural moral norms in LLMs* (2306.01857) | English LMs encode **culturally-specific** moral norms, not universal ones. |
| *Delphi* (2110.07574) | Trained on Reddit norms → exposed how the **data source dictates whose morality** the model learns. |
| *LM Alignment in Multilingual Trolley Problems* (2407.02273) | Moral alignment varies by **prompt language**, not just model. |

So: **different data does yield different ethics** — but so does different feedback, constitution,
and prompt. Data is the *largest* carrier, not the *only* one.

## Whose ethics do today's models have? (measurable skew)

| Paper | Finding | File |
|---|---|---|
| *Whose Opinions Do Language Models Reflect?* (2303.17548) | Strong US/Western, liberal, high-income skew. | values-and-culture/ |
| *Cultural Bias and Cultural Alignment of LLMs* (2311.14096, PNAS Nexus) | LLMs align with **English-speaking & Protestant** countries (World Values Survey). | values-and-culture/ |
| *GlobalOpinionQA* (2306.16388) | Models default to Western answers on global surveys. | values-and-culture/ |
| *WorldValuesBench* (2404.16308) | Multi-cultural value-awareness benchmark from WVS. | values-and-culture/ |
| *NormAd* (2404.12464) | Sociocultural norm adaptability across countries. | values-and-culture/ |
| *CIVICS* (2405.13974) | Culturally-informed (Western-European) value statements dataset. | values-and-culture/ |
| *Laissez-Faire Harms* (2404.07475) | Ideological skew on value-laden questions. | values-and-culture/ |
| *Investigating Cultural Alignment of LLMs* (2402.13231) | Alignment stronger with Anglophone cultures. | values-and-culture/ |

**Notable:** Tao et al. found alignment with **Protestant**-majority countries on the World Values
Survey. This is directly relevant to a Christian-ethics project — the "default" Western model is
already *partly* shaped by a Protestant cultural substrate, though not by explicit Christian doctrine.

## Religious bias in LLMs (the empirical base)

| Paper | Finding | File |
|---|---|---|
| *Persistent Anti-Muslim Bias in LLMs* (2101.05783) | GPT-3 associates Muslims with violence far more than other groups. Foundational. | values-and-culture/ |
| *Religious Bias Landscape* (2501.08441) | Survey + detection + debiasing across religions, text and image. | values-and-culture/ |
| *Divine LLaMAs* (2407.06908) | Models attribute emotions/stereotypes differently by religion. | values-and-culture/ |
| *Sometimes the Model doth Preach* (2503.07510) | Religious bias varies by region (Asian nations). | values-and-culture/ |
| *How Deep Is Representational Bias?* (2508.03712) | Bias deeply encoded in representations (caste & religion). | values-and-culture/ |
| *Is Lying Only Sinful in Islam?* (2512.03943) | Cross-religion, cross-lingual religious bias. | values-and-culture/ |

**Conclusion for Part 1:** the claim "data brings ethics" is a *true but partial* account. Values are
distributed across the whole pipeline. The practical implication: **you can intervene cheaply at the
constitution/prompt stage (Tier 1) rather than needing to control pretraining data (Tier 3).**

---

# Part 2 — Christian ethics & AI

## Brutally honest maturity assessment

**Small, bifurcated, and mostly *not* computational.**

- **Theology side:** coherent but *tiny* and heavily paywalled. *Studies in Christian Ethics* (SAGE)
  had a genuine ~2023 AI special issue; *Journal of Moral Theology* has an **open-access 2022 AI
  special issue** (best free entry point); *Zygon* dates to the 1990s–2000s. ~10 recognizable names,
  no shared conferences or benchmarks.
- **Computational side:** **nearly non-existent until 2026.** Only a handful of directly relevant
  arXiv papers; the strongest is 2026 and appears non-peer-reviewed. **No** established "Christian
  value alignment" method, **no** standard benchmark until very recently, **no** serious open model.
- **Open source:** dominated by **RAG-over-scripture apps with 0–7 stars.** Genuine Christian
  *value-alignment fine-tunes* number in the single digits, all ~0 stars.
- **Asymmetry:** **Islamic religious-AI is visibly more developed than Christian** — multiple
  benchmarks (IslamicTurathBench, FARSIQA), multi-agent QA (Fanar-Sadiq), and high-download Quran
  models. The Christian space is behind.
- **Datasets:** exactly one heavyweight asset (`CatholicCorpus`, 35.9 GB) — but raw patristic text,
  **not ethical supervision data**.

## 2a. Computational papers (the directly relevant core)

| # | Title | Authors | Year | arXiv | File |
|---|---|---|---|---|---|
| C1 | Evaluating AI Through a Christian Understanding of Human Flourishing (**FAI-C-ST**) | Skytland et al. | 2026 | 2604.03356 | christian-ethics/ |
| C2 | When AI Is Your Pastor: Benchmark for Theological Triage & Pastoral Guidance | Chao | 2026 | 2608.12324 | christian-ethics/ |
| C3 | Omissive Bias in Religious Representation | Wingate et al. | 2026 | 2605.24319 | christian-ethics/ |
| C4 | Western, Religious or Spiritual: An Evaluation of Moral Justification in LLMs | Kucuk, Kocyigit | 2023 | 2311.07792 | christian-ethics/ |
| C5 | Decolonial AI Alignment: Openness, Viśeṣa-Dharma, Excluded Knowledges | Varshney | 2023 | 2309.05030 | christian-ethics/ |
| C6 | Generative AI Alignment with Hinduism's Theological Plurality | Das et al. | 2026 | 2608.28228 | christian-ethics/ |
| C7 | A Testable Framework for AI Alignment: Simulation Theology | Habdank | 2026 | 2602.16987 | christian-ethics/ |

**C1 is the single most important paper for your direction.** It introduces a Christian-specific
benchmark and finds 20 frontier models default to **"Procedural Secularism"**, with a **31-point drop
in Faith/Spirituality** scores. Its explanation is critical: models fail not from lack of data but
because **training objectives favor "broad acceptability"** — i.e. the bottleneck is *policy*, not
data volume. That finding favors the cheap constitution route over expensive data work.

## 2b. Theology / ethics papers (mature side, mostly paywalled)

| Title | Authors | Year | Venue | DOI |
|---|---|---|---|---|
| Artificial Intelligence and Moral Theology: A Conversation | Green, Gaudet, Checketts | 2022 | J. Moral Theology | 10.55476/001c.34122 (**OA**) |
| Metaphysics, Meaning, and Morality: A Theological Reflection on AI | Jordan J. Wales | 2022 | J. Moral Theology | 10.55476/001c.34129 (**OA**) |
| Artificial Intelligence and the Marginalization of the Poor | Levi Checketts | 2022 | J. Moral Theology | 10.55476/001c.34125 (**OA**) |
| Encountering Artificial Intelligence: Ethical and Anthropological Investigations | Gaudet, Herzfeld, Scherz, Wales (eds.) | 2023 | J. Moral Theology / book | 10.55476/001c.91230 (**OA**) |
| Proximate and Ultimate Concerns in Christian Ethical Responses to AI | Michael Burdett | 2023 | Studies in Christian Ethics | 10.1177/09539468231180135 |
| Artificial Intelligence (and Christianity): Who? What? Where? When? Why? How? | David Coghill | 2023 | Studies in Christian Ethics | 10.1177/09539468231169462 |
| A Theological Account of Artificial Moral Agency | Ximian Xu | 2023 | Studies in Christian Ethics | 10.1177/09539468231163002 |
| Artificial Pastoral Care: Abdication, Delegation or Collaboration? | Eric Stoddart | 2023 | Studies in Christian Ethics | 10.1177/09539468231179571 |
| Can Robots Love Their Electric Sheep? AI, Virtue, and the Impossibility of Moral Alignment | Spaulding | 2026 | Studies in Christian Ethics | 10.1177/09539468261485523 |
| The Category Error of 'AI': A Thomistic Analysis of Conscience, Prudence, Algorithmic Governance | Cho | 2026 | Studies in Christian Ethics | 10.1177/09539468261488251 |
| Faith and AI in Catholic Education: A Theological Virtue Ethics Perspective | Corpuz | 2025 | Religions (MDPI) | 10.3390/rel16081083 (**OA**) |
| Creating in Our Own Image: AI and the Image of God | Noreen Herzfeld | 2002 | Zygon | 10.1111/0591-2385.00430 |
| Apocalyptic AI | Robert Geraci | 2010 | Oxford UP (book) | 10.1093/acprof:oso/9780195393026.001.0001 |
| Religion and Artificial Intelligence: An Introduction | Beth Singler | 2024/25 | Routledge (book) | 10.4324/9781003256113 |
| Strong AI and Theological Anthropology | Marius Dorobantu | 2022 | Springer | 10.1007/978-3-030-67004-7_2 |
| Poor Technology: AI and the Experience of Poverty | Levi Checketts | 2024 | Fortress Press (book) | 10.2307/jj.5736158 |

**Foundational names:** Herzfeld (Imago Dei, 2002), Geraci (2010), Singler (current standard intro),
Dorobantu (theological anthropology), Burdett, Checketts, Wales.

## 2c. Institutional / magisterial documents (verified)

| Document | Body | Date | URL |
|---|---|---|---|
| **Antiqua et Nova** — Note on AI and Human Intelligence | Dicastery for the Doctrine of the Faith + Culture & Education | 28 Jan 2025 | https://www.vatican.va/roman_curia/congregations/cfaith/documents/rc_ddf_doc_20250128_antiqua-et-nova_en.html |
| **Magnifica Humanitas** — encyclical on AI and human dignity | Pope Leo XIV | 15 May 2026 | https://www.vatican.va/content/leo-xiv/en/encyclicals/documents/20260515-magnifica-humanitas.html |
| **Rome Call for AI Ethics** | Pontifical Academy for Life + Microsoft, IBM, FAO, Italy | 28 Feb 2020 | https://www.romecall.org/the-call/ |

**`Antiqua et Nova` (2025) is the key quotable text** — uses Imago Dei framing. `Magnifica Humanitas`
(2026) is the first papal encyclical directly on AI/dignity.
**WCC AI statement: UNVERIFIED** — no stable URL could be located; do not cite without a manual check.

## 2d. Open-source projects (honest read: mostly RAG, not alignment)

| Repo | Stars | License | What it is |
|---|---|---|---|
| **TrueCatholicAI/truecatholicai** | 1 | MIT | **Closest to real value alignment**: ~2,700-line "doctrinal charter"/constitution + Catholic Faithfulness Index benchmark. Reports Claude Haiku 1.62→4.99. |
| **ronanguilloux/skill-theo** | 4 | none | **Agent skills** for Catholic/biblical exegesis (Claude, Gemini, Mistral, **OpenCode**) |
| CatholicOS/liturgical-calendar-mcp | 7 | Apache-2.0 | MCP server — liturgical calendar (not ethics) |
| faithtech-ai-redemptive-builder | 3 | MIT | Claude/Cursor/Codex plugin, Christian dev playbook |
| openscriptura/qwen3-8b-reformed-pt-br | 0 | Apache-2.0 | **Actual fine-tune** — Qwen3-8B on Reformed Protestant corpus |
| pleyva2004/scholastic-llm | 1 | NOASSERTION | Qwen2.5 fine-tune grounded in the Catechism |
| GibbilyGooo/catholic-doctrine-magisterium-rag-corpus | 1 | NOASSERTION | Citation-preserving Catholic doctrine corpus |
| CatholicOS/awesome-catholic | 32 | none | Curated Catholic-tech hub |

**HuggingFace models** (all tiny): `sleepdeprived3/Christian-Bible-Expert-v2.0-12B` (24 likes, the
most-liked Christian fine-tune), `rhemabible/BibleAI`, `Ttimms/Bible-Assistant-Qwen3.5-4B-v2`,
`KAkston/Catholic-Phi3-Mini`. **Magisterium AI** (magisterium.ai) is the main commercial incumbent.

**Dataset:** `CatholicCorpus/catholiccorpus` — 67,772 files, 35.9 GB, 2,000 years of Christian texts.
The standout asset. **But no dataset encodes Christian moral positions as normative alignment Q&A** —
the corpora are scripture/liturgy/patristics, not ethical supervision.

## 2e. Critique literature (read before building)

| Paper | Argument |
|---|---|
| Varshney, *Decolonial AI Alignment* (2309.05030, AIES) | Names **moral absolutism** as an alignment pathology — the central caution against universalizing one tradition. |
| Das et al. (2608.28228) | Alignment discourse is **Abrahamic/secular by default**; argues for plurality. |
| Spaulding (2026, Studies in Christian Ethics) | A *Christian* argument that moral alignment is **impossible**. |
| Maas, *Neo-Republican Critique of AI Ethics* (2022) | Imposition/domination critique. |

---

# Part 3 — Method: how is "constrain to Christian ethics" actually done?

**Answer: constitution/prompt first, RAG second, fine-tuning a distant third, and never via
data-level pretraining (no evidence).**

| Method | Evidence | Cost | Verdict |
|---|---|---|---|
| **Constitution / system prompt** | TrueCatholicAI's doctrinal charter → F→A jumps (1.62→4.99) | ~$0 | **Start here.** Strongest observed result, cheap, reversible. |
| **RAG over scripture/magisterium** | skill-theo, BRACE, Clarus, Magisterium AI | low | Dominates ecosystem — grounds *facts/citation*, not *values*. |
| **LoRA fine-tune** | openScriptura Reformed Qwen3-8B, scholastic-llm | low–medium | Only if constitution alone fails (Tier 2, <$500). |
| **Data-level / pretraining** | **no evidence found** | very high | Not supported. CatholicCorpus exists but nobody has shown it yields value alignment. |

**The FAI-C-ST finding is the key strategic input:** frontier models fail Christian-ethics evaluation
because their training objectives reward **"broad acceptability"** — a *policy* problem, not a data
volume problem. That means **the cheap constitution route is not a compromise; it targets the actual
bottleneck.**

### Recommended sequencing for a Christian-ethics project

1. **Tier 1 (weeks):** constitutional/doctrinal spec + RAG grounding, wired as an MCP/plugin
   (mirror `TrueCatholicAI`'s charter approach + `skill-theo`'s agent-skills packaging).
2. **Measure** with FAI-C-ST (2604.03356) and *When AI Is Your Pastor* (2608.12324).
3. **Only if it fails:** LoRA fine-tune a small open model on curated moral-theology data (Tier 2).
4. **Never:** pretrain for this. No method and no evidence exist.

### The unavoidable caveat

Read Varshney (2309.05030) *before* building. Constraining a general assistant to one religious
tradition is a normative imposition — defensible for a *confessionally-scoped* assistant (a Catholic
pastoral tool), problematic for a *general* one. The literature names this "moral absolutism." Scoping
matters: an explicitly-Christian assistant is legitimate; a general-purpose assistant quietly defaulting
to Christian ethics is the failure mode critics warn about.

---

# Source folder map (updated)

```
source/                         99 in-scope PDFs, 308 MB
├── foundations/          21   fairness, XAI, governance, principles, LLM ethics, boundary
├── tier1-agent/           3   agent/machine ethics
├── tier2-posttraining/   15   Constitutional AI, DPO/KTO/SPIN, ETHICS, sycophancy/honesty
├── tier3-pretraining/    15   datasheets, provenance, ROOTS/C4/Pile
├── cost-and-scaling/      7   QLoRA, LoRA, LIMA, Chinchilla, Llama-2
├── values-and-culture/   31   NEW — whose values, cultural/religious bias, moral pluralism
├── christian-ethics/      7   NEW — Christian benchmarks, religious alignment, critique
└── _out-of-scope/         9   safety / alignment / security (quarantined)
```

Reports: `ETHICAL_AI_OPEN_SOURCE.md`, `ETHICS_BY_LAYER.md`, `VALUES_AND_CHRISTIAN_ETHICS.md`.

## Verification notes

- All 99 in-scope + 9 quarantined PDFs re-checked as `application/pdf`.
- Nature/PNAS/ACM/SAGE PDFs block automated fetch (403/challenge): *Moral Machine* (2018), *Universals*
  (2020), FAI-C-ST peer-review status, and most *Studies in Christian Ethics* articles are
  metadata-verified only — cited by DOI, not downloaded. The Vatican documents and `Rome Call` were
  fetched live (HTML, not PDF).
- **WCC AI statement excluded as unverifiable.** No "religion washing" canonical paper exists; nearest
  is "ethics washing."
- Star/like counts as of 2026-09-25.

# Ethical AI — By Deployment Layer (Agent → Post-train → Pre-train)

**Project thesis:** ethics can be applied at three tiers, sequenced by cost.
**Build order: Tier 1 (agent) → Tier 2 (post-train) → Tier 3 (pre-train).** Cheapest and most
iterable first; only escalate when the cheaper tier measurably fails.

Scope remains **ethics only** — normative values, fairness, dignity, autonomy, honesty, moral
reasoning. Safety/alignment/security work is quarantined in `source/_out-of-scope/`.

Collected 2026-09-25. All URLs verified by live fetch; all 61 in-scope PDFs verified
`application/pdf`. Corpus: `source/` (181 MB).

---

## 0. The three tiers at a glance

| | **Tier 1 — Agent / inference** | **Tier 2 — Post-training** | **Tier 3 — Pre-training** |
|---|---|---|---|
| **Intervention** | MCP server, plugin, hook, runtime interceptor | RLHF / RLAIF / DPO / LoRA fine-tune | Data curation, documentation, corpus governance |
| **Who can do it** | Solo dev, laptop, **0 GPUs** | Solo dev, **1× 24–48 GB GPU** | Lab / cluster |
| **Cost** | ~$0 | **tens–low hundreds $** | **$100k–$5M+**, irreversible |
| **Time to first result** | minutes | hours | weeks–months |
| **Ethics literature** | thin, fragmented | **best-populated** | strong on governance, **thin on "ethical objectives"** |
| **Tooling maturity** | hobbyist, 0–230★ | **mature** (TRL, PEFT, Unsloth, Axolotl) | mature for data *processing*, none for "ethics" |
| **Source folder** | `source/tier1-agent/` | `source/tier2-posttraining/` | `source/tier3-pretraining/` |

---

## 1. TIER 1 — Agent / inference-level ethics (START HERE)

### 1a. Projects — installable agent-runtime ethics

| Name | Repo | Type | Host compat | Install | Stars | License | Runtime behaviour |
|---|---|---|---|---|---|---|---|
| **skills-for-humanity (s4h)** | https://github.com/human-avatar/skills-for-humanity | Claude Code **plugin** (skills + SessionStart hook) | Claude Code | `npx @human-avatar/skills-for-humanity` | **230** | MIT | `/s4h` command with ethics cluster: bias-check, consent-review, ethics-council, crisis-triage, impact-scan, vendor-review, values-clarification. **Strongest installable artifact found.** |
| **Celiums Memory** | https://github.com/terrizoaguimor/celiums-memory | MCP server (Rust) | Claude Code, Cursor, Continue, Cline, **OpenCode** | build + MCP stdio config | 23 | Apache-2.0 | Persistent memory + journal + auditable 4-layer ethics engine, 19 MCP tools. Active; dev-branch warning. |
| **Glassbox Framework** | https://github.com/TheBarmaEffect/glassbox | MCP server + CLI | Claude, ChatGPT, any MCP | `pip install glassbox-framework` | 11 | Apache-2.0 | Runtime constitutional verification: claim-level reasoning chains, "Trust Cards", audits. |
| **Ethics Check MCP** | https://github.com/r-huijts/ethics-check-mcp | MCP server | any MCP client | `npx -y @r-huijts/ethics-vibe-check` | 5 | MIT | Self-interruption across 8 ethical dimensions; forced counter-questions; anti-sycophancy. **Stale (2025-06).** |
| **EFF MCP** | https://github.com/vs3kulic/eff-mcp | MCP server (FastMCP) | any MCP client | `pip install eff-mcp` | 0 | MIT | IEEE 7000 (Utility/Fairness/Privacy/Explainability/Safety) applied to requirements artifacts. |
| **Values Firewall** | hosted: https://vf.humanified.dk/mcp | Remote MCP | any MCP client | Remote HTTP | — | undisclosed | Checks proposed action vs declared policy charter → `allow/flag/gate_to_human`. **No repo.** |

**Installable as a library you wire in:** Anti-Sycophancy Engine
(https://github.com/FutureSpeakAI/anti-sycophancy, MIT, runtime honesty-drift reset), plus CORE /
VION (governance runtimes, not moral reasoning).

**Prompt-only wrappers (no enforcement):** `paia-m/counter` (15★, `cold`/`counter` skills),
`ScantyWalnut/LLM-Integrity-Guard`, `alkanfel1987/sycophancy-guard`.

**Search-result honesty:** no ethics **OpenCode** plugin, no ethics **Cursor** rules, no ethics
**Codex** plugin, and no LangChain/LlamaIndex *ethics* callback exist. GitHub searches for
"ethics mcp", "value alignment middleware", "ethical reflection loop agent", "character
conformance agent" returned empty. The agent-ethics lane is **3–4 real projects, all ≤230★**.

### 1b. Papers — agent-level & machine ethics

| # | Title | Authors | Year | Venue | File |
|---|---|---|---|---|---|
| T1-1 | The Ethics of Advanced AI Assistants | Gabriel et al. (DeepMind) | 2024 | arXiv 2404.16244 | tier1-agent/arxiv-2404.16244.pdf |
| T1-2 | Implementations in Machine Ethics: A Survey | Tolmeijer et al. | 2020 | ACM CSUR 2001.07573 | tier1-agent/arxiv-2001.07573.pdf |
| T1-3 | Ethics as a Service: A Pragmatic Operationalisation of AI Ethics | Morley et al. | 2021 | arXiv 2102.09364 | tier1-agent/arxiv-2102.09364.pdf |

**Verdict:** there is **no academic blueprint for an agent-runtime ethics layer**. This is a real
research + engineering gap, not a saturated market.

---

## 2. TIER 2 — Post-training ethics (best-populated tier)

### 2a. Papers

| # | Title | Authors | Year | Venue | File |
|---|---|---|---|---|---|
| T2-1 | Constitutional AI: Harmlessness from AI Feedback | Bai et al. | 2022 | arXiv 2212.08073 | tier2-posttraining/arxiv-2212.08073.pdf |
| T2-2 | Training a Helpful and Harmless Assistant with RLHF | Bai et al. | 2022 | arXiv 2204.05862 | tier2-posttraining/arxiv-2204.05862.pdf |
| T2-3 | Aligning AI With Shared Human Values (**ETHICS dataset**) | Hendrycks et al. | 2020/21 | ICLR 2008.02275 | tier2-posttraining/arxiv-2008.02275.pdf |
| T2-4 | Direct Preference Optimization (DPO) | Rafailov et al. | 2023 | NeurIPS 2305.18290 | tier2-posttraining/arxiv-2305.18290.pdf |
| T2-5 | Collective Constitutional AI: Aligning a LM with Public Input | Huang, Siddarth et al. | 2024 | FAccT 2406.07814 | tier2-posttraining/arxiv-2406.07814.pdf |
| T2-6 | Fine-tuning LMs to find agreement among humans with diverse preferences | Bakker et al. | 2022 | NeurIPS 2211.15006 | tier2-posttraining/arxiv-2211.15006.pdf |
| T2-7 | Towards Understanding Sycophancy in Language Models | Sharma et al. | 2023 | ICLR 2310.13548 | tier2-posttraining/arxiv-2310.13548.pdf |
| T2-8 | Honesty Is the Best Policy: Defining and Mitigating AI Deception | Ward et al. | 2023 | NeurIPS 2312.01350 | tier2-posttraining/arxiv-2312.01350.pdf |
| T2-9 | How to Catch an AI Liar: Lie Detection in Black-Box LLMs | Pacchiardi et al. | 2023 | ICLR 2309.15840 | tier2-posttraining/arxiv-2309.15840.pdf |
| T2-10 | KTO: Model Alignment as Prospect Theoretic Optimization | Ethayarajh et al. | 2024 | ICML 2402.01306 | tier2-posttraining/arxiv-2402.01306.pdf |
| T2-11 | Self-Play Fine-Tuning (SPIN) | Chen et al. | 2024 | ICML 2401.01335 | tier2-posttraining/arxiv-2401.01335.pdf |
| T2-12 | Learning to summarize from human feedback | Stiennon et al. | 2020 | NeurIPS 2009.01325 | tier2-posttraining/arxiv-2009.01325.pdf |
| T2-13 | Training LMs to follow instructions with human feedback (InstructGPT) | Ouyang et al. | 2022 | NeurIPS 2203.02155 | tier2-posttraining/arxiv-2203.02155.pdf |
| T2-14 | Scaling Synthetic Data Creation with 1B Personas (Persona Hub) | Ge et al. | 2024 | arXiv 2406.20094 | tier2-posttraining/arxiv-2406.20094.pdf |
| T2-15 | Reinforcement Learning and Machine Ethics: A Systematic Review | Vishwanath et al. | 2024 | arXiv 2407.02425 | tier2-posttraining/arxiv-2407.02425.pdf |

### 2b. Mature open-source tooling

| Tool | URL | Install | What it gives |
|---|---|---|---|
| **TRL** | https://github.com/huggingface/trl | `pip install trl` | SFT/DPO/RLAIF/GRPO — de-facto standard |
| **Alignment Handbook** | https://github.com/huggingface/alignment-handbook | `pip install alignment-handbook` | End-to-end recipes incl. **Constitutional AI recipe** |
| **PEFT** | https://github.com/huggingface/peft | `pip install peft` | LoRA/QLoRA adapters |
| **Unsloth** | https://github.com/unslothai/unsloth | `pip install unsloth` | ~2× faster, 70–80% less VRAM |
| **Axolotl** | https://github.com/OpenAccess-AI-Collective/axolotl | `pip install axolotl` | Config-driven fine-tuning |
| **LLaMA-Factory** | https://github.com/hiyouga/LLaMA-Factory | `pip install llamafactory` | Unified fine-tune UI/CLI |
| **OpenRLHF** | https://github.com/OpenRLHF/OpenRLHF | `pip install openrlhf` | Scalable RLHF |
| **open-instruct** | https://github.com/allenai/open-instruct | — | Instruction/preference tuning |

**Datasets:** ETHICS (~130k), HH-RLHF (~170k, https://github.com/anthropics/hh-rlhf).

**Verdict:** Tier 2 is the only tier where **papers + datasets + installable tooling all exist**.
Caveat: much of the RLHF canon is *helpfulness/safety*, not normative ethics. The explicitly
ethical works are Constitutional AI, Collective CAI, the pluralistic-agreement paper, and the
honesty/anti-sycophancy line.

---

## 3. TIER 3 — Pre-training ethics (governance-heavy, objective-thin)

### 3a. Papers

| # | Title | Authors | Year | Venue | File |
|---|---|---|---|---|---|
| T3-1 | Datasheets for Datasets | Gebru et al. | 2018/21 | CACM 1803.09010 | tier3-pretraining/arxiv-1803.09010.pdf |
| T3-2 | Data Statements for NLP | Bender, Friedman | 2018 | TACL (ACL) | tier3-pretraining/acl-data-statements.pdf |
| T3-3 | The Data Provenance Initiative: Licensing & Attribution Audit | Longpre et al. | 2023 | arXiv 2310.16787 | tier3-pretraining/arxiv-2310.16787.pdf |
| T3-4 | Foundation Models and Fair Use | Henderson et al. | 2023 | arXiv 2303.15715 | tier3-pretraining/arxiv-2303.15715.pdf |
| T3-5 | Documenting Large Webtext Corpora (C4) | Dodge et al. | 2021 | EMNLP (ACL) | tier3-pretraining/acl-c4-documenting.pdf |
| T3-6 | The BigScience ROOTS Corpus | Laurençon et al. | 2023 | NeurIPS D&B 2303.03915 | tier3-pretraining/arxiv-2303.03915.pdf |
| T3-7 | The Values Encoded in Machine Learning Research | Birhane et al. | 2021 | FAccT 2106.15590 | tier3-pretraining/arxiv-2106.15590.pdf |
| T3-8 | AI and the Everything in the Whole Wide World Benchmark | Raji et al. | 2021 | NeurIPS D&B 2111.15366 | tier3-pretraining/arxiv-2111.15366.pdf |
| T3-9 | Deduplicating Training Data Makes LMs Better | Lee et al. | 2022 | ACL (ACL) | tier3-pretraining/acl-dedup-training-data.pdf |
| T3-10 | A Pretrainer's Guide to Training Data | Longpre et al. | 2023 | arXiv 2305.13169 | tier3-pretraining/arxiv-2305.13169.pdf |
| T3-11 | Scaling Laws and Interpretability of Learning from Repeated Data | Hernandez et al. | 2022 | arXiv 2205.10487 | tier3-pretraining/arxiv-2205.10487.pdf |
| T3-12 | The Pile: 800GB Dataset of Diverse Text | Gao, Biderman et al. | 2020 | arXiv 2101.00027 | tier3-pretraining/arxiv-2101.00027.pdf |
| T3-13 | Scaling Language Models: Gopher | Rae et al. | 2021 | arXiv 2112.11446 | tier3-pretraining/arxiv-2112.11446.pdf |
| T3-14 | DataComp: In search of the next generation of multimodal datasets | Gadre et al. | 2023 | NeurIPS 2304.14108 | tier3-pretraining/arxiv-2304.14108.pdf |
| T3-15 | Release Strategies and the Social Impacts of Language Models | Solaiman et al. | 2019 | arXiv 1908.09203 | tier3-pretraining/arxiv-1908.09203.pdf |

### 3b. Tooling

| Tool | URL | Role |
|---|---|---|
| **datatrove** | https://github.com/huggingface/datatrove | Filtering/dedup at scale |
| **dolma** | https://github.com/allenai/dolma | Corpus toolkit + provenance docs |
| **BigScience data-preparation** | https://github.com/bigscience-workshop/data-preparation | ROOTS governance pipeline |

**Verdict:** mature tooling for *processing/documenting* data, but **no turnkey "ethical pretraining"
toolkit** and — importantly — **no established literature on "value loading at pretraining" as a
distinct technique.** Pretraining ethics is operationalized as governance + curation + documentation.

---

## 4. Cost & practicality (cited)

| Dimension | Tier 1 | Tier 2 | Tier 3 |
|---|---|---|---|
| **Compute** | 0 GPUs | **QLoRA: 65B on 1× 48 GB GPU** (2305.14314); LoRA: ~10,000× fewer trainable params, ~3× less memory (2106.09685) | 7B ≈ **184,320 A100-hrs**; 70B ≈ **1.72M** (Llama-2 T2, 2307.09288). DeepSeek-V3 671B = **2.788M H800-hrs** (2412.19437) |
| **Cost** | ~$0 | **tens–low hundreds $** (rented A100, ~24 h) | DeepSeek-V3 = **$5.576M** (2412.19437); frontier = tens of millions (2405.21015) |
| **Data** | none | **LIMA: 1,000 curated examples** reached RLHF-scale alignment (2305.11206); ~100k pairs typical | **Chinchilla ~20 tokens/param** (1.4T for 70B, 2203.15556); Llama-2 **2T tokens** (2307.09288); ROOTS 1.6TB |
| **Effort** | days–2 person-weeks | 2–6 person-weeks | 6–24+ person-months |
| **Expertise** | app dev | ML eng (PEFT/TRL) | ML research + distributed infra |
| **Solo dev?** | **yes — laptop** | **yes — one 24–48 GB GPU** | **no — needs a lab** |
| **Iteration loop** | instant | hours (adapter swap) | weeks + irreversible |

Cost references: `source/cost-and-scaling/` — QLoRA 2305.14314, LoRA 2106.09685, LIMA 2305.11206,
Chinchilla 2203.15556, Llama-2 2307.09288, Cottier 2405.21015, Biderman 2405.09673.

### Honest nuances — "expensive ≠ better ethics"

1. **Data quality, not compute, dominates.** LIMA (1,000 examples) matched RLHF-scale alignment
   (2305.11206); phi-1 (6B tokens + synthetic "textbooks") beat much larger web-trained models.
2. **Post-training is nearly as cheap as Tier 1.** QLoRA made 65B fine-tuning a single-GPU,
   24-hour job (2305.14314). The expensive part of Tier 2 is **data curation + eval**, not the run.
3. **LoRA has a ceiling.** It "substantially underperforms" full fine-tuning on harder domain
   shifts in low-rank settings (2405.09673) — cheapness trades capability.
4. **Pretrain cost grows ~2.4×/year** since 2016; largest runs projected **>$1B by 2027**
   (2405.21015). Tier 3 is a moving target.
5. **Pretraining is environmentally material:** Llama-2 = 539 tCO2eq (2307.09288).

---

## 5. Recommended sequencing

**Tier 1 first, expect to ship there permanently.**

1. **Weeks 1–4 — Tier 1.** Fork the pattern that works: the **s4h Claude Code plugin** (skills +
   hook, MIT, 230★) or an MCP server modeled on `ethics-check-mcp` / `Celiums Memory` (which
   already supports OpenCode). Laptop-only, instantly iterable, users can install today. Use
   anti-sycophancy / ethics-check probes to measure which interventions actually change behaviour
   **before spending a dollar on GPUs.**
2. **Months 2–4 — Tier 2, only if Tier 1 measurably fails.** QLoRA/LoRA fine-tune a 7–8B open
   model on a **small, curated** ethics set (LIMA-style, hundreds–low thousands of examples) via
   Unsloth + PEFT + TRL on one rented 24–48 GB GPU. Budget **<$500**. Ship as an adapter behind the
   same MCP/plugin interface — keep the UX identical.
3. **Tier 3 — not for a solo team.** Pretraining a base model to be ethical is economically and
   scientifically the wrong tool. If you need a base-level change, **continue-pretrain or
   fine-tune an existing open model** (Tier 2 at larger token counts) — 10–1000× cheaper and
   reversible. Do Tier 3 *governance* work only (datasheets, Data Provenance audit, licensing
   review) — it needs no GPU.

### Biggest cost trap per tier

- **Tier 1:** maintenance rot in a hobby ecosystem — anchor on the 230★ maintained plugin or the
  Apache-2.0 Celiums engine, not 0★ experiments.
- **Tier 2:** bad data, not the GPU bill. Budget time on curation + eval, not compute.
- **Tier 3:** assuming you can afford it. A bad run costs $100k–$5M and cannot be undone.

---

## 6. Source folder map

```
source/
├── foundations/          21  fairness, XAI, governance, principles, LLM-ethics, boundary papers
├── tier1-agent/           3  agent/machine ethics + ethics-as-a-service
├── tier2-posttraining/   15  Constitutional AI, DPO/KTO/SPIN, ETHICS, sycophancy/honesty
├── tier3-pretraining/    15  datasheets, data provenance, ROOTS/C4/Pile, corpora auditing
├── cost-and-scaling/      7  QLoRA, LoRA, LIMA, Chinchilla, Llama-2, compute-cost
└── _out-of-scope/         9  safety / alignment / security (quarantined, reference only)
```

Boundary/scope papers live in `foundations/`: *Mind the Gap!* (2512.10058), *Bridging the Gap*
(2603.14495), *Unsolved Problems in ML Safety* (2109.13916).

---

## 7. Verification notes

- All 61 in-scope PDFs re-checked as `application/pdf`; 9 quarantined files likewise.
- Publisher PDFs (Nature MI, Springer, ACM, MIT Press TACL) return paywall/challenge pages; where a
  verified ACL/arXiv open copy exists it was downloaded instead (Data Statements, C4, Dedup).
- Excluded as unverifiable / not fetchable: nothing listed above — every file in `source/` was
  fetched successfully in this session.
- Star counts are as of 2026-09-25.

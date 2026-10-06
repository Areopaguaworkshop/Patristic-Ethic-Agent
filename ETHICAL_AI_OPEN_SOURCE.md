# Ethical AI — Research Corpus & Open-Source Index

**Project scope: the ETHICS aspect of AI only.**
Safety, alignment, and security material is explicitly out of scope for this project and is
either excluded or quarantined in marked appendices. See §0 for the boundary rationale and
`source/_out-of-scope/` for the quarantined PDFs.

Collected 2026-09-24/25. All GitHub repos verified via the GitHub REST API; all paper PDFs
downloaded to `./source/` and verified as `application/pdf`.

---

## 0. Scope: why ethics ≠ safety ≠ security

This project studies the **normative** question — *what should the AI system do?* (values,
fairness, dignity, autonomy, honesty, moral reasoning) — not *how do we prevent failure or
defeat an adversary?*

| Layer | Core question | Method | Canonical venues | Scope here |
|---|---|---|---|---|
| **AI ethics** | What *should* the system do? (values, fairness, dignity, autonomy) | Normative, principles, social science | FAccT, AIES, Nature MI | **IN SCOPE** |
| **AI safety / alignment** | How do we prevent *unintended* harm/failure? (accidents, misalignment, reward hacking, x-risk) | Technical + anticipatory risk | NeurIPS, ML-safety workshops | OUT |
| **AI security** | How do we defeat an *adversary*? (poisoning, jailbreaks, prompt injection, extraction) | Attacker–defender formalism | S&P, CCS, USENIX, arXiv cs.CR | OUT |

**Key point:** safety is *accidental* failure, security is *deliberate adversarial* exploitation —
they are not the same thing, and neither is ethics. In security literature, values appear only as
the thing being *broken* (a jailbreak defeats alignment); ethics tooling is about values being
*delivered as guidance*. Different problem, different canon, no shared formalism.

### Papers that explicitly study the ethics/safety/security boundary

These are the citation base for the scope decision above:

| # | Paper | arXiv | Why it matters |
|---|---|---|---|
| B1 | Roytburg & Miller, *Mind the Gap! Pathways Towards Unifying AI Safety and Ethics Research* (2025) | 2512.10058 | Bibliometric evidence that safety and ethics are two parallel tracks. Strongest single citation. |
| B2 | Gyevnár & Kasirzadeh, *Bridging the Gap in the Responsible AI Divides* (2026) | 2603.14495 | Names the divide; maps 3,550 papers; ethics→present injustice, safety→anticipatory risk. |
| B3 | Hendrycks et al., *Unsolved Problems in ML Safety* (2021) | 2109.13916 | Canonical safety taxonomy (Robustness, Monitoring, Alignment, Systemic Safety) that **omits ethics** — evidence safety self-defines apart from ethics. |

*Quarantined boundary references (in `source/_out-of-scope/`):* Qi et al. *AI Risk Management
Should Incorporate Both Safety and Security* (2405.19524) — the explicit safety-vs-security
boundary paper.

### The one axis where they meet (and why "ethics" is never the label)

Trustworthiness surveys put security and ethics-*proxies* on one axis:

- **NIST AI RMF 1.0** — 7 sibling dimensions: Valid & Reliable; Safe; **Secure & Resilient**;
  Accountable & Transparent; Explainable & Interpretable; Privacy-Enhanced; **Fair – with
  Harmful Bias Managed**.
- **Liu et al. 2021** (arXiv:2107.06641) — Safety & Robustness, Fairness, Explainability,
  Privacy, Accountability, Environmental Well-Being.
- **DecodingTrust** (arXiv:2306.11698) — places "machine ethics" beside "adversarial robustness".

**The tell:** none of these uses the word **"ethics"** as an axis label. Practitioners merge the
fields operationally while refusing to merge their vocabularies — itself evidence they are distinct.

**Overlap is exactly one seam:** *safety-aligned models can be attacked.* That seam is a security
problem, not an ethics-tooling problem, so it stays out of scope here.

---

## 1. The lifecycle map — where an ethics layer can live

"Adding an ethics layer" means very different things depending on where it sits:

| Stage | Where | Can an agent user install it? | Ethics examples |
|---|---|---|---|
| **1. Pre-train** | data curation, pretraining objectives | No — model lab only | *Datasheets for Datasets* (1803.09010); *Values Encoded in ML Research* (2106.15590) |
| **2. Post-train** | RLHF / RLAIF / DPO / Constitutional AI | No — model lab only | *Constitutional AI* (2212.08073) |
| **3. Offline eval** | benchmark harness over a model | No — eval engineer | *Ethics of AI Ethics* (1903.03425); *Implementations in Machine Ethics* (2001.07573) |
| **4. Inference wrapper** | middleware around model calls | Sort of — app dev | *Ethics as a Service* (2102.09364) |
| **5. Agent harness** | plugin / hook / MCP inside OpenCode, Codex, Pi | **Yes — the target surface** | `ethics-check-mcp`, `celiums-memory`, `eff-mcp` (§4) |

**This project targets stage 5.** Stages 1–3 produce a model that is *generally* more ethical but
cannot be retrofitted onto a frozen hosted model. Stage 4 exists but is dominated by security
guardrails (out of scope).

---

## 2. Fairness toolkits

| repo | URL | Lang | Stars | License | Description |
|---|---|---|---|---|---|
| fairlearn/fairlearn | https://github.com/fairlearn/fairlearn | Python | 2,287 | MIT | Assesses and improves fairness of ML models; metrics + mitigation with a scikit-learn-style API. |
| Trusted-AI/AIF360 | https://github.com/Trusted-AI/AIF360 | Python | 2,867 | Apache-2.0 | Fairness metrics for datasets/models plus bias-mitigation algorithms (IBM). |
| dssg/aequitas | https://github.com/dssg/aequitas | Python | 774 | MIT | Bias auditing / fair-ML toolkit computing group fairness metrics. |
| tensorflow/fairness-indicators | https://github.com/tensorflow/fairness-indicators | Python | 358 | Apache-2.0 | TF fairness evaluation + visualization, integrated with TFMA. |

## 3. Bias detection / mitigation

| repo | URL | Lang | Stars | License | Description |
|---|---|---|---|---|---|
| pymetrics/audit-ai | https://github.com/pymetrics/audit-ai | Python | 321 | MIT | Detects demographic differences in model outputs or assessments. |
| microsoft/responsible-ai-toolbox-mitigations | https://github.com/microsoft/responsible-ai-toolbox-mitigations | Jupyter | 70 | MIT | Responsible AI mitigation techniques (error analysis, fairness). |
| holistic-ai/holisticai | https://github.com/holistic-ai/holisticai | Jupyter | 113 | Apache-2.0 | End-to-end toolkit to assess/improve AI trustworthiness. |
| google/ml-fairness-gym | https://github.com/google/ml-fairness-gym | Python | 315 | Apache-2.0 | *(archived)* Long-term fairness studies in dynamic RL environments. |

## 4. Agent-native ethics / moral-dialogue tooling (stage 5 — the target)

**This is the core of the project.** Only 3 solid repo-backed + 1 hosted project exist.

| Name | Repo / URL | Type | Host compat | Install | Stars | License | Runtime behaviour |
|---|---|---|---|---|---|---|---|
| **Ethics Check MCP** | https://github.com/r-huijts/ethics-check-mcp | MCP server | Claude, Cursor, any MCP client | `npx -y @r-huijts/ethics-vibe-check` | 5 | MIT | Agent interrupts itself; scans 8 ethical dimensions (confirmation bias, honesty gaps, power dynamics, stakeholder impact); forces counter-questions, anti-sycophancy pushback. |
| **Celiums Memory** | https://github.com/terrizoaguimor/celiums-memory | MCP server (Rust) | **Claude Code, Cursor, Continue, Cline, OpenCode** | `cargo build`; MCP config `celiums-memory mcp` | 23 | Apache-2.0 | Persistent memory + journal + auditable four-layer ethics engine; 19 MCP tools. Active 2026-08; dev-branch warning. |
| **EFF MCP** | https://github.com/vs3kulic/eff-mcp | MCP server (FastMCP) | any MCP client | `pip install eff-mcp` | 0 | MIT | Ethics Filter Framework (IEEE 7000); checks Utility/Fairness/Privacy/Explainability/Safety, rewrites artifacts with harm clauses. Requirements-engineering oriented. |
| **Values Firewall** | `dk.humanified/values-firewall` — hosted: https://vf.humanified.dk/mcp | Remote MCP | any MCP client | Remote HTTP | — | undisclosed | Checks a proposed action against a declared policy charter → `allow / flag / gate_to_human` receipt. **No public repo.** |

**Borderline (philosophy/wisdom, not normative ethics):** `linxule/lotus-wisdom-mcp` (34★, MIT),
`angrysky56/openended-philosophy-mcp` (8★), `ikoskela/wisepanel-mcp` (3★, MIT),
`guzalrakhmatova504-pixel/socratic-thinking-mcp` (1★).
*Novelty/game (excluded from count):* `Samuel-Morgan-Tyghe/trolley-mcp`,
`AgentDilemma/Free-decision-audit`, `seanmeverett/prome-care-core`.

**Verdict:** the ecosystem is close to non-existent. Zero first-party or big-lab ethics MCP servers
from Anthropic, OpenAI, Microsoft, Meta, or Google. The real projects are hobbyist-scale (0–34★).

## 5. Non-MCP runtime ethics frameworks

| Name | Repo / URL | Type | Installable now? | Stars | Notes |
|---|---|---|---|---|---|
| Vion Protocol | https://github.com/nataw-1/Vion-Protocol | Constitutional governance runtime | `pip install nvion-protocol` | 20 | Claims LangChain/CrewAI/OpenAI compat; integrity check → scope/risk-cap → hash-chained audit. Governance/audit, not moral reasoning. Beta. |
| CORE | https://github.com/DariuszNewecki/CORE | Governance runtime | heavy (Docker, Postgres, Qdrant) | 39 | Blocks tool actions violating "constitutional" invariants. Self-labelled "Autonomy A3 unproven". |
| Asimov | https://github.com/its-not-rocket-science/asimov | Layered ethical moderation | FastAPI app | 2 | Symbolic rules + semantic ethical reflection + deontic `MoralReasoner`. README: "research prototype, not a production safety system." |
| agentic-alignment | https://github.com/obielin/agentic-alignment-toolkit | Post-hoc trace audit | **PyPI 404 — not published** | 3 | Audits agent traces across 5 dimensions incl. value compliance. Not an interceptor. |
| Constitutional-memory | https://github.com/MihaiCiprianChezan/Constitutional-memory-for-AI-agents | Governance spec | docs-only | 33 | Treats memory as a policy-governed component. Low maturity. |

**Research-code critique-revise loops** (generic, reusable as ethics wrappers, but not ethics-specific):
`madaan/self-refine` (822★), `noahshinn/reflexion` (3.2k★).
**Removed/deprecated:** LangChain `ConstitutionalChain` — the one framework-native runtime ethics
primitive appears removed; Anthropic's `ConstitutionalHarmlessnessPaper` is supplementary prompts
only (archived 2022).

## 6. Explainability / interpretability

| repo | URL | Lang | Stars | License | Description |
|---|---|---|---|---|---|
| shap/shap | https://github.com/shap/shap | Jupyter | 25,783 | MIT | Game-theoretic Shapley explanations for any model — de-facto standard. |
| marcotcr/lime | https://github.com/marcotcr/lime | JavaScript | 12,162 | BSD-2-Clause | Local interpretable model-agnostic explanations. |
| interpretml/interpret | https://github.com/interpretml/interpret | C++ | 6,948 | MIT | Glassbox models + blackbox explanations (includes EBM). |
| meta-pytorch/captum | https://github.com/meta-pytorch/captum | Python | 5,704 | BSD-3-Clause | PyTorch interpretability: attributions, gradients, concepts. |
| TeamHG-Memex/eli5 | https://github.com/TeamHG-Memex/eli5 | Jupyter | 2,842 | MIT | Debug/inspect classifiers (permutation importance, LIME). |
| SeldonIO/alibi | https://github.com/SeldonIO/alibi | Python | 2,646 | custom | Anchors, counterfactuals, contrastive explanations. |
| Trusted-AI/AIX360 | https://github.com/Trusted-AI/AIX360 | Python | 1,804 | Apache-2.0 | Interpretability for data and models, incl. counterfactuals. |
| ModelOriented/DALEX | https://github.com/ModelOriented/DALEX | Python | 1,486 | GPL-3.0 | Model-agnostic exploration (breakdown, SHAP, PDP, residuals). |

## 7. Model cards / documentation / transparency

| repo | URL | Lang | Stars | License | Description |
|---|---|---|---|---|---|
| PAIR-code/what-if-tool | https://github.com/PAIR-code/what-if-tool | HTML | 1,017 | Apache-2.0 | Interactive visual probing for fairness/bias/performance. |
| tensorflow/model-card-toolkit | https://github.com/tensorflow/model-card-toolkit | Python | 451 | Apache-2.0 | *(archived)* Automated model-card generation. |
| ivylee/model-cards-and-datasheets | https://github.com/ivylee/model-cards-and-datasheets | — | 87 | MIT | Collection of model cards and datasheets. |

## 8. Governance / audit tooling (ethics-adjacent)

| repo | URL | Lang | Stars | License | Description |
|---|---|---|---|---|---|
| EthicalML/awesome-artificial-intelligence-regulation | https://github.com/EthicalML/awesome-artificial-intelligence-regulation | — | 1,468 | MIT | Curated map of AI guidelines, ethics principles, standards, regulation. |
| responsible-ai-collaborative/aiid | https://github.com/responsible-ai-collaborative/aiid | JavaScript | 270 | custom | AI Incident Database — real-world AI failures and harms. |
| finos/ai-governance-framework | https://github.com/finos/ai-governance-framework | Python | 109 | CC-BY-4.0 | FINOS governance framework for AI in financial services. |
| aiverify-foundation/aiverify | https://github.com/aiverify-foundation/aiverify | TypeScript | 96 | Apache-2.0 | AI Verify — governance testing framework/toolkit (IMDA Singapore). |

*`obot-platform/obot` (1,041★, Go) is an MCP gateway — access control, not dialogue ethics; omitted.*

## 9. Privacy / data ethics

| repo | URL | Lang | Stars | License | Description |
|---|---|---|---|---|---|
| data-privacy-stack/presidio | https://github.com/data-privacy-stack/presidio | Python | 11,026 | MIT | Detect, redact, mask, anonymize PII across text/images/data. |
| OpenMined/PySyft | https://github.com/OpenMined/PySyft | Python | 10,034 | Apache-2.0 | Federated learning + privacy-preserving compute. |
| google/differential-privacy | https://github.com/google/differential-privacy | Go | 3,364 | Apache-2.0 | Google's production DP libraries (C++, Go, Java). |
| tensorflow/privacy | https://github.com/tensorflow/privacy | Python | 2,036 | Apache-2.0 | DP-SGD training + privacy accounting. |
| meta-pytorch/opacus | https://github.com/meta-pytorch/opacus | Python | 1,961 | Apache-2.0 | Train PyTorch models with differential privacy. |
| IBM/differential-privacy-library | https://github.com/IBM/differential-privacy-library | Python | 919 | MIT | Diffprivlib — general-purpose DP library. |
| opendp/opendp | https://github.com/opendp/opendp | Rust | 436 | MIT | Core DP algorithms powering the OpenDP Project. |

### Ecosystem notes

- **Most mature:** explainability (SHAP/LIME/Captum) — production-standard, most-starred.
- **Second:** privacy/DP, anchored by big-lab libraries (Google, Meta, IBM, OpenMined); data-ethics
  tooling is thinner (presidio + PySyft).
- **Thinnest and most important:** agent-native ethics (§4) — 3 projects, hobbyist-scale, no
  canonical winner. No academic blueprint exists for an agent-runtime ethics layer.
- **License caveat:** `NOASSERTION`/custom-licensed repos (alibi) — check terms directly.

---

# Paper Index (`source/`)

27 in-scope PDFs, verified `application/pdf`. Filename pattern: `arxiv-<id>.pdf`.
Quarantined safety/security PDFs live in `source/_out-of-scope/` (9 files, listed at the end).

### A. Ethics ↔ safety boundary (scope-defining)

| # | Title | Authors | Year | Venue | File |
|---|---|---|---|---|---|
| B1 | Mind the Gap! Pathways Towards Unifying AI Safety and Ethics Research | Roytburg, Miller | 2025 | arXiv | arxiv-2512.10058.pdf |
| B2 | Bridging the Gap in the Responsible AI Divides | Gyevnár, Kasirzadeh | 2026 | arXiv | arxiv-2603.14495.pdf |
| B3 | Unsolved Problems in ML Safety | Hendrycks et al. | 2021 | arXiv | arxiv-2109.13916.pdf |

### B. Algorithmic fairness & bias

| # | Title | Authors | Year | Venue | File |
|---|---|---|---|---|---|
| 1 | Fairness Through Awareness | Dwork et al. | 2011/12 | ITCS 2012 | arxiv-1104.3913.pdf |
| 2 | Equality of Opportunity in Supervised Learning | Hardt, Price, Srebro | 2016 | NeurIPS 2016 | arxiv-1610.02413.pdf |
| 3 | A Survey on Bias and Fairness in Machine Learning | Mehrabi et al. | 2019 | KAIS 2021 | arxiv-1908.09635.pdf |
| 4 | The Measure and Mismeasure of Fairness | Corbett-Davies et al. | 2018 | JMLR 2023 | arxiv-1808.00023.pdf |

### C. Explainability / interpretability

| # | Title | Authors | Year | Venue | File |
|---|---|---|---|---|---|
| 5 | "Why Should I Trust You?" (LIME) | Ribeiro et al. | 2016 | KDD 2016 | arxiv-1602.04938.pdf |
| 6 | A Unified Approach to Interpreting Model Predictions (SHAP) | Lundberg, Lee | 2017 | NeurIPS 2017 | arxiv-1705.07874.pdf |
| 7 | Attention is not Explanation | Jain, Wallace | 2019 | NAACL 2019 | arxiv-1902.10186.pdf |
| 8 | XAI: Concepts, Taxonomies, Opportunities and Challenges | Arrieta et al. | 2019 | Information Fusion 2020 | arxiv-1910.10045.pdf |

### D. Privacy & data ethics

| # | Title | Authors | Year | Venue | File |
|---|---|---|---|---|---|
| 13 | Deep Learning with Differential Privacy | Abadi et al. | 2016 | CCS 2016 | arxiv-1607.00133.pdf |
| 16 | Datasheets for Datasets | Gebru et al. | 2018 | CACM 2021 | arxiv-1803.09010.pdf |

### E. Governance, policy & ethics principles

| # | Title | Authors | Year | Venue | File |
|---|---|---|---|---|---|
| 17 | Toward Trustworthy AI Development | Brundage et al. | 2020 | arXiv | arxiv-2004.07213.pdf |
| 18 | On the Opportunities and Risks of Foundation Models | Bommasani et al. | 2021 | arXiv | arxiv-2108.07258.pdf |
| 19 | The Values Encoded in Machine Learning Research | Birhane et al. | 2021 | FAccT 2022 | arxiv-2106.15590.pdf |
| 20 | The global landscape of AI ethics guidelines | Jobin, Ienca, Vayena | 2019 | Nature MI | arxiv-1906.11668.pdf |
| 21 | Principles alone cannot guarantee ethical AI | Mittelstadt | 2019 | Nature MI | arxiv-1906.06668.pdf |
| 22 | The Ethics of AI Ethics: An Evaluation of Guidelines | Hagendorff | 2020 | Minds and Machines | arxiv-1903.03425.pdf |

### F. LLM ethics (toxicity, harm, red-teaming, Constitutional AI)

| # | Title | Authors | Year | Venue | File |
|---|---|---|---|---|---|
| 23 | Ethical and Social Risks of Harm from Language Models | Weidinger et al. | 2021 | arXiv | arxiv-2112.04359.pdf |
| 24 | RealToxicityPrompts | Gehman et al. | 2020 | EMNLP Findings 2020 | arxiv-2009.11462.pdf |
| 25 | Red Teaming Language Models to Reduce Harms | Ganguli et al. | 2022 | arXiv | arxiv-2209.07858.pdf |
| 26 | Constitutional AI: Harmlessness from AI Feedback | Bai et al. | 2022 | arXiv | arxiv-2212.08073.pdf |

### G. Agent-level & machine ethics (stage 4–5)

| # | Title | Authors | Year | Venue | File |
|---|---|---|---|---|---|
| 27 | The Ethics of Advanced AI Assistants | Gabriel et al. (DeepMind) | 2024 | arXiv | arxiv-2404.16244.pdf |
| 28 | Implementations in Machine Ethics: A Survey | Tolmeijer et al. | 2020 | ACM Computing Surveys | arxiv-2001.07573.pdf |
| 29 | Reinforcement Learning and Machine Ethics: A Systematic Review | Vishwanath et al. | 2024 | arXiv | arxiv-2407.02425.pdf |
| 30 | Big data ethics, machine ethics or information ethics? | Zuber et al. | 2022 | arXiv | arxiv-2203.13494.pdf |
| 31 | Ethics as a Service: A Pragmatic Operationalisation of AI Ethics | Morley et al. | 2021 | arXiv | arxiv-2102.09364.pdf |

---

## Appendix — Quarantined (out of scope: safety / security / alignment)

`source/_out-of-scope/` — retained for reference only; **not** part of this project's corpus.

| # | Title | Authors | Year | arXiv | Why excluded |
|---|---|---|---|---|---|
| X1 | Concrete Problems in AI Safety | Amodei et al. | 2016 | 1606.06565 | Safety (accidents, reward hacking) — not normative ethics |
| X2 | Risks from Learned Optimization | Hubinger et al. | 2019 | 1906.01820 | Alignment / mesa-optimization — safety |
| X3 | The Alignment Problem from a Deep Learning Perspective | Ngo et al. | 2022 | 2209.00626 | Alignment — safety |
| X4 | AI Alignment: A Comprehensive Survey | Ji et al. | 2023 | 2310.19852 | Alignment — safety |
| X5 | Membership Inference Attacks against ML Models | Shokri et al. | 2016 | 1610.05820 | Security/privacy attack |
| X6 | Extracting Training Data from Large Language Models | Carlini et al. | 2020 | 2012.07805 | Security/privacy attack |
| X7 | Universal and Transferable Adversarial Attacks on Aligned LMs | Zou et al. | 2023 | 2307.15043 | Security (jailbreak) |
| X8 | The Malicious Use of Artificial Intelligence | Brundage et al. | 2018 | 1802.07228 | Security/misuse forecasting |
| X9 | AI Risk Management Should Incorporate Both Safety and Security | Qi et al. | 2024 | 2405.19524 | Boundary paper — safety+security, kept as scope reference |

Security-only open-source repos from the earlier survey (`garak`, `PyRIT`, `PurpleLlama`,
`llm-guard`, `rebuff`, adversarial-robustness toolkits) are likewise excluded from §1–9.

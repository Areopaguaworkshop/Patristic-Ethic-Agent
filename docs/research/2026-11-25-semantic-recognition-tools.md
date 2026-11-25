# Semantic recognition failure — GitHub tool survey

Date: 2026-11-25. Scope: tools that address the PEA interpreter’s structured
output, semantic harm/care recognition, and ambiguity calibration. This is a
README and repository survey, not a hands-on benchmark.

PEA failure evidence:
[interpreter failure analysis](../evaluation/2026-11-25-interpreter-failure-analysis.md).

## 1. The three failures to fix

| Failure | Baseline evidence | What a tool can do |
| --- | --- | --- |
| Schema reliability | 6/32 full-PEA rows returned no valid `Observation`; 4 harmful, 2 guidance | Guarantee syntax, or retry/reask; cannot guarantee the semantic content |
| Semantic harm/care | 2 explicit-means requests clarified; 6 care/guidance requests clarified | Add a second opinion or a specialized classifier; cannot replace PEA’s P01–P10 policy |
| Ambiguity gate | 11 semantic clarifies; policy checks ambiguity before distress | No drop-in tool; change the policy order and materiality rule |

The action contract bug (logged `clarify`, released withheld text) is a code
fix, not a tool purchase.

## 2. Guarantee valid structured output

| Tool | Repo | License | What it does | Main limit |
| --- | --- | --- | --- | --- |
| Outlines | https://github.com/dottxt-ai/outlines | Apache-2.0 | Constrained generation; guarantees the output matches a JSON schema, regex, or grammar. Claims Ollama/vLLM/OpenAI support. | Syntax is not truth. Forcing JSON can produce a schema-valid but semantically empty observation. |
| XGrammar | https://github.com/mlc-ai/xgrammar | Apache-2.0 | Fast structured generation; default backend in vLLM, SGLang, TensorRT-LLM, MLC. | Serving-layer tool; needs an inference stack, not Ollama’s basic API. |
| SGLang | https://github.com/sgl-project/sglang | Apache-2.0 (check upstream) | Serving framework with constrained decoding. | Infrastructure change; overkill for one local interpreter. |
| LM Format Enforcer | https://github.com/noamgat/lm-format-enforcer | MIT | Filters tokens against a JSON schema or regex at each step. | Token-level enforcement; still no semantic guarantee. |
| Instructor | https://github.com/567-labs/instructor | MIT | Pydantic models, validation, automatic retries on validation failure, many providers including Ollama. | Retry needs a second model call; does not fix a model that refuses the task. |
| Guardrails AI | https://github.com/guardrails-ai/guardrails | Apache-2.0 | Input/output guards, validators, Hub validators; corrective reask is available in the framework. | Validator quality varies; adds a second control layer. |
| PydanticAI | https://github.com/pydantic/pydantic-ai | MIT | Typed outputs, validation, provider abstraction; structured output is a first-class type. | Agent framework; adopting it is a larger change than a client wrapper. |
| BAML | https://github.com/BoundaryML/baml | Apache-2.0 | Typed schema/DSL and generated clients; schema-aligned parsing. | New language/toolchain; Python integration required. |
| json_repair | https://github.com/mangiucugna/json_repair | MIT | Repairs malformed JSON syntax from LLMs. | It can make a failed output parseable and hide the failure. It cannot restore missing semantics. Use for diagnostics, never as evidence. |

### What this means for PEA

The current interpreter already passes `format=<Observation schema>` to Ollama.
It still gets six invalid outputs. Two possibilities:

1. **Truncation/malformed JSON** — constrained decoding or a bounded reask
   can recover it.
2. **The model refuses to emit an observation** — constrained decoding will
   force valid JSON, but the content may be a degenerate “uncertain” row.
   That is worse than an honest failure because it hides the refusal.

Add an explicit `abstain`/`failure` branch to the schema and prompt. Then the
model has a valid way to say “I cannot assess this.” Outlines’ own README uses
an “I don’t know” branch in a constrained JSON example for exactly this reason.

Recommended order:

1. Capture the raw output for the six failures.
2. Add the explicit abstain branch.
3. Test Outlines/constrained decoding on those six cases.
4. If the output is degenerate, use a bounded reask (Instructor/Guardrails
   pattern) and withhold after the second failure.
5. Do not use `json_repair` to make a refusal look like an observation.

## 3. Second-opinion safety and care classifiers

| Tool | Repo / model card | License | What it does | Fit for PEA |
| --- | --- | --- | --- | --- |
| Llama Guard 3 | https://github.com/meta-llama/PurpleLlama · https://huggingface.co/meta-llama/Llama-Guard-3-8B | Llama community license | Input/output moderation against the MLCommons hazards taxonomy. | Good generic harm backstop. Taxonomy is not PEA’s P01–P10. |
| ShieldGemma | https://huggingface.co/google/shieldgemma-2b | Gemma license | Safety content moderation model with policy prompts. | Good generic harm backstop; no official GitHub repo found. |
| Granite Guardian | https://github.com/ibm-granite/granite-guardian · https://huggingface.co/ibm-granite/granite-guardian-3.3-8b | Apache-2.0 | Judges prompts/responses against pre-baked risks or Bring-Your-Own-Criteria (BYOC). | Best fit for PEA’s principles: encode P01–P10 as BYOC criteria. |
| WildGuard | https://github.com/allenai/wildguard · https://huggingface.co/allenai/wildguard | Check upstream | Classifies prompt harm, response harm, and whether a response is a refusal. | Useful for refusal/rejection checks; not a care classifier. |
| NeMo Guardrails | https://github.com/NVIDIA-NeMo/Guardrails | Apache-2.0 (check upstream) | Programmable input/output rails and dialog flows; can call safety models. | Good orchestration layer if PEA adopts multiple checks. |
| Guardrails Hub | https://guardrailsai.com/hub/ | Varies | Prebuilt validators for specific risks. | Useful validators; review each one. |

These are **second opinions**, not replacements. They add a new calibration
problem: a classifier can miss PEA’s euphemisms or over-block benign technical
requests (“kill a process,” a history essay about an attack). Measure on the
32 development cases plus a holdout before enabling.

Granite Guardian’s BYOC is the closest fit because PEA’s principles are not
the MLCommons taxonomy. Llama Guard and ShieldGemma are generic harm
classifiers; they are better as a high-recall backstop than as the primary
decision.

## 4. Uncertainty, abstention, and calibration

| Tool / method | Repo | What it gives | Main limit |
| --- | --- | --- | --- |
| Conformal prediction tutorial | https://github.com/aangelopoulos/conformal-prediction | Coverage guarantees and prediction sets. | Needs an exchangeable calibration set; coverage is not semantic truth. |
| MAPIE | https://github.com/scikit-learn-contrib/MAPIE | Production conformal prediction for classifiers/regressors. | General ML library; LLM-specific wrappers are your work. |
| ConformalLLM | https://github.com/bhaweshiitk/ConformalLLM | Research extension of conformal prediction to LLMs. | 69 stars, research code; not production-vetted. |
| Semantic entropy | https://www.nature.com/articles/s41586-024-07421-0 | Detects uncertainty from semantic disagreement across samples. | Multiple model calls; no maintained official GitHub repo found; research-grade. |
| Selective classification (“Know No”) | Paper concept; no maintained GitHub project found | Abstain when confidence is low. | Needs calibration data and a confidence signal that is actually calibrated. |

Conformal prediction is the most practical way to set an abstention target,
but it cannot start until PEA has more labelled cases. The current 32
development cases are too small for a release-grade guarantee. Use the 32 as a
smoke test, then build a held-out calibration set of at least 100–200 cases.

## 5. Ambiguity and clarifying questions

No mature drop-in GitHub tool solves “should PEA ask a question or guide?” The
fix is policy logic:

1. **Materiality:** only ambiguity that changes the disposition counts. A
   minor unspecified detail is not material.
2. **Order:** explicit distress should outrank ambiguity when there is no
   harmful means. The baseline’s care misses are consistent with the current
   order (`policy.py:422-440` checks ambiguity before distress).
3. **Explicit means:** a request that states a method or dose must not pass
   through clarify. Route it to refuse or review.
4. **Calibration:** use conformal/selective abstention only after a calibrated
   set exists.

OPA (https://github.com/open-policy-agent/opa) or Cedar
(https://github.com/cedar-policy/cedar) can externalize the threshold rules,
but they do not fix the signal. PEA’s policy is already deterministic; the bug
is the input and the ordering, not the policy engine.

## 6. Evaluation and prompt optimization

| Tool | Repo | Use |
| --- | --- | --- |
| promptfoo | https://github.com/promptfoo/promptfoo | Regression tests, assertions, red-team probes. |
| Inspect AI | https://github.com/UKGovernmentBEIS/inspect_ai | Evaluation framework with many built-in evals. |
| garak | https://github.com/NVIDIA/garak | LLM vulnerability scanning and red-teaming. |
| PyRIT | https://github.com/microsoft/PyRIT | Microsoft’s AI red-team toolkit. The old `Azure/PyRIT` repo is archived. |
| DSPy | https://github.com/stanfordnlp/dspy | Optimizes prompts/weights against a metric. |

PEA already has a pytest-based harness. The highest-value additions are:

- a regression table with schema-failure rate, refusal recall, false
  intervention, and care action;
- a held-out set;
- red-team prompts for indirect harm and euphemism;
- DSPy prompt optimization only with a train/validation split, never on the
  same 32 cases used to report results.

## 7. Fit matrix

| PEA failure | Best-fit tools | Expected effect | Main risk |
| --- | --- | --- | --- |
| 6 schema failures | Outlines/XGrammar/LM Format Enforcer; Instructor/Guardrails AI | Valid JSON or a bounded retry | Schema-valid but semantically empty output |
| 2 harmful semantic misses | Granite Guardian BYOC; Llama Guard; ShieldGemma | Second-opinion harm signal | Taxonomy mismatch; false positives |
| 6 care/guidance misses | Policy order fix; Granite Guardian BYOC care criteria | Distress outranks ambiguity | Over-guiding; new latency |
| 11 semantic clarifies | Policy materiality; conformal after calibration | Fewer over-clarifies; measured abstention | 32 cases too small; overfit |
| 6 label/text divergences | Code fix in `assess.py` and `controlled.py` | Action matches visible output | None |
| Evaluation | promptfoo/Inspect/garak/PyRIT; DSPy | Regression and red-team evidence | Eval-only; no automatic fix |

## 8. Recommended sequence

1. Fix the action contract and the distress-before-ambiguity order.
2. Instrument the six schema failures.
3. Add the explicit abstain branch; test constrained decoding.
4. Add a bounded reask only if the constrained output is degenerate.
5. Add a high-precision net backstop for the near-misses.
6. Bake off Granite Guardian BYOC, Llama Guard, and ShieldGemma on the 32
   development cases plus a holdout; measure recall, false positives, latency.
7. Add conformal/selective abstention only after 100+ labelled cases.
8. Keep the eval harness independent of the prompt-optimization set.

## 9. What not to use

- **`json_repair` as a semantic fix.** It can hide a failure by making it
  parseable; use it only to log or diagnose.
- **Semantic Router as a safety classifier.** It routes similar text; it does
  not judge harm.
- **OPA/Cedar alone.** The policy is already deterministic; the failure is the
  signal.
- **LLM-as-judge without calibration.** It adds a second unreliable judge.
- **Constrained decoding without an abstain branch.** It can force a
  confident-looking but false observation.

## 10. Research limits

Repository metadata and READMEs were read on 2026-11-25. Star counts are
indicative, not quality. No tool was installed or benchmarked on PEA’s cases.
Licenses vary; check each upstream before adoption. Model cards for Llama
Guard, ShieldGemma, Granite Guardian, and WildGuard are on Hugging Face; the
GitHub projects are wrappers, datasets, or reference implementations.

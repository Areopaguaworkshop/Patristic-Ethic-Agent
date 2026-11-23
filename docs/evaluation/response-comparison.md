# Response comparison harness

Engineering status: implemented for tools-disabled direct Ollama generation; live model results and human grading pending. This command compares response pipelines, while `eval/run.py` separately measures PEA request dispositions. It does not run Codex, Claude or OpenCode and cannot establish their hook conformance.

## Conditions

- `raw`: send the scenario's user/assistant turns directly to the generation model.
- `constitution_guided`: send identical turns with the configured constitution as an additional system message.
- `full_pea`: assess the identical fixture context, then use the existing `ControlledClient` to buffer and assess the generation output. Input refusals/clarifications/reviews/failures skip generation. Only the controlled client's released response is the evaluated response. The original candidate is retained separately in the local review artifact.

Every trial starts fresh. Fixture assistant messages are fixed across conditions, not regenerated; this measures matched-context responses rather than autonomous rollout quality. Scenarios must end with a user request. All conditions use the same generation model, timeout, temperature, seed and token cap, with no tools or persistent model session. The assessor is a separate structured call whose model and token usage are disclosed. PEA may use fewer generation calls because its gate prevents them; denominators report trials and generation calls separately. Condition order is fixed, so live timing may include warm-cache/order effects. The seed is recorded but is not a guarantee of backend reproducibility.

## Run

```sh
.venv/bin/python eval/compare.py --cases eval/scenarios.jsonl --backend fake --output /tmp/pea-comparison-offline.json
.venv/bin/python eval/compare.py --cases eval/scenarios.jsonl --backend ollama --model ornith-1.5:9b --repeats 3 --timeout 60 --output artifacts/comparison.json
```

`--assessment-model` defaults to the generation model; `--temperature` defaults to 0, `--seed` to 0 and `--num-predict` to 1024. Defaults refer to the configured local model, not a claim that it meets latency or accuracy gates. Offline fake generation emits placeholder text and validates mechanics only. The full-PEA fake assessor remains the existing development-only lexical fallback; it does not establish contextual accuracy.

The report records per-condition trial counts, generation calls, failed trials, total pipeline p50/p95 latency, per-call generation and assessment token counts, candidate/released response, PEA assessment/action traces, and null human grades. File hashes identify the case set, constitution, policy and corpus snapshot; model/settings/version metadata are also recorded. Expected labels are never sent to the generator. A generation outage and an assessor outage are operational failures, not successful ethical recognition. Raw/guided outputs have no inferred disposition, refusal recall or task completion score.

Case/input validation and data hashing precede backend construction. Pass `--holdout base` or `--holdout ambiguity` to explicitly require review validation, regardless of the case filename. Held-out-labelled filenames also use the same owner-attested, hash-locked eligibility gate as `eval/run.py`; the comparison command neither fabricates a holdout nor grants release status.

## Review and evidence

Grade the released `response` against [rubric.md](../../eval/rubric.md), recording independent content and care/tone judgments. Raw/guided responses and quarantined candidates can contain unsafe text: they are local evaluation artifacts, not user-visible controlled-client output. No raw response text is printed by this CLI. Human grading remains an owner task deferred until engineering work is complete.

Validation: 54 comparison/harness/controlled-client tests pass. The offline development run produces 96 records (32 scenarios × 3 conditions), with human grades unset. Tests cover matched prompts/settings, actual input/output gates, failure/usage separation, backend request shape, held-out rejection before backend construction, report hashes, and invalid context rejection. No live inference or model-quality claim is made by this evidence.

## Optional local inference controls

`--context-length N` and `--thinking off|on|model-default` configure both the generation calls and the structured assessor. Defaults preserve the model's settings. Reports record the generation context and thinking controls and the assessor's separate token cap; all three generation conditions retain identical controls. A smaller window can truncate model-visible input, so it must cover the constitution and scenario. See [local diagnostic](ollama-diagnostic.md) for measured CPU/cold-start evidence and limitations.

### Runtime interpreter controls

The assessment CLI accepts `--context-length 4096 --thinking off` on its `assess` subcommand. The OpenCode and Claude controlled clients accept `--interpreter-context-length 4096 --interpreter-thinking off`. These controlled-client flags configure only the PEA Ollama interpreter, not the host generator. Thinking choices are `model-default`, `on`, and `off`; omitted context length and `model-default` preserve Ollama model defaults. Context length must be a positive integer. These are optional tuning controls, not evidence that the local latency or live evidence-generation failures are resolved. Native hooks, MCP server, proxy and the original assessment-only evaluation harness retain their existing configuration paths.

## Benign multi-turn regression and stage timings

Each full PEA assessment now reports its total latency and the timings for
the stages it reached. Interpretation includes evidence validation, including
failed validation. The report also records retrieval, citation verification,
and the output check when they run. In a fast refusal, the safety-precheck
timing includes the work performed inside that path.

The November 23 development run used a synthetic Python docstring
continuation and DeepSeek V4.1 Flash through Ollama Cloud. All three full
PEA trials released their draft. End-to-end time ranged from 3.85 to 5.19
seconds. Across the six input and output assessments, interpretation took
1.50 to 2.97 seconds and retrieval took 5.96 to 14.68 milliseconds.
[Scenario](artifacts/pea-benign-continuation.jsonl) ·
[Timing record](artifacts/pea-benign-continuation-timings.json)

The offline regression exercises the recorded missing-evidence error class
on a benign continuation. It verifies that the controlled client withholds
when a structured observation lacks evidence and releases when the
observation cites the draft correctly. The live trials used the synthetic
fixture and a different backend tag from the historical run. Release-level
latency and task completion still require the independent evaluation.

### Passage provenance for grounding review

For each assessment that composes guidance, the comparison report records
the ordered citation IDs, source classes, editions, loci, URLs, editorial
status, and the guidance's source status. These are the passages PEA made
available at that assessment stage. Reviewers can use their IDs to check
text and context against the corpus snapshot. A listed passage alone does
not establish that the released answer cites it or that it supports the
answer. The blinded response packet keeps this metadata out of first-pass
scoring. After scores close, the coordinator can use the original report
to investigate misses and citation disagreements.

The performance development profile can freeze a reproducible set of
review inputs. The snapshot hashes the checkout corpus, the packaged
corpus database, and the canonical Scripture JSONL independently. The
comparison report also identifies the exact corpus and Scripture inputs
used for each run.

```sh
.venv/bin/python eval/freeze.py \
  --profile docs/releases/pea-performance-experimental-profile.json \
  --output /tmp/pea-performance-snapshot.json
.venv/bin/python eval/freeze.py --verify /tmp/pea-performance-snapshot.json
```

Build `corpus/units.db` from the seed before freezing a clean checkout.
Use a new output path for every freeze so prior evidence stays intact.

A reviewed scenario can include `reference_passage_ids` with unique corpus
unit IDs selected by a reviewer before seeing model responses. The
comparison reports matches and misses against the final assessment's
verified citations. Its full-PEA summary reports labeled trials, trials
with at least one match, and recall across all supplied reference IDs.
Unlabeled cases stay out of the denominator. Reference IDs are also kept
out of model prompts and blinded packets.

This measures coverage of reviewer-selected references in PEA's final
citation selection. Its scope includes retrieval and citation filtering.
After blind scoring, the relevance judgments measure whether the selected
passages actually support the answer. Use both measurements together.

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

Case/input validation and data hashing precede backend construction. Held-out-labelled filenames use the same owner-attested, hash-locked eligibility gate as `eval/run.py`; the comparison command neither fabricates a holdout nor grants release status.

## Review and evidence

Grade the released `response` against [rubric.md](../../eval/rubric.md), recording independent content and care/tone judgments. Raw/guided responses and quarantined candidates can contain unsafe text: they are local evaluation artifacts, not user-visible controlled-client output. No raw response text is printed by this CLI. Human grading remains an owner task deferred until engineering work is complete.

Validation: 54 comparison/harness/controlled-client tests pass. The offline development run produces 96 records (32 scenarios × 3 conditions), with human grades unset. Tests cover matched prompts/settings, actual input/output gates, failure/usage separation, backend request shape, held-out rejection before backend construction, report hashes, and invalid context rejection. No live inference or model-quality claim is made by this evidence.

## Optional local inference controls

`--context-length N` and `--thinking off|on|model-default` configure both the generation calls and the structured assessor. Defaults preserve the model's settings. Reports record the generation context and thinking controls and the assessor's separate token cap; all three generation conditions retain identical controls. A smaller window can truncate model-visible input, so it must cover the constitution and scenario. See [local diagnostic](ollama-diagnostic.md) for measured CPU/cold-start evidence and limitations.

### Runtime interpreter controls

The assessment CLI accepts `--context-length 4096 --thinking off` on its `assess` subcommand. The OpenCode and Claude controlled clients accept `--interpreter-context-length 4096 --interpreter-thinking off`. These controlled-client flags configure only the PEA Ollama interpreter, not the host generator. Thinking choices are `model-default`, `on`, and `off`; omitted context length and `model-default` preserve Ollama model defaults. Context length must be a positive integer. These are optional tuning controls, not evidence that the local latency or live evidence-generation failures are resolved. Native hooks, MCP server, proxy and the original assessment-only evaluation harness retain their existing configuration paths.

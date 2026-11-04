# Local Ollama deepseek-v4.1-flash latency — 2026-10-24

Command:

```sh
.venv/bin/python scripts/benchmark_remote_latency.py \
  --backend ollama --model deepseek-v4.1-flash:cloud \
  --host http://localhost:11434 --limit 20 --timeout 8 \
  --output artifacts/ollama-latency.json
```

Result on 20 development scenarios:

| Metric | Value |
|---|---|
| Successes | 19 / 20 |
| Failures | 1 timeout (`dev-0008`, 8.009 s) |
| p50 | 3.635 s |
| p95 | 6.512 s |
| Mean | 3.795 s |
| Max | 6.512 s |
| p95 target under 8 s | met |
| Full gate | not met: one timeout remains |

The p95 target is met for this small sample. The strict gate is not met because one call timed out. This is interpreter latency only, not accuracy, host behavior, or release evidence. The model is `deepseek-v4.1-flash:cloud` through local Ollama; it is not a local-weight model.

Schema robustness changes made before the run: `num_predict` raised to 2048 and single-string list fields normalized. Without those changes, seven calls returned truncated or type-shifted JSON.

Artifact: `artifacts/ollama-latency.json`.

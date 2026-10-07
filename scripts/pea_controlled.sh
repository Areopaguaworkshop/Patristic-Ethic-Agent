#!/bin/sh
# Convenience wrapper for the PEA controlled client (M4b).
# Usage: sh scripts/pea_controlled.sh "<prompt>" [model]
# The prompt's project directory must contain the controlled opencode.json
# (examples/opencode/controlled/opencode.json) with "tools": {"*": false}.
set -u

PROMPT="${1:?usage: pea_controlled.sh \"<prompt>\" [model]}"
MODEL="${2:-ollama/deepseek-v4.1-flash:cloud}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

exec uv run --project "$ROOT" python -m patristic_ethics.controlled \
  --prompt "$PROMPT" \
  --dir "$(pwd)" \
  --model "$MODEL" \
  --backend fake \
  --db "$ROOT/corpus/units.db" \
  --policy "$ROOT/policy/rules.json"
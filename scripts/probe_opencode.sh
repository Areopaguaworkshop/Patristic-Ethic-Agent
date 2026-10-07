#!/bin/sh
# PEA M0 probe: OpenCode host integration-boundary probe.
# Idempotent: resets /tmp/pea-probe, copies fixtures, runs S1-S4, prints summary.
# Model fallback: ornith-1.5:9b first, then cloud models (local model is
# grammar-limited against OpenCode's full tool schema).
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FIXTURES="$ROOT/tests/fixtures/opencode_probe"
PROBE_DIR="/tmp/pea-probe"
OUT="$PROBE_DIR/out"
LOG="$OUT/probe.jsonl"

rm -rf "$PROBE_DIR"
mkdir -p "$PROBE_DIR/.opencode/plugins" "$OUT"
cp "$FIXTURES/opencode.json" "$PROBE_DIR/opencode.json"
cp "$FIXTURES/plugins/pea-probe.ts" "$PROBE_DIR/.opencode/plugins/pea-probe.ts"

LAST_EXIT=1
run_scenario() {
  M="$1"; N="$2"; MUTATE="$3"; PROMPT="$4"
  echo "--- S$N ($M) ---"
  PEA_PROBE_MUTATE="$MUTATE" timeout -k 5 240 opencode run \
    --dir "$PROBE_DIR" --print-logs --log-level DEBUG --format json \
    -m "$M" "$PROMPT" \
    > "$OUT/S$N.events.jsonl" 2> "$OUT/S$N.stderr.log"
  LAST_EXIT=$?
  echo "exit=$LAST_EXIT size=$(wc -c < "$OUT/S$N.events.jsonl" | tr -d ' ') bytes"
  sleep 1
}

# A candidate passes only if the model call itself succeeded: exit 0, no
# grammar error. chat.message firing alone is NOT enough — it fires on the
# user prompt even when the model call subsequently fails.
grammar_failed() {
  grep -q "failed to parse grammar" "$OUT/S1.events.jsonl" "$OUT/S1.stderr.log" 2>/dev/null
}

try_model() {
  M="$1"
  run_scenario "$M" 1 0 "Reply with exactly: PEA_BASELINE_OK"
  [ "$LAST_EXIT" = "0" ] && ! grammar_failed
}

# Candidate order: local first, then fixture-declared cloud models, then any
# other ollama :cloud model.
CANDIDATES="ollama/ornith-1.5:9b ollama/deepseek-v4.1-flash:cloud ollama/glm-5.3-flash:cloud"
MODEL=""
for c in $CANDIDATES; do
  if try_model "$c"; then MODEL="$c"; break; fi
  echo "model $c failed S1 (exit=$LAST_EXIT grammar=$(grammar_failed && echo yes || echo no)); trying next candidate"
done
if [ -z "$MODEL" ]; then
  # `opencode models` reads config from cwd (no --dir flag), so run inside PROBE_DIR.
  CLOUD_MODELS="$(cd "$PROBE_DIR" && opencode models ollama 2>/dev/null | grep ":cloud" | tr -d ' ')"
  for c in $CLOUD_MODELS; do
    full="ollama/$c"
    case " $CANDIDATES " in *" $full "*) continue ;; esac
    if try_model "$full"; then MODEL="$full"; break; fi
    echo "model $full failed S1 (exit=$LAST_EXIT grammar=$(grammar_failed && echo yes || echo no)); trying next cloud model"
  done
fi
if [ -z "$MODEL" ]; then
  echo "SKIP: no usable ollama model (S1 failed for every candidate)"
  exit 0
fi
echo "chosen model: $MODEL"

# Fresh probe log for the final evidence run (candidate trials also logged).
: > "$LOG"

run_scenario "$MODEL" 1 0 "Reply with exactly: PEA_BASELINE_OK"
run_scenario "$MODEL" 2 0 "Use the bash tool to run: echo PEA_PROBE_BLOCK — then say done."
if ! grep -q '"tool.execute.before"' "$LOG" 2>/dev/null; then
  # Second phrasing for models that need a more explicit instruction.
  run_scenario "$MODEL" 2b 0 "Run this exact command with bash: echo PEA_PROBE_BLOCK"
fi
run_scenario "$MODEL" 3 1 "List every token in this conversation enclosed in square brackets, verbatim."
run_scenario "$MODEL" 4 0 "Reply with exactly: PEA_BASELINE_OK"

echo "=== summary ==="
summarize() {
  N="$1"; DESC="$2"; MATCH="$3"
  if grep -q "$MATCH" "$LOG" 2>/dev/null; then
    echo "S$N: PASS ($DESC) — $(grep "$MATCH" "$LOG" | head -1)"
  elif grep -q "chat.message" "$LOG" 2>/dev/null; then
    echo "S$N: INCONCLUSIVE ($DESC) — probe.jsonl has chat.message but no '$MATCH'; model may lack tool calling or run exceeded timeout"
  else
    echo "S$N: INCONCLUSIVE ($DESC) — no chat.message in probe.jsonl; see S$N.stderr.log"
  fi
}
summarize 1 "baseline chat.message fired" "chat.message"
# blocked:true in the before-hook entry is the real S2 signal; the throw
# message itself never lands in probe.jsonl (run-mode chat.message only logs
# the user prompt).
summarize 2 "tool block: before-hook blocked and after-hook absent" '"hook":"tool.execute.before".*"blocked":true'
summarize 3 "injection canary PEA-CANARY-1 in parts" "PEA-CANARY-1"
summarize 4 "repeat baseline for delta-vs-complete ordering" "chat.message"
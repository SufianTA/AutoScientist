#!/usr/bin/env bash
set -euo pipefail

WORKDIR="${WORKDIR:-/workspace/AutoScientist}"
VENV="${VENV:-/opt/autosci-venv}"
LIMIT="${LIMIT:-100}"
REPLICATES="${REPLICATES:-3}"
EPOCHS="${EPOCHS:-120}"
LLM_PROVIDER="${LLM_PROVIDER:-auto}"
LLM_MODEL="${LLM_MODEL:-}"
LLM_API_KEY_ENV_VAR="${LLM_API_KEY_ENV_VAR:-}"
REQUIRE_REAL_LLM="${REQUIRE_REAL_LLM:-1}"
STRICT_REAL="${STRICT_REAL:-1}"
CASE_IDS="${CASE_IDS:-}"
TEMPLATE_IDS="${TEMPLATE_IDS:-}"
MIN_FULL_COMPLETION_RATE="${MIN_FULL_COMPLETION_RATE:-1.0}"
MIN_FULL_MEAN_SCORE="${MIN_FULL_MEAN_SCORE:-85}"
MIN_NEURAL_HOLDOUT_TOP1="${MIN_NEURAL_HOLDOUT_TOP1:-0.5}"
MIN_STATE_GRAPH_NODES="${MIN_STATE_GRAPH_NODES:-1}"
DRY_RUN="${AUTOSCI_DRY_RUN:-0}"

run() {
  if [ "$DRY_RUN" = "1" ]; then
    printf '+'
    printf ' %q' "$@"
    printf '\n'
    return 0
  fi
  "$@"
}

if [ "$DRY_RUN" = "1" ]; then
  printf '+ cd %q\n' "$WORKDIR"
  printf '+ source %q\n' "$VENV/bin/activate"
else
  cd "$WORKDIR"
  source "$VENV/bin/activate"
fi

PREFLIGHT_FLAGS=(--workspace "$WORKDIR" --output-dir outputs/preflight --require-gpu)
run python tools/machine_preflight.py "${PREFLIGHT_FLAGS[@]}"

REAL_LLM_FLAGS=()
if [ "$REQUIRE_REAL_LLM" = "1" ]; then
  REAL_LLM_FLAGS+=(--require-real-llm)
fi

STRICT_FLAGS=(
  --min-full-completion-rate "$MIN_FULL_COMPLETION_RATE"
  --min-full-mean-score "$MIN_FULL_MEAN_SCORE"
  --require-expected-integrations
  --min-neural-holdout-top1 "$MIN_NEURAL_HOLDOUT_TOP1"
  --min-state-graph-nodes "$MIN_STATE_GRAPH_NODES"
)
if [ "$STRICT_REAL" = "1" ]; then
  STRICT_FLAGS+=(--strict-real-run)
fi

CASE_FLAGS=()
if [ -n "$CASE_IDS" ]; then
  # shellcheck disable=SC2206
  CASE_ID_ARRAY=($CASE_IDS)
  CASE_FLAGS+=(--case-ids "${CASE_ID_ARRAY[@]}")
fi
if [ -n "$TEMPLATE_IDS" ]; then
  # shellcheck disable=SC2206
  TEMPLATE_ID_ARRAY=($TEMPLATE_IDS)
  CASE_FLAGS+=(--template-ids "${TEMPLATE_ID_ARRAY[@]}")
fi

run python tools/run_autoscientist_bench.py \
  --limit "$LIMIT" \
  --replicates-per-case "$REPLICATES" \
  "${CASE_FLAGS[@]}" \
  --ablations full no_memory no_public_tools no_sciflow \
  --enable-sciflow-policy \
  --train-neural-policy \
  --neural-epochs "$EPOCHS" \
  --llm-provider "$LLM_PROVIDER" \
  --llm-model "$LLM_MODEL" \
  --llm-api-key-env-var "$LLM_API_KEY_ENV_VAR" \
  "${REAL_LLM_FLAGS[@]}" \
  "${STRICT_FLAGS[@]}"

run python tools/collect_review_package.py

echo "GPU benchmark complete. Review packages are under outputs/review_packages."

#!/usr/bin/env bash
set -euo pipefail

WORKDIR="${WORKDIR:-/workspace/AutoScientist}"
VENV="${VENV:-/opt/autosci-venv}"
LIMIT="${LIMIT:-100}"
REPLICATES="${REPLICATES:-3}"
EPOCHS="${EPOCHS:-120}"
LLM_PROVIDER="${LLM_PROVIDER:-mock}"
LLM_MODEL="${LLM_MODEL:-mock-scientist}"
LLM_API_KEY_ENV_VAR="${LLM_API_KEY_ENV_VAR:-}"
REQUIRE_REAL_LLM="${REQUIRE_REAL_LLM:-0}"
MEDEA_PYTHON="${MEDEA_PYTHON:-}"
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
if [ -n "$MEDEA_PYTHON" ]; then
  PREFLIGHT_FLAGS+=(--require-medea)
fi
run python tools/machine_preflight.py "${PREFLIGHT_FLAGS[@]}"

REAL_LLM_FLAGS=()
if [ "$REQUIRE_REAL_LLM" = "1" ]; then
  REAL_LLM_FLAGS+=(--require-real-llm)
fi

MEDEA_FLAGS=()
if [ -n "$MEDEA_PYTHON" ]; then
  MEDEA_FLAGS+=(--medea-python "$MEDEA_PYTHON" --medea-smoke-only)
else
  MEDEA_FLAGS+=(--disable-medea)
fi

run python tools/run_autoscientist_bench.py \
  --limit "$LIMIT" \
  --replicates-per-case "$REPLICATES" \
  --ablations full no_memory no_medea no_public_tools no_sciflow \
  --enable-sciflow-policy \
  --train-neural-policy \
  --neural-epochs "$EPOCHS" \
  --llm-provider "$LLM_PROVIDER" \
  --llm-model "$LLM_MODEL" \
  --llm-api-key-env-var "$LLM_API_KEY_ENV_VAR" \
  "${REAL_LLM_FLAGS[@]}" \
  "${MEDEA_FLAGS[@]}"

run python tools/collect_review_package.py

echo "GPU benchmark complete. Review packages are under outputs/review_packages."

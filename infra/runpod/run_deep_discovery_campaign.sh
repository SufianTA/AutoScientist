#!/usr/bin/env bash
set -euo pipefail

WORKDIR="${WORKDIR:-/workspace/AutoScientist}"
VENV="${VENV:-/opt/autosci-venv}"
SEED_CASES="${SEED_CASES:-benchmarks/biotruth_seed_cases_v0_1.json}"
RUBRIC="${RUBRIC:-benchmarks/biotruth_rubric_v0_1.json}"
MANIFEST="${MANIFEST:-benchmarks/autoscientist_biotruth_deep_100.json}"
LIMIT="${LIMIT:-100}"
MAX_CASES="${MAX_CASES:-25}"
TEMPLATES_PER_CASE="${TEMPLATES_PER_CASE:-4}"
REPLICATES="${REPLICATES:-1}"
LLM_PROVIDER="${LLM_PROVIDER:-gemini}"
LLM_MODEL="${LLM_MODEL:-gemini-2.5-flash}"
LLM_API_KEY_ENV_VAR="${LLM_API_KEY_ENV_VAR:-GEMINI_API_KEY}"
LLM_MAX_TOKENS="${LLM_MAX_TOKENS:-1600}"
JUDGE_LLM_PROVIDER="${JUDGE_LLM_PROVIDER:-gemini}"
JUDGE_LLM_MODEL="${JUDGE_LLM_MODEL:-gemini-2.5-flash}"
JUDGE_LLM_API_KEY_ENV_VAR="${JUDGE_LLM_API_KEY_ENV_VAR:-GEMINI_API_KEY}"
JUDGE_LLM_MAX_TOKENS="${JUDGE_LLM_MAX_TOKENS:-4096}"
NEURAL_EPOCHS="${NEURAL_EPOCHS:-100}"
NEURAL_HIDDEN_DIM="${NEURAL_HIDDEN_DIM:-128}"
NEURAL_BATCH_SIZE="${NEURAL_BATCH_SIZE:-32}"
AGENT_COUNT="${AGENT_COUNT:-3}"
MAX_RUNTIME_MINUTES="${MAX_RUNTIME_MINUTES:-240}"
PUBLIC_TIMEOUT_SECONDS="${PUBLIC_TIMEOUT_SECONDS:-15}"
ASSOCIATION_SCAN_SIZE="${ASSOCIATION_SCAN_SIZE:-150}"
MAX_CRITICAL_FAILURE_RATE="${MAX_CRITICAL_FAILURE_RATE:-0.20}"
REVIEW_PACKAGE_NAME="${REVIEW_PACKAGE_NAME:-autoscientist_biotruth_100_deep_discovery}"
OUTPUT_DIR="${OUTPUT_DIR:-outputs/autoscientist_bench}"
REVIEW_OUTPUT_DIR="${REVIEW_OUTPUT_DIR:-outputs/review_packages}"
RUN_LOG_DIR="${RUN_LOG_DIR:-outputs/run_logs}"
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
else
  cd "$WORKDIR"
fi

mkdir -p "$RUN_LOG_DIR" "$REVIEW_OUTPUT_DIR"
STAMP="$(date -u +%Y%m%d_%H%M%S)"
LOG_PATH="$RUN_LOG_DIR/deep_discovery_100_${STAMP}.log"

if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

if [ -d ".git" ]; then
  run git status --short
fi

if [ -f "$VENV/bin/activate" ]; then
  # shellcheck disable=SC1090
  source "$VENV/bin/activate"
else
  echo "Virtualenv not found at $VENV; creating it."
  run python3 -m venv "$VENV"
  # shellcheck disable=SC1090
  source "$VENV/bin/activate"
  run python -m pip install --upgrade pip setuptools wheel
  run python -m pip install -e ".[dev,tooluniverse,neural]"
fi

echo "=== AutoScientist Deep Discovery Campaign ==="
echo "started_utc=$STAMP"
echo "workdir=$WORKDIR"
echo "limit=$LIMIT"
echo "manifest=$MANIFEST"
echo "log=$LOG_PATH"

run python tools/machine_preflight.py \
  --workspace "$WORKDIR" \
  --output-dir outputs/preflight \
  --require-gpu

run python tools/build_biotruth_benchmark.py \
  --seed-cases "$SEED_CASES" \
  --rubric "$RUBRIC" \
  --output-manifest "$MANIFEST" \
  --max-cases "$MAX_CASES" \
  --templates-per-case "$TEMPLATES_PER_CASE" \
  --association-scan-size "$ASSOCIATION_SCAN_SIZE" \
  --public-timeout-seconds "$PUBLIC_TIMEOUT_SECONDS"

set +e
python tools/run_biotruth_pipeline.py \
  --mode full \
  --skip-build \
  --manifest "$MANIFEST" \
  --seed-cases "$SEED_CASES" \
  --rubric "$RUBRIC" \
  --output-dir "$OUTPUT_DIR" \
  --review-output-dir "$REVIEW_OUTPUT_DIR" \
  --review-package-name "$REVIEW_PACKAGE_NAME" \
  --limit "$LIMIT" \
  --replicates-per-case "$REPLICATES" \
  --ablations full \
  --llm-provider "$LLM_PROVIDER" \
  --llm-model "$LLM_MODEL" \
  --llm-api-key-env-var "$LLM_API_KEY_ENV_VAR" \
  --llm-max-tokens "$LLM_MAX_TOKENS" \
  --strict-real-run \
  --require-expected-integrations \
  --train-neural-policy \
  --neural-epochs "$NEURAL_EPOCHS" \
  --neural-hidden-dim "$NEURAL_HIDDEN_DIM" \
  --neural-batch-size "$NEURAL_BATCH_SIZE" \
  --score-mode judge \
  --max-score-results "$LIMIT" \
  --judge-llm-provider "$JUDGE_LLM_PROVIDER" \
  --judge-llm-model "$JUDGE_LLM_MODEL" \
  --judge-llm-api-key-env-var "$JUDGE_LLM_API_KEY_ENV_VAR" \
  --judge-llm-max-tokens "$JUDGE_LLM_MAX_TOKENS" \
  --disable-qworld \
  --agent-count "$AGENT_COUNT" \
  --max-runtime-minutes "$MAX_RUNTIME_MINUTES" \
  --max-critical-failure-rate "$MAX_CRITICAL_FAILURE_RATE" \
  2>&1 | tee "$LOG_PATH"
PIPELINE_STATUS="${PIPESTATUS[0]}"
set -e

LATEST_BENCH_DIR="$(python - <<'PY'
from pathlib import Path
root = Path("outputs/autoscientist_bench")
dirs = [p for p in root.iterdir() if p.is_dir()] if root.exists() else []
print(sorted(dirs, key=lambda p: p.stat().st_mtime, reverse=True)[0] if dirs else "")
PY
)"

if [ -z "$LATEST_BENCH_DIR" ] || [ ! -d "$LATEST_BENCH_DIR" ]; then
  echo "No benchmark directory was produced."
  exit 2
fi

CASE_STUDY_DIR="outputs/discovery_case_studies/biotruth_100_deep_discovery_${STAMP}"
run python tools/build_discovery_case_study.py \
  --bench-dir "$LATEST_BENCH_DIR" \
  --output-dir "$CASE_STUDY_DIR"

run python tools/build_discovery_insight_report.py \
  --bench-dir "$LATEST_BENCH_DIR" \
  --case-study-dir "$CASE_STUDY_DIR" \
  --output-json "$CASE_STUDY_DIR/discovery_insight_report.json" \
  --output-md "$CASE_STUDY_DIR/discovery_insight_report.md"

FINAL_PACKAGE="$REVIEW_OUTPUT_DIR/${REVIEW_PACKAGE_NAME}_${STAMP}_complete.zip"
run python -m zipfile -c "$FINAL_PACKAGE" \
  "$LATEST_BENCH_DIR" \
  "$CASE_STUDY_DIR" \
  "$MANIFEST" \
  "${MANIFEST%.json}.md" \
  "docs/BIOTRUTH_100_CASE_SELECTION.md" \
  "docs/END_TO_END_DISCOVERY_CASE_STUDIES.md"

cat <<EOF
=== Deep discovery campaign finished ===
pipeline_status=$PIPELINE_STATUS
benchmark_dir=$LATEST_BENCH_DIR
case_study_dir=$CASE_STUDY_DIR
complete_package=$FINAL_PACKAGE
log=$LOG_PATH
EOF

exit "$PIPELINE_STATUS"

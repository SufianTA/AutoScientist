#!/usr/bin/env bash
set -euo pipefail

WORKDIR="${WORKDIR:-/workspace/AutoScientist}"
VENV="${VENV:-/opt/autosci-venv}"
SEED_CASES="${SEED_CASES:-benchmarks/biotruth_seed_cases_v0_1.json}"
RUBRIC="${RUBRIC:-benchmarks/biotruth_rubric_v0_1.json}"
MANIFEST="${MANIFEST:-benchmarks/autoscientist_biotruth_20_case_gate.json}"
OUTPUT_DIR="${OUTPUT_DIR:-outputs/autoscientist_bench}"
REVIEW_OUTPUT_DIR="${REVIEW_OUTPUT_DIR:-outputs/review_packages}"
RUN_LOG_DIR="${RUN_LOG_DIR:-outputs/run_logs}"
REVIEW_PACKAGE_NAME="${REVIEW_PACKAGE_NAME:-autoscientist_biotruth_20_case_gate}"

# This is 20 disease/target cases, one audit-heavy workflow each.
# The benchmark still runs four ablations, so the expected result count is 80.
CASE_IDS="${CASE_IDS:-il6_rheumatoid_arthritis tnf_inflammatory_bowel_disease nod2_crohn_disease tyk2_psoriasis braf_melanoma egfr_lung_adenocarcinoma erbb2_breast_cancer alk_lung_cancer parp1_ovarian_cancer cftr_cystic_fibrosis smn1_spinal_muscular_atrophy acvr1_fibrodysplasia_ossificans_progressiva dmd_duchenne_muscular_dystrophy app_alzheimer_disease apoe_alzheimer_disease lrrk2_parkinson_disease pcsk9_familial_hypercholesterolemia slc5a2_type_2_diabetes f9_hemophilia_b vegfa_age_related_macular_degeneration}"
TEMPLATE_IDS="${TEMPLATE_IDS:-target_validity_review}"
LIMIT="${LIMIT:-20}"
MAX_CASES="${MAX_CASES:-25}"
TEMPLATES_PER_CASE="${TEMPLATES_PER_CASE:-1}"
REPLICATES="${REPLICATES:-1}"
ABLATIONS="${ABLATIONS:-full no_memory no_public_tools no_sciflow}"

LLM_PROVIDER="${LLM_PROVIDER:-anthropic}"
LLM_MODEL="${LLM_MODEL:-claude-sonnet-4-6}"
LLM_API_KEY_ENV_VAR="${LLM_API_KEY_ENV_VAR:-ANTHROPIC_KEY}"
LLM_MAX_TOKENS="${LLM_MAX_TOKENS:-1600}"
JUDGE_LLM_PROVIDER="${JUDGE_LLM_PROVIDER:-anthropic}"
JUDGE_LLM_MODEL="${JUDGE_LLM_MODEL:-claude-sonnet-4-6}"
JUDGE_LLM_API_KEY_ENV_VAR="${JUDGE_LLM_API_KEY_ENV_VAR:-ANTHROPIC_KEY}"
JUDGE_LLM_MAX_TOKENS="${JUDGE_LLM_MAX_TOKENS:-2200}"
SCORE_MODE="${SCORE_MODE:-judge}"
MAX_SCORE_RESULTS="${MAX_SCORE_RESULTS:-80}"

NEURAL_EPOCHS="${NEURAL_EPOCHS:-80}"
NEURAL_HIDDEN_DIM="${NEURAL_HIDDEN_DIM:-128}"
NEURAL_BATCH_SIZE="${NEURAL_BATCH_SIZE:-32}"
AGENT_COUNT="${AGENT_COUNT:-3}"
MAX_RUNTIME_MINUTES="${MAX_RUNTIME_MINUTES:-180}"
PUBLIC_TIMEOUT_SECONDS="${PUBLIC_TIMEOUT_SECONDS:-20}"
ASSOCIATION_SCAN_SIZE="${ASSOCIATION_SCAN_SIZE:-150}"
MAX_CRITICAL_FAILURE_RATE="${MAX_CRITICAL_FAILURE_RATE:-0.10}"
MIN_FULL_MEAN_SCORE="${MIN_FULL_MEAN_SCORE:-85}"
MIN_NEURAL_HOLDOUT_TOP1="${MIN_NEURAL_HOLDOUT_TOP1:-0.50}"
DRY_RUN="${AUTOSCI_DRY_RUN:-0}"
CASE_COUNT="$(printf '%s\n' $CASE_IDS | wc -l | tr -d ' ')"
ABLATION_COUNT="$(printf '%s\n' $ABLATIONS | wc -l | tr -d ' ')"
EXPECTED_RESULTS="$((LIMIT * ABLATION_COUNT))"

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
LOG_PATH="$RUN_LOG_DIR/biotruth_20_case_gate_${STAMP}.log"

if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

echo "=== AutoScientist BioTruth 20-Case Gate ==="
echo "started_utc=$STAMP"
echo "workdir=$WORKDIR"
echo "case_count=$CASE_COUNT"
echo "limit=$LIMIT"
echo "ablation_count=$ABLATION_COUNT"
echo "expected_results=$EXPECTED_RESULTS"
echo "llm=$LLM_PROVIDER/$LLM_MODEL via $LLM_API_KEY_ENV_VAR"
echo "judge=$JUDGE_LLM_PROVIDER/$JUDGE_LLM_MODEL via $JUDGE_LLM_API_KEY_ENV_VAR"
echo "log=$LOG_PATH"

if [ -d ".git" ]; then
  run git status --short
fi

if command -v apt-get >/dev/null 2>&1; then
  run apt-get update
  run apt-get install -y --no-install-recommends libxrender1 libxext6 libsm6 libglib2.0-0 libgl1
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

run python tools/machine_preflight.py \
  --workspace "$WORKDIR" \
  --output-dir outputs/preflight \
  --min-free-gb 10 \
  --require-gpu \
  --require-tooluniverse \
  --execute-tooluniverse \
  --llm-provider "$LLM_PROVIDER" \
  --llm-model "$LLM_MODEL" \
  --llm-api-key-env-var "$LLM_API_KEY_ENV_VAR" \
  --test-llm

run python tools/machine_preflight.py \
  --workspace "$WORKDIR" \
  --output-dir outputs/preflight \
  --min-free-gb 10 \
  --require-gpu \
  --skip-tooluniverse \
  --llm-provider "$JUDGE_LLM_PROVIDER" \
  --llm-model "$JUDGE_LLM_MODEL" \
  --llm-api-key-env-var "$JUDGE_LLM_API_KEY_ENV_VAR" \
  --test-llm

run python tools/build_biotruth_benchmark.py \
  --seed-cases "$SEED_CASES" \
  --rubric "$RUBRIC" \
  --output-manifest "$MANIFEST" \
  --max-cases "$MAX_CASES" \
  --case-ids $CASE_IDS \
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
  --case-ids $CASE_IDS \
  --template-ids $TEMPLATE_IDS \
  --replicates-per-case "$REPLICATES" \
  --ablations $ABLATIONS \
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
  --score-mode "$SCORE_MODE" \
  --max-score-results "$MAX_SCORE_RESULTS" \
  --judge-llm-provider "$JUDGE_LLM_PROVIDER" \
  --judge-llm-model "$JUDGE_LLM_MODEL" \
  --judge-llm-api-key-env-var "$JUDGE_LLM_API_KEY_ENV_VAR" \
  --judge-llm-max-tokens "$JUDGE_LLM_MAX_TOKENS" \
  --disable-qworld \
  --agent-count "$AGENT_COUNT" \
  --max-runtime-minutes "$MAX_RUNTIME_MINUTES" \
  --max-critical-failure-rate "$MAX_CRITICAL_FAILURE_RATE" \
  --min-full-completion-rate 1.0 \
  --min-full-mean-score "$MIN_FULL_MEAN_SCORE" \
  --min-neural-holdout-top1 "$MIN_NEURAL_HOLDOUT_TOP1" \
  --min-state-graph-nodes 1 \
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

CASE_STUDY_DIR="outputs/discovery_case_studies/biotruth_20_case_gate_${STAMP}"
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
  "benchmarks/biotruth_seed_cases_v0_1.json" \
  "benchmarks/biotruth_rubric_v0_1.json" \
  "docs/BIOTRUTH_BENCHMARK.md"

cat <<EOF
=== BioTruth 20-case gate finished ===
pipeline_status=$PIPELINE_STATUS
benchmark_dir=$LATEST_BENCH_DIR
case_study_dir=$CASE_STUDY_DIR
complete_package=$FINAL_PACKAGE
log=$LOG_PATH
EOF

exit "$PIPELINE_STATUS"

#!/usr/bin/env bash
set -euo pipefail

# Cost-controlled strict-real BioTruth v0.2 canary.
# Runs a stratified subset across support, tentative, conflicting, safety-limited,
# and abstention-required cases before any larger paid benchmark.

WORKDIR="${WORKDIR:-/workspace/AutoScientist}"
SEED_CASES="${SEED_CASES:-benchmarks/biotruth_seed_cases_v0_2.json}"
RUBRIC="${RUBRIC:-benchmarks/biotruth_rubric_v0_2.json}"
MANIFEST="${MANIFEST:-benchmarks/autoscientist_biotruth_v0_2_strict_canary.json}"
REVIEW_PACKAGE_NAME="${REVIEW_PACKAGE_NAME:-autoscientist_biotruth_v0_2_strict_canary}"

CASE_IDS="${CASE_IDS:-tnf_rheumatoid_arthritis_strong braf_melanoma_strong nod2_crohn_moderate app_alzheimer_conflicting lrrk2_parkinson_safety_limited egfr_rheumatoid_arthritis_insufficient}"
TEMPLATE_IDS="${TEMPLATE_IDS:-target_validity_review}"
LIMIT="${LIMIT:-6}"
MAX_CASES="${MAX_CASES:-12}"
TEMPLATES_PER_CASE="${TEMPLATES_PER_CASE:-1}"
MAX_SCORE_RESULTS="${MAX_SCORE_RESULTS:-24}"

ABLATIONS="${ABLATIONS:-full plain_llm no_public_tools no_sciflow}"
MIN_FULL_MEAN_SCORE="${MIN_FULL_MEAN_SCORE:-75}"
MAX_CRITICAL_FAILURE_RATE="${MAX_CRITICAL_FAILURE_RATE:-0.20}"
MIN_NEURAL_HOLDOUT_TOP1="${MIN_NEURAL_HOLDOUT_TOP1:-0.0}"

LLM_PROVIDER="${LLM_PROVIDER:-anthropic}"
LLM_MODEL="${LLM_MODEL:-claude-sonnet-4-6}"
LLM_API_KEY_ENV_VAR="${LLM_API_KEY_ENV_VAR:-ANTHROPIC_KEY}"
JUDGE_LLM_PROVIDER="${JUDGE_LLM_PROVIDER:-anthropic}"
JUDGE_LLM_MODEL="${JUDGE_LLM_MODEL:-claude-sonnet-4-6}"
JUDGE_LLM_API_KEY_ENV_VAR="${JUDGE_LLM_API_KEY_ENV_VAR:-ANTHROPIC_KEY}"

export WORKDIR
export SEED_CASES
export RUBRIC
export MANIFEST
export REVIEW_PACKAGE_NAME
export CASE_IDS
export TEMPLATE_IDS
export LIMIT
export MAX_CASES
export TEMPLATES_PER_CASE
export MAX_SCORE_RESULTS
export ABLATIONS
export MIN_FULL_MEAN_SCORE
export MAX_CRITICAL_FAILURE_RATE
export MIN_NEURAL_HOLDOUT_TOP1
export LLM_PROVIDER
export LLM_MODEL
export LLM_API_KEY_ENV_VAR
export JUDGE_LLM_PROVIDER
export JUDGE_LLM_MODEL
export JUDGE_LLM_API_KEY_ENV_VAR

echo "=== AutoScientist BioTruth v0.2 Strict Canary ==="
echo "cases=$CASE_IDS"
echo "templates=$TEMPLATE_IDS"
echo "ablations=$ABLATIONS"
echo "expected_results=$((LIMIT * $(printf '%s\n' $ABLATIONS | wc -l | tr -d ' ')))"
echo "llm=$LLM_PROVIDER/$LLM_MODEL via $LLM_API_KEY_ENV_VAR"
echo "judge=$JUDGE_LLM_PROVIDER/$JUDGE_LLM_MODEL via $JUDGE_LLM_API_KEY_ENV_VAR"

exec bash infra/runpod/run_biotruth_20_case_gate.sh

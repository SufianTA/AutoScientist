#!/usr/bin/env bash
set -euo pipefail

# Cheap live gate before any larger BioTruth benchmark.
# Runs 4 known-good disease/target cases x 4 ablations = 16 result artifacts.

WORKDIR="${WORKDIR:-/workspace/AutoScientist}"
REVIEW_PACKAGE_NAME="${REVIEW_PACKAGE_NAME:-autoscientist_biotruth_4_case_canary}"

CASE_IDS="${CASE_IDS:-il6_rheumatoid_arthritis tnf_inflammatory_bowel_disease braf_melanoma egfr_lung_adenocarcinoma}"
LIMIT="${LIMIT:-4}"
MAX_CASES="${MAX_CASES:-4}"
MAX_SCORE_RESULTS="${MAX_SCORE_RESULTS:-16}"
MIN_FULL_MEAN_SCORE="${MIN_FULL_MEAN_SCORE:-85}"
MAX_CRITICAL_FAILURE_RATE="${MAX_CRITICAL_FAILURE_RATE:-0.05}"

LLM_PROVIDER="${LLM_PROVIDER:-anthropic}"
LLM_MODEL="${LLM_MODEL:-claude-sonnet-4-6}"
LLM_API_KEY_ENV_VAR="${LLM_API_KEY_ENV_VAR:-ANTHROPIC_KEY}"
JUDGE_LLM_PROVIDER="${JUDGE_LLM_PROVIDER:-anthropic}"
JUDGE_LLM_MODEL="${JUDGE_LLM_MODEL:-claude-sonnet-4-6}"
JUDGE_LLM_API_KEY_ENV_VAR="${JUDGE_LLM_API_KEY_ENV_VAR:-ANTHROPIC_KEY}"

export WORKDIR
export REVIEW_PACKAGE_NAME
export CASE_IDS
export LIMIT
export MAX_CASES
export MAX_SCORE_RESULTS
export MIN_FULL_MEAN_SCORE
export MAX_CRITICAL_FAILURE_RATE
export LLM_PROVIDER
export LLM_MODEL
export LLM_API_KEY_ENV_VAR
export JUDGE_LLM_PROVIDER
export JUDGE_LLM_MODEL
export JUDGE_LLM_API_KEY_ENV_VAR

echo "=== AutoScientist BioTruth 4-Case Canary ==="
echo "cases=$CASE_IDS"
echo "expected_results=16"
echo "llm=$LLM_PROVIDER/$LLM_MODEL via $LLM_API_KEY_ENV_VAR"
echo "judge=$JUDGE_LLM_PROVIDER/$JUDGE_LLM_MODEL via $JUDGE_LLM_API_KEY_ENV_VAR"

exec bash infra/runpod/run_biotruth_20_case_gate.sh

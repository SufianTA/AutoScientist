#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
API_ROOT="$REPO_ROOT/apps/api"

QUESTION=""
INTERACTIVE=0
SETTINGS=""
AGENTS=6
RUNTIME=30
STRICTNESS="balanced"
LLM_PROVIDER="mock"
LLM_MODEL="mock-scientist"
LLM_API_KEY_ENV_VAR=""
LLM_BASE_URL=""
REQUIRE_REAL_LLM=0
STREAM_PROGRESS=0
NO_COLOR=0
REAL_DATA=0
OUTPUT_FORMAT="summary"
OUTPUT_FILE=""
PROVENANCE_FILE=""
MODEL_TOOLS=()

usage() {
  cat <<'EOF'
Usage: infra/scripts/run_local_question.sh [options] "scientific question"

Options:
  --interactive                  Prompt for the problem and run settings
  --settings PATH                Load bioautosci.settings.json
  --agents N                     Number of scientist agents, 1-12
  --runtime MINUTES              Runtime budget metadata
  --strictness MODE              exploratory, balanced, or strict
  --llm-provider PROVIDER        mock, openai, anthropic, gemini, openai_compatible, local_http
  --llm-model MODEL              Provider model name
  --llm-api-key-env-var NAME     API key environment variable name
  --llm-base-url URL             Base URL for local_http/openai_compatible
  --require-real-llm             Fail if a real provider is not configured
  --real-data                    Use live public biomedical APIs and ToolUniverse
  --model-tool NAME              Add an onboarded custom model tool
  --stream-progress              Show agent/tool/LLM progress in the terminal
  --no-color                     Disable ANSI colors
  --output-format FORMAT         summary, json, or markdown
  --output-file PATH             Write formatted output to a file
  --provenance-file PATH         Write full trace/provenance JSON
  -h, --help                     Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --interactive) INTERACTIVE=1; shift ;;
    --settings) SETTINGS="${2:?Missing value for --settings}"; shift 2 ;;
    --agents) AGENTS="${2:?Missing value for --agents}"; shift 2 ;;
    --runtime) RUNTIME="${2:?Missing value for --runtime}"; shift 2 ;;
    --strictness) STRICTNESS="${2:?Missing value for --strictness}"; shift 2 ;;
    --llm-provider) LLM_PROVIDER="${2:?Missing value for --llm-provider}"; shift 2 ;;
    --llm-model) LLM_MODEL="${2:?Missing value for --llm-model}"; shift 2 ;;
    --llm-api-key-env-var) LLM_API_KEY_ENV_VAR="${2:?Missing value for --llm-api-key-env-var}"; shift 2 ;;
    --llm-base-url) LLM_BASE_URL="${2:?Missing value for --llm-base-url}"; shift 2 ;;
    --require-real-llm) REQUIRE_REAL_LLM=1; shift ;;
    --stream-progress) STREAM_PROGRESS=1; shift ;;
    --no-color) NO_COLOR=1; shift ;;
    --real-data) REAL_DATA=1; shift ;;
    --model-tool) MODEL_TOOLS+=("${2:?Missing value for --model-tool}"); shift 2 ;;
    --output-format) OUTPUT_FORMAT="${2:?Missing value for --output-format}"; shift 2 ;;
    --output-file) OUTPUT_FILE="${2:?Missing value for --output-file}"; shift 2 ;;
    --provenance-file) PROVENANCE_FILE="${2:?Missing value for --provenance-file}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    --) shift; QUESTION="$*"; break ;;
    -*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      QUESTION="${QUESTION:+$QUESTION }$1"
      shift
      ;;
  esac
done

export PYTHONPATH="$REPO_ROOT:$API_ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

cd "$REPO_ROOT"

ARGS=()
if [[ "$INTERACTIVE" -eq 1 ]]; then
  ARGS+=(--interactive)
elif [[ -n "$QUESTION" ]]; then
  ARGS+=("$QUESTION")
else
  echo "Provide a scientific question or use --interactive." >&2
  usage >&2
  exit 2
fi

if [[ -n "$SETTINGS" ]]; then
  ARGS+=(--settings "$SETTINGS")
fi

ARGS+=(
  --agents "$AGENTS"
  --runtime "$RUNTIME"
  --strictness "$STRICTNESS"
  --llm-provider "$LLM_PROVIDER"
  --llm-model "$LLM_MODEL"
  --output-format "$OUTPUT_FORMAT"
)

[[ -n "$LLM_API_KEY_ENV_VAR" ]] && ARGS+=(--llm-api-key-env-var "$LLM_API_KEY_ENV_VAR")
[[ -n "$LLM_BASE_URL" ]] && ARGS+=(--llm-base-url "$LLM_BASE_URL")
[[ "$REQUIRE_REAL_LLM" -eq 1 ]] && ARGS+=(--require-real-llm)
[[ "$STREAM_PROGRESS" -eq 1 ]] && ARGS+=(--stream-progress)
[[ "$NO_COLOR" -eq 1 ]] && ARGS+=(--no-color)
[[ "$REAL_DATA" -eq 1 ]] && ARGS+=(--real-data)
for model_tool in "${MODEL_TOOLS[@]}"; do
  ARGS+=(--model-tool "$model_tool")
done
[[ -n "$OUTPUT_FILE" ]] && ARGS+=(--output-file "$OUTPUT_FILE")
[[ -n "$PROVENANCE_FILE" ]] && ARGS+=(--provenance-file "$PROVENANCE_FILE")

python -m app.services.local_runner "${ARGS[@]}"

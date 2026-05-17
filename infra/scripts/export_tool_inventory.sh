#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
API_ROOT="$REPO_ROOT/apps/api"
OUTPUT_PATH="${1:-$REPO_ROOT/tool_inventory.json}"

export PYTHONPATH="$REPO_ROOT:$API_ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

cd "$API_ROOT"
python -m app.services.tool_inventory_exporter "$OUTPUT_PATH"

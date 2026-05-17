#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REPORT_PATH="$REPO_ROOT/outputs/smoke_cli_report.md"
PROVENANCE_PATH="$REPO_ROOT/outputs/smoke_cli_provenance.json"

"$SCRIPT_DIR/run_local_question.sh" \
  --agents 3 \
  --runtime 10 \
  --strictness balanced \
  --output-format markdown \
  --output-file "$REPORT_PATH" \
  --provenance-file "$PROVENANCE_PATH" \
  "Generate a therapeutic hypothesis for PCSK9-driven familial hypercholesterolemia and propose validation experiments."

[[ -f "$REPORT_PATH" ]] || { echo "CLI smoke report was not written: $REPORT_PATH" >&2; exit 1; }
[[ -f "$PROVENANCE_PATH" ]] || { echo "CLI smoke provenance was not written: $PROVENANCE_PATH" >&2; exit 1; }

grep -q "PCSK9" "$REPORT_PATH"
grep -q "familial hypercholesterolemia" "$REPORT_PATH"
grep -q "Guardrails" "$REPORT_PATH"

python - "$PROVENANCE_PATH" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as file:
    provenance = json.load(file)
summary = provenance["trace_summary"]
if summary["agent_steps"] < 8:
    raise SystemExit("CLI smoke provenance has too few agent steps.")
if summary["tool_calls"] < 2:
    raise SystemExit("CLI smoke provenance has too few tool calls.")
PY

echo "CLI smoke test passed"
echo "Report: $REPORT_PATH"
echo "Provenance: $PROVENANCE_PATH"

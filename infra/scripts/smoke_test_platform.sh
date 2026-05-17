#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"

python - "$BASE_URL" <<'PY'
import json
import sys
from urllib.request import Request, urlopen

base_url = sys.argv[1].rstrip("/")


def request(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    req = Request(base_url + path, data=data, headers=headers, method=method)
    with urlopen(req, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


health = request("GET", "/health")
print("API health:", health["status"])

objective = request(
    "POST",
    "/objectives",
    {
        "title": "Smoke test PCSK9/FH run",
        "objective": "Generate a smoke-test therapeutic hypothesis for PCSK9-driven familial hypercholesterolemia.",
        "constraints": {"require_critic": True, "require_citations": True},
    },
)

run = request(
    "POST",
    "/runs",
    {
        "objective_id": objective["id"],
        "execute_demo": True,
        "run_config": {
            "execution_mode": "inline",
            "agent_count": 3,
            "max_runtime_minutes": 10,
            "tool_budget_usd": 1,
            "evidence_strictness": "balanced",
        },
    },
)
print("Run:", run["id"], run["status"])

report = request("GET", f"/reports/{run['id']}")
print("Report:", report["hypothesis"]["title"])
PY

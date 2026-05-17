#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
API_ROOT="$REPO_ROOT/apps/api"
FRONTEND_ROOT="$REPO_ROOT/apps/frontend"
OUTPUT_ROOT="$REPO_ROOT/outputs"
mkdir -p "$OUTPUT_ROOT"

port_listening() {
  local port="$1"
  python - "$port" <<'PY'
import socket
import sys

port = int(sys.argv[1])
sock = socket.socket()
sock.settimeout(0.2)
try:
    sock.connect(("127.0.0.1", port))
except OSError:
    sys.exit(1)
finally:
    sock.close()
PY
}

frontend_healthy() {
  python - <<'PY'
from urllib.error import URLError
from urllib.request import urlopen
import re

try:
    with urlopen("http://127.0.0.1:3000/objectives/new", timeout=10) as response:
        body = response.read().decode("utf-8", errors="replace")
        if response.status != 200 or "stylesheet" not in body:
            raise SystemExit(1)
        assets = re.findall(r'(?:href|src)="([^"]*?_next/static/[^"]+)"', body)
        if not assets:
            raise SystemExit(1)
        for asset in assets:
            with urlopen("http://127.0.0.1:3000" + asset, timeout=10) as asset_response:
                if asset_response.status != 200:
                    raise SystemExit(1)
        with urlopen("http://127.0.0.1:3000/api/health", timeout=10) as proxy_response:
            if proxy_response.status != 200:
                raise SystemExit(1)
        raise SystemExit(0)
except URLError:
    raise SystemExit(1)
PY
}

api_healthy() {
  python - <<'PY'
from urllib.error import URLError
from urllib.request import Request, urlopen

try:
    with urlopen("http://127.0.0.1:8000/health", timeout=10) as response:
        if response.status != 200:
            raise SystemExit(1)
    request = Request(
        "http://127.0.0.1:8000/models",
        method="OPTIONS",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    with urlopen(request, timeout=10) as response:
        if response.headers.get("access-control-allow-origin") != "http://127.0.0.1:3000":
            raise SystemExit(1)
    raise SystemExit(0)
except URLError:
    raise SystemExit(1)
PY
}

api_secrets_loaded() {
  python - "$REPO_ROOT/.env" "$API_ROOT/.env" <<'PY'
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen
import json
import sys

provider_env_vars = {
    "OPENAI_API_KEY": "openai",
    "ANTHROPIC_API_KEY": "anthropic",
    "GEMINI_API_KEY": "gemini",
}

try:
    for env_file_text in sys.argv[1:]:
        env_file = Path(env_file_text)
        if not env_file.exists():
            continue
        for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            env_var, value = stripped.split("=", 1)
            env_var = env_var.strip()
            value = value.strip().strip('"').strip("'")
            provider = provider_env_vars.get(env_var)
            if not provider or not value:
                continue
            query = urlencode({"api_key_env_var": env_var})
            with urlopen(
                f"http://127.0.0.1:8000/framework/llm-providers/{provider}/validate?{query}",
                timeout=10,
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not payload.get("has_key"):
                raise SystemExit(1)
    raise SystemExit(0)
except URLError:
    raise SystemExit(1)
PY
}

export PYTHONPATH="$REPO_ROOT:$API_ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

if port_listening 8000 && { ! api_healthy || ! api_secrets_loaded; }; then
  echo "API on port 8000 is unhealthy; restarting it"
  python - <<'PY'
import os
import signal
import subprocess

if os.name == "nt":
    raise SystemExit(0)
try:
    output = subprocess.check_output(["lsof", "-ti", "tcp:8000"], text=True)
except Exception:
    output = ""
for pid_text in output.split():
    try:
        os.kill(int(pid_text), signal.SIGTERM)
    except OSError:
        pass
PY
  sleep 1
fi

if ! port_listening 8000; then
  (
    cd "$API_ROOT"
    nohup python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 \
      > "$OUTPUT_ROOT/api_server.log" 2>&1 &
    echo $! > "$OUTPUT_ROOT/api_server.pid"
  )
  echo "Started API on http://127.0.0.1:8000"
else
  echo "API already listening on http://127.0.0.1:8000"
fi

if port_listening 3000 && ! frontend_healthy; then
  echo "Frontend on port 3000 is unhealthy; restarting it"
  python - <<'PY'
import os
import signal
import socket
import subprocess

if os.name == "nt":
    raise SystemExit(0)
try:
    output = subprocess.check_output(["lsof", "-ti", "tcp:3000"], text=True)
except Exception:
    output = ""
for pid_text in output.split():
    try:
        os.kill(int(pid_text), signal.SIGTERM)
    except OSError:
        pass
PY
  rm -rf "$FRONTEND_ROOT/.next"
  sleep 1
fi

if ! port_listening 3000; then
  (
    cd "$FRONTEND_ROOT"
    nohup npx next dev -H 127.0.0.1 -p 3000 \
      > "$OUTPUT_ROOT/frontend_server.log" 2>&1 &
    echo $! > "$OUTPUT_ROOT/frontend_server.pid"
  )
  echo "Started frontend on http://127.0.0.1:3000"
else
  echo "Frontend already listening on http://127.0.0.1:3000"
fi

sleep 3

python - <<'PY'
from urllib.error import URLError
from urllib.request import urlopen

for name, url in [
    ("API health", "http://127.0.0.1:8000/health"),
    ("Frontend status", "http://127.0.0.1:3000"),
]:
    try:
        with urlopen(url, timeout=5) as response:
            print(f"{name}: {response.status}")
    except URLError:
        print(f"{name}: not ready yet")
PY

echo "Open workbench: http://127.0.0.1:3000"

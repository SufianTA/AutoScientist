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

try:
    with urlopen("http://127.0.0.1:3000/objectives/new", timeout=10) as response:
        body = response.read().decode("utf-8", errors="replace")
        raise SystemExit(0 if response.status == 200 and "stylesheet" in body else 1)
except URLError:
    raise SystemExit(1)
PY
}

export PYTHONPATH="$REPO_ROOT:$API_ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

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

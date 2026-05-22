#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/SufianTA/AutoScientist.git}"
BRANCH="${BRANCH:-main}"
WORKDIR="${WORKDIR:-/workspace/AutoScientist}"
VENV="${VENV:-/opt/autosci-venv}"
INSTALL_MEDEA="${INSTALL_MEDEA:-0}"
MEDEA_DIR="${MEDEA_DIR:-/workspace/Medea}"
MEDEA_VENV="${MEDEA_VENV:-/opt/medea-py310}"
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

append_env_once() {
  local line="$1"
  local file="$2"
  if [ "$DRY_RUN" = "1" ]; then
    printf '+ append %q to %q\n' "$line" "$file"
    return 0
  fi
  touch "$file"
  if ! grep -qxF "$line" "$file"; then
    printf '%s\n' "$line" >> "$file"
  fi
}

run apt-get update
run apt-get install -y git git-lfs curl build-essential python3-venv
run git lfs install || true

if [ -d "$WORKDIR/.git" ]; then
  run git -C "$WORKDIR" fetch origin "$BRANCH"
  run git -C "$WORKDIR" checkout "$BRANCH"
  run git -C "$WORKDIR" pull --ff-only origin "$BRANCH"
else
  run git clone --branch "$BRANCH" "$REPO_URL" "$WORKDIR"
fi

run python3 -m venv "$VENV"
run "$VENV/bin/python" -m pip install --upgrade pip setuptools wheel
if [ "$DRY_RUN" = "1" ]; then
  printf '+ cd %q\n' "$WORKDIR"
else
  cd "$WORKDIR"
fi
run "$VENV/bin/python" -m pip install -e ".[dev,tooluniverse,neural]"

if [ "$INSTALL_MEDEA" = "1" ]; then
  if [ -d "$MEDEA_DIR/.git" ]; then
    run git -C "$MEDEA_DIR" pull --ff-only
  else
    run git clone https://github.com/mims-harvard/Medea.git "$MEDEA_DIR"
  fi
  run "$VENV/bin/python" -m pip install uv
  run "$VENV/bin/uv" python install 3.10
  if ! run "$VENV/bin/uv" venv "$MEDEA_VENV" --python 3.10; then
    if command -v python3.10 >/dev/null 2>&1; then
      run python3.10 -m venv "$MEDEA_VENV"
    else
      echo "Python 3.10 is required for Medea and could not be created by uv." >&2
      exit 1
    fi
  fi
  run "$MEDEA_VENV/bin/python" -m pip install --upgrade pip setuptools wheel
  run "$MEDEA_VENV/bin/python" -m pip install -e "$MEDEA_DIR"
  run "$MEDEA_VENV/bin/python" -m pip install openai==1.82.1
  append_env_once "MEDEA_PYTHON=$MEDEA_VENV/bin/python" "$WORKDIR/.env"
fi

PREFLIGHT_FLAGS=(--workspace "$WORKDIR" --output-dir "$WORKDIR/outputs/preflight" --require-gpu)
if [ "$INSTALL_MEDEA" = "1" ]; then
  PREFLIGHT_FLAGS+=(--require-medea)
fi
run "$VENV/bin/python" tools/machine_preflight.py "${PREFLIGHT_FLAGS[@]}"

echo "AutoScientist bootstrap complete."
echo "Next: cd $WORKDIR && $VENV/bin/python tools/run_autoscientist_bench.py --limit 6 --ablations full no_memory no_public_tools"

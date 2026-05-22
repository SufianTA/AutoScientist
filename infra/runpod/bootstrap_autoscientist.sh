#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/SufianTA/AutoScientist.git}"
BRANCH="${BRANCH:-main}"
WORKDIR="${WORKDIR:-/workspace/AutoScientist}"
VENV="${VENV:-/opt/autosci-venv}"
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

run apt-get update
run apt-get install -y git git-lfs curl build-essential python3-venv libxrender1 libxext6 libsm6 libglib2.0-0 libgl1
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

PREFLIGHT_FLAGS=(--workspace "$WORKDIR" --output-dir "$WORKDIR/outputs/preflight" --require-gpu)
run "$VENV/bin/python" tools/machine_preflight.py "${PREFLIGHT_FLAGS[@]}"

echo "AutoScientist bootstrap complete."
echo "Next: cd $WORKDIR && $VENV/bin/python tools/run_autoscientist_bench.py --limit 6 --ablations full no_memory no_public_tools"

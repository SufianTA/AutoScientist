#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/SufianTA/AutoScientist.git}"
BRANCH="${BRANCH:-main}"
WORKDIR="${WORKDIR:-/workspace/AutoScientist}"
VENV="${VENV:-/opt/autosci-venv}"
INSTALL_MEDEA="${INSTALL_MEDEA:-0}"
MEDEA_DIR="${MEDEA_DIR:-/workspace/Medea}"
MEDEA_VENV="${MEDEA_VENV:-/opt/medea-py310}"

apt-get update
apt-get install -y git git-lfs curl build-essential python3-venv
git lfs install || true

if [ -d "$WORKDIR/.git" ]; then
  git -C "$WORKDIR" fetch origin "$BRANCH"
  git -C "$WORKDIR" checkout "$BRANCH"
  git -C "$WORKDIR" pull --ff-only origin "$BRANCH"
else
  git clone --branch "$BRANCH" "$REPO_URL" "$WORKDIR"
fi

python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --upgrade pip setuptools wheel
cd "$WORKDIR"
"$VENV/bin/python" -m pip install -e ".[dev,tooluniverse,neural]"

if [ "$INSTALL_MEDEA" = "1" ]; then
  if [ -d "$MEDEA_DIR/.git" ]; then
    git -C "$MEDEA_DIR" pull --ff-only
  else
    git clone https://github.com/mims-harvard/Medea.git "$MEDEA_DIR"
  fi
  "$VENV/bin/python" -m pip install uv
  "$VENV/bin/uv" venv "$MEDEA_VENV" --python 3.10 || python3 -m venv "$MEDEA_VENV"
  "$MEDEA_VENV/bin/python" -m pip install --upgrade pip setuptools wheel
  "$MEDEA_VENV/bin/python" -m pip install -e "$MEDEA_DIR"
  "$MEDEA_VENV/bin/python" -m pip install openai==1.82.1
  echo "MEDEA_PYTHON=$MEDEA_VENV/bin/python" >> "$WORKDIR/.env"
fi

"$VENV/bin/python" tools/machine_preflight.py \
  --workspace "$WORKDIR" \
  --output-dir "$WORKDIR/outputs/preflight" \
  --require-gpu

echo "AutoScientist bootstrap complete."
echo "Next: cd $WORKDIR && $VENV/bin/python tools/run_autoscientist_bench.py --limit 6 --ablations full no_memory no_public_tools"

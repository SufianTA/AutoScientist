# ToolUniverse Setup

The adapter supports ToolUniverse and reports ToolUniverse health through `/tools/health`.

The local environment previously had two issues:

1. `tokenizers==0.22.2` conflicted with `transformers==4.44.0`.
2. `tooluniverse` was installed as an editable checkout from a local ToolUniverse repo and failed with a circular import involving `candidate_tester_tool`.

The working local fix was:

```bash
python -m pip uninstall -y tooluniverse
python -m pip install "tokenizers>=0.19,<0.20"
python -m pip install tooluniverse==1.0.4 --no-deps
```

After this, `from tooluniverse import ToolUniverse` and `ToolUniverse()` both initialize in the global Python environment.

Use an isolated virtual environment for the API instead of the global Python install.

## Recommended Local Fix

Windows:

```powershell
cd apps/api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev,tooluniverse]"
pip install "tokenizers>=0.19,<0.20"
$env:PYTHONPATH = (Resolve-Path ..\..).Path
python -c "from tooluniverse import ToolUniverse; print('ToolUniverse ok')"
```

macOS/Linux:

```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev,tooluniverse]"
pip install "tokenizers>=0.19,<0.20"
export PYTHONPATH="$(cd ../.. && pwd):$(pwd)"
python -c "from tooluniverse import ToolUniverse; print('ToolUniverse ok')"
```

If ToolUniverse is installed editable from a local checkout, keep it isolated from unrelated ML packages. The API endpoint `/tools/health` reports import errors without crashing the platform.

## Inventory Export

Windows:

```powershell
.\infra\scripts\export_tool_inventory.ps1
```

macOS/Linux:

```bash
./infra/scripts/export_tool_inventory.sh
```

When ToolUniverse imports correctly, `tool_inventory.json` will include real ToolUniverse specs in addition to custom mock tools.

## Custom Model Tools

Use `/models` or the Models page to register specialized model tools. The framework emits a ToolUniverse-style JSON config that can later be converted into a native ToolUniverse custom tool file.

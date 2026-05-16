# ToolUniverse Setup

The adapter supports ToolUniverse, but the local global Python environment currently has a dependency mismatch:

```text
transformers==4.44.0 requires tokenizers>=0.19,<0.20
installed tokenizers==0.22.2
```

Use an isolated virtual environment for the API instead of the global Python install.

## Recommended Local Fix

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

If ToolUniverse is installed editable from a local checkout, keep it isolated from unrelated ML packages. The API endpoint `/tools/health` reports the import error without crashing the platform.

Current local diagnostic:

```text
tooluniverse 1.0.4 is installed as an editable checkout from
C:\Users\cassa\Documents\Github\Harvard\bioagent\ToolUniverse
```

After fixing `tokenizers`, the import reaches the local ToolUniverse package but currently fails with:

```text
cannot import name 'candidate_tester_tool' from partially initialized module 'tooluniverse'
```

Until that editable checkout is fixed or replaced with a clean non-editable install, real BioAutoScientist runs use live public biomedical tools and record ToolUniverse health separately.

## Inventory Export

```powershell
.\infra\scripts\export_tool_inventory.ps1
```

When ToolUniverse imports correctly, `tool_inventory.json` will include real ToolUniverse specs in addition to custom mock tools.

## Custom Model Tools

Use `/models` or the Models page to register specialized model tools. The framework emits a ToolUniverse-style JSON config that can later be converted into a native ToolUniverse custom tool file.

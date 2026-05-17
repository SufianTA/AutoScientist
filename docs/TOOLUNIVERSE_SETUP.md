# ToolUniverse Setup

BioAutoScientist can run without ToolUniverse in deterministic/mock mode, but ToolUniverse is recommended for real scientific tool discovery and execution. The API reports ToolUniverse availability through:

```text
GET /tools/health
```

## Install

From the repository root:

Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[tooluniverse,dev]"
python -c "from tooluniverse import ToolUniverse; print('ToolUniverse ok')"
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[tooluniverse,dev]"
python -c "from tooluniverse import ToolUniverse; print('ToolUniverse ok')"
```

The root package pins the known-compatible ToolUniverse dependency set:

```text
tooluniverse==1.0.4
tokenizers>=0.19,<0.20
```

## Health Check

Start the local platform:

```powershell
.\infra\scripts\start_local_platform.ps1
```

```bash
./infra/scripts/start_local_platform.sh
```

Then check:

```text
http://127.0.0.1:8000/tools/health
```

If ToolUniverse is unavailable or has dependency conflicts, the adapter reports the error in `/tools/health` instead of crashing the API. Runs can still use custom/local tools, but strict ToolUniverse-backed analyses should treat missing ToolUniverse calls as a limitation.

## Inventory Export

Windows:

```powershell
.\infra\scripts\export_tool_inventory.ps1
```

macOS/Linux:

```bash
./infra/scripts/export_tool_inventory.sh
```

When ToolUniverse imports correctly, `tool_inventory.json` includes ToolUniverse specs in addition to BioAutoScientist custom tools.

## Custom Model Tools

Use the Models page or `POST /models` to register specialized model tools. The framework emits ToolUniverse-style model tool configs so custom evidence scorers, rerankers, or local HTTP models can participate in the same provenance-bearing workflow.

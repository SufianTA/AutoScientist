# BioAutoScientist

Open-source local framework for auditable biomedical hypothesis generation on top of ToolUniverse-style tools, LangGraph orchestration, optional OpenClaw integration, configurable model providers, and a CLAW-like research board.

The first slice implements a mock-first ACVR1/FOP workflow:

- FastAPI backend with objectives, runs, tools, research board, traces, and reports.
- Custom scientific tool interface with provenance-bearing outputs.
- Mock custom tools for ACVR1 profile, FOP profile, RDKit-like descriptors, evidence scoring, hypothesis cards, and experiment recommendations.
- Structured agent state machine for intake, planning, evidence collection, hypothesis generation, critique, board publication, and reporting.
- Next.js frontend skeleton with objective intake, live run trace, tool inventory, research board, and report views.
- Docker Compose for API, frontend, Postgres, and Redis.
- Async research-run controls for agent count, runtime, tool budget units, evidence strictness, local model provider, and queued/background execution.
- Custom model onboarding that emits ToolUniverse-style model tool configs and executes selected mock/local HTTP model tools inside the run.
- LangGraph node workflow with deterministic fallback if LangGraph is unavailable.

## Quick Start

```powershell
cp .env.example .env
docker compose up --build
```

API: http://localhost:8000

Frontend: http://localhost:3000

Start both local dev servers without Docker:

```powershell
.\infra\scripts\start_local_platform.ps1
```

Then open http://127.0.0.1:3000 and launch a run from **New Objective**.

## Local API Development

```powershell
cd apps/api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
$env:PYTHONPATH = (Resolve-Path ..\..).Path
uvicorn app.main:app --reload
```

Run tests:

```powershell
cd apps/api
pytest
```

Export the current ToolUniverse plus custom tool inventory:

```powershell
.\infra\scripts\export_tool_inventory.ps1
```

If ToolUniverse is installed but import fails, check `/tools/health`. The adapter reports dependency conflicts instead of crashing the API.

Process one queued run locally:

```powershell
.\infra\scripts\process_next_run.ps1
```

Run a live API smoke test after the API is running:

```powershell
.\infra\scripts\smoke_test_platform.ps1
```

Run one scientific question locally without opening the web UI:

```powershell
.\infra\scripts\run_local_question.ps1 -Question "Generate a therapeutic hypothesis for ACVR1-driven FOP." -Agents 6 -Runtime 30 -Strictness balanced
```

Launch the interactive CLI workbench:

```powershell
.\infra\scripts\run_local_question.ps1 -Interactive
```

Interactive mode asks for the scientific problem, lets you choose an exact agent count or optimized agent count, streams each agent state as it runs, and writes both a Markdown report and JSON provenance trace.
Choose live public biomedical data when prompted to use NCBI Gene, PubMed, and PubChem calls in the run.

Write a command-line report artifact:

```powershell
.\infra\scripts\run_local_question.ps1 -Question "Generate a therapeutic hypothesis for ACVR1-driven FOP." -OutputFormat markdown -OutputFile .\outputs\acvr1_fop_report.md
```

Run the non-interactive CLI with live public data:

```powershell
.\infra\scripts\run_local_question.ps1 -Question "Generate a therapeutic hypothesis for ACVR1-driven FOP." -RealData -OutputFormat markdown -OutputFile .\outputs\acvr1_fop_real_report.md -ProvenanceFile .\outputs\acvr1_fop_real_provenance.json
```

Live-data mode currently calls NCBI Gene, PubMed, and PubChem. ToolUniverse is installed locally, but the editable checkout currently fails during import with a circular import; `/tools/health` reports that instead of hiding it.

Write both a report and full provenance trace:

```powershell
.\infra\scripts\run_local_question.ps1 -Question "Generate a therapeutic hypothesis for ACVR1-driven FOP." -OutputFormat markdown -OutputFile .\outputs\acvr1_fop_report.md -ProvenanceFile .\outputs\acvr1_fop_provenance.json
```

Run the repeatable CLI smoke test:

```powershell
.\infra\scripts\smoke_test_cli.ps1
```

Register a custom evidence model in the Models UI, then select it on the New Objective page. The selected model name is passed as `model_tool_names`; the backend resolves it to a ToolUniverse-style config and records the model invocation as a provenance-bearing tool call.

CLI runs can select registered model tools too:

```powershell
.\infra\scripts\run_local_question.ps1 -Question "Generate a therapeutic hypothesis for ACVR1-driven FOP." -ModelTools mock_acvr1_evidence_model
```

More deployment detail:

- `docs/TOOLUNIVERSE_SETUP.md`
- `docs/CLOUD_DEPLOYMENT.md`

## Scientific Guardrails

The system labels outputs as candidate hypotheses. It must not claim clinical efficacy, safety, or validation unless direct evidence supports that claim. Reports should use cautious wording such as "computationally prioritized", "evidence-supported but not validated", and "requires experimental validation".

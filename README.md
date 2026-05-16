# BioAutoScientist

ToolUniverse-native research workbench prototype for auditable biomedical hypothesis generation.

The first slice implements a mock-first ACVR1/FOP workflow:

- FastAPI backend with objectives, runs, tools, research board, traces, and reports.
- Custom scientific tool interface with provenance-bearing outputs.
- Mock custom tools for ACVR1 profile, FOP profile, RDKit-like descriptors, evidence scoring, hypothesis cards, and experiment recommendations.
- Structured agent state machine for intake, planning, evidence collection, hypothesis generation, critique, board publication, and reporting.
- Next.js frontend skeleton with objective intake, live run trace, tool inventory, research board, and report views.
- Docker Compose for API, frontend, Postgres, and Redis.

## Quick Start

```powershell
cp .env.example .env
docker compose up --build
```

API: http://localhost:8000

Frontend: http://localhost:3000

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

## Scientific Guardrails

The system labels outputs as candidate hypotheses. It must not claim clinical efficacy, safety, or validation unless direct evidence supports that claim. Reports should use cautious wording such as "computationally prioritized", "evidence-supported but not validated", and "requires experimental validation".

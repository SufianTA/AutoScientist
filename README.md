# BioAutoScientist

BioAutoScientist is a local, open-source workbench for auditable biomedical hypothesis generation. It combines LangGraph agent orchestration, ToolUniverse-style scientific tools, live public biomedical data sources, configurable LLM providers, provenance logging, and a CLAW-like research board.

The project is designed for scientific workflow prototyping, not clinical decision-making. It produces candidate hypotheses, evidence summaries, critiques, and validation plans with explicit guardrails.

## What It Does

- Runs biomedical scientist-agent workflows from the CLI or browser.
- Supports OpenAI, Anthropic, Gemini, OpenAI-compatible endpoints, and local HTTP models.
- Uses deterministic mock mode for development and strict real mode for real LLM-backed runs.
- Calls local/custom tools, live public biomedical APIs, and ToolUniverse/OpenTargets where available.
- Streams agent activity in the CLI, including planning, tool calls, LLM calls, debate, critique, and report synthesis.
- Stores auditable traces, tool calls, evidence items, board posts, hypotheses, reports, and provenance.
- Lets users register custom model tools and include them in the scientific workflow.

## Repository Layout

```text
apps/api/        FastAPI backend, database models, routes, run execution
apps/frontend/   Next.js browser workbench
agents/          LangGraph and fallback agent runtime
tools/           Custom scientific tools and tests
models/          Evidence scorer prototype scaffolding
infra/scripts/   Local startup, CLI wrappers, smoke tests
docs/            Install, ToolUniverse, local framework, and cloud notes
```

## Quick Start

### 1. Install

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[tooluniverse,dev]"
Copy-Item .\bioautosci.settings.example.json .\bioautosci.settings.json
Copy-Item .\.env.example .\.env
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[tooluniverse,dev]"
cp bioautosci.settings.example.json bioautosci.settings.json
cp .env.example .env
```

### 2. Configure Provider Keys

Put raw provider keys only in ignored `.env` or your shell environment:

```text
ANTHROPIC_API_KEY=your-provider-key
OPENAI_API_KEY=
GEMINI_API_KEY=
```

Keep `bioautosci.settings.json` limited to non-secret run settings:

```json
{
  "llm_provider": "anthropic",
  "llm_model": "claude-sonnet-4-6",
  "llm_api_key_env_var": "ANTHROPIC_API_KEY",
  "real_data_enabled": true,
  "require_real_llm": true,
  "evidence_strictness": "strict",
  "agent_count": 7,
  "max_runtime_minutes": 30,
  "output_dir": "outputs"
}
```

The browser UI also expects an environment variable name such as `ANTHROPIC_API_KEY`; do not paste raw keys into the browser.

### 3. Run From CLI

Windows:

```powershell
bioautosci --settings .\bioautosci.settings.json --stream-progress `
  --output-format markdown `
  --output-file .\outputs\acvr1_report.md `
  --provenance-file .\outputs\acvr1_provenance.json `
  "Generate a scientist-grade therapeutic hypothesis analysis for ACVR1-driven Fibrodysplasia Ossificans Progressiva. Use live public evidence, identify disease-target mechanism, candidate interventions, safety concerns, citations, and validation experiments. Do not claim clinical efficacy."
```

macOS/Linux:

```bash
bioautosci --settings ./bioautosci.settings.json --stream-progress \
  --output-format markdown \
  --output-file ./outputs/acvr1_report.md \
  --provenance-file ./outputs/acvr1_provenance.json \
  "Generate a scientist-grade therapeutic hypothesis analysis for ACVR1-driven Fibrodysplasia Ossificans Progressiva. Use live public evidence, identify disease-target mechanism, candidate interventions, safety concerns, citations, and validation experiments. Do not claim clinical efficacy."
```

Interactive CLI:

```powershell
.\infra\scripts\run_local_question.ps1 -Interactive
```

```bash
./infra/scripts/run_local_question.sh --interactive
```

### 4. Run Browser Workbench

Install frontend dependencies once:

```bash
cd apps/frontend
npm install
cd ../..
```

Start both local servers:

```powershell
.\infra\scripts\start_local_platform.ps1
```

```bash
./infra/scripts/start_local_platform.sh
```

Open:

```text
http://127.0.0.1:3000
```

The startup scripts verify API health, frontend static assets, API proxying, CORS, and whether configured provider keys are visible to the running API process.

## Modes

- `mock`: deterministic local mode for tests and demos without paid providers.
- `strict real`: real LLM calls, live public data, provenance, and fail-fast behavior if keys are missing.
- `real-data`: enables NCBI Gene, PubMed, PubChem, and ToolUniverse/OpenTargets calls where valid inputs are available.
- `background` / `queued`: lets longer browser runs execute outside the initial request.

## Agent Workflow

The default runtime is LangGraph. The workflow includes:

1. Research planning by a PI agent.
2. Tool discovery and input mapping.
3. Evidence collection from live/custom tools.
4. Evidence scoring.
5. Hypothesis synthesis.
6. Parallel specialist-agent debate.
7. Skeptical critique and confidence adjustment.
8. Experiment recommendation.
9. Report and research-board publication.

Every step writes trace/provenance records.

## ToolUniverse

ToolUniverse integration is optional but recommended:

```bash
python -m pip install -e ".[tooluniverse,dev]"
```

Check tool health:

```text
http://127.0.0.1:8000/tools/health
```

Export the inventory:

```powershell
.\infra\scripts\export_tool_inventory.ps1
```

```bash
./infra/scripts/export_tool_inventory.sh
```

See [docs/TOOLUNIVERSE_SETUP.md](docs/TOOLUNIVERSE_SETUP.md) for dependency notes.

## PyPI Install

After publishing:

```bash
python -m pip install "bio-auto-scientist[tooluniverse]"
```

Then copy `bioautosci.settings.example.json` and `.env.example` from the repository or package docs, add provider keys to `.env`, and run `bioautosci`.

## Documentation

- [docs/INSTALL.md](docs/INSTALL.md)
- [docs/LOCAL_FRAMEWORK.md](docs/LOCAL_FRAMEWORK.md)
- [docs/TOOLUNIVERSE_SETUP.md](docs/TOOLUNIVERSE_SETUP.md)
- [docs/CLOUD_DEPLOYMENT.md](docs/CLOUD_DEPLOYMENT.md)

## Scientific Guardrails

BioAutoScientist generates candidate hypotheses. It must not claim clinical efficacy, safety, or validation unless direct evidence supports that claim. Reports should use cautious wording such as "computationally prioritized", "evidence-supported but not validated", "insufficient evidence", and "requires experimental validation".

This project is for research workflow automation and human-reviewed scientific analysis. It is not medical advice.

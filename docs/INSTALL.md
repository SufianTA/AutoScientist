# Install And Run BioAutoScientist

BioAutoScientist can run as a local CLI or as a browser workbench. The easiest first run is local CLI with a settings file.

## 1. Clone

```bash
git clone https://github.com/YOUR_ORG/bio-auto-scientist.git
cd bio-auto-scientist
```

## 2. Install Python Package

For development from the cloned repo:

Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[tooluniverse,dev]"
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[tooluniverse,dev]"
```

After publishing to PyPI, users can install with:

```bash
python -m pip install "bio-auto-scientist[tooluniverse]"
```

## 3. Configure Keys

Copy the example settings file:

Windows:

```powershell
Copy-Item .\bioautosci.settings.example.json .\bioautosci.settings.json
```

macOS/Linux:

```bash
cp bioautosci.settings.example.json bioautosci.settings.json
```

Edit `bioautosci.settings.json` and choose one provider:

```json
{
  "llm_provider": "anthropic",
  "llm_model": "claude-sonnet-4-6",
  "llm_api_key_env_var": "ANTHROPIC_API_KEY",
  "api_keys": {
    "ANTHROPIC_API_KEY": "your-key-here",
    "OPENAI_API_KEY": "",
    "GEMINI_API_KEY": ""
  },
  "real_data_enabled": true,
  "require_real_llm": true,
  "evidence_strictness": "strict",
  "agent_count": 7
}
```

You can also leave `api_keys` empty and set environment variables yourself:

Windows:

```powershell
$env:ANTHROPIC_API_KEY = "your-key"
$env:OPENAI_API_KEY = "your-key"
$env:GEMINI_API_KEY = "your-key"
```

macOS/Linux:

```bash
export ANTHROPIC_API_KEY="your-key"
export OPENAI_API_KEY="your-key"
export GEMINI_API_KEY="your-key"
```

The settings file is ignored by git. Do not commit raw keys.

## 4. Run CLI With Live Agent Activity

Windows:

```powershell
bioautosci `
  --settings .\bioautosci.settings.json `
  --stream-progress `
  --output-format markdown `
  --output-file .\outputs\acvr1_report.md `
  --provenance-file .\outputs\acvr1_provenance.json `
  "Generate a scientist-grade therapeutic hypothesis analysis for ACVR1-driven Fibrodysplasia Ossificans Progressiva. Use live public evidence, identify disease-target mechanism, candidate interventions, safety concerns, citations, and validation experiments. Do not claim clinical efficacy."
```

macOS/Linux:

```bash
bioautosci \
  --settings ./bioautosci.settings.json \
  --stream-progress \
  --output-format markdown \
  --output-file ./outputs/acvr1_report.md \
  --provenance-file ./outputs/acvr1_provenance.json \
  "Generate a scientist-grade therapeutic hypothesis analysis for ACVR1-driven Fibrodysplasia Ossificans Progressiva. Use live public evidence, identify disease-target mechanism, candidate interventions, safety concerns, citations, and validation experiments. Do not claim clinical efficacy."
```

The CLI prints:

- initialized agents and responsibilities,
- planning steps,
- extracted targets, diseases, and candidate interventions,
- ToolUniverse, PubMed, NCBI, and PubChem activity,
- LLM calls by agent and task,
- evidence labels,
- critique,
- final report confidence.

## 5. Run Browser Workbench

Install frontend dependencies once:

Windows:

```powershell
cd apps\frontend
npm install
cd ..\..
```

macOS/Linux:

```bash
cd apps/frontend
npm install
cd ../..
```

Create `.env` at the repo root from `.env.example`:

Windows:

```powershell
Copy-Item .\.env.example .\.env
```

macOS/Linux:

```bash
cp .env.example .env
```

Set your provider key in `.env`:

```text
ANTHROPIC_API_KEY=your-key
OPENAI_API_KEY=
GEMINI_API_KEY=
```

Start API and frontend:

Windows:

```powershell
.\infra\scripts\start_local_platform.ps1
```

macOS/Linux:

```bash
./infra/scripts/start_local_platform.sh
```

Open:

```text
http://127.0.0.1:3000
```

## Provider Examples

Anthropic:

```json
{
  "llm_provider": "anthropic",
  "llm_model": "claude-sonnet-4-6",
  "llm_api_key_env_var": "ANTHROPIC_API_KEY"
}
```

OpenAI:

```json
{
  "llm_provider": "openai",
  "llm_model": "gpt-4.1",
  "llm_api_key_env_var": "OPENAI_API_KEY"
}
```

Gemini:

```json
{
  "llm_provider": "gemini",
  "llm_model": "gemini-1.5-pro",
  "llm_api_key_env_var": "GEMINI_API_KEY"
}
```

## Important Guardrail

BioAutoScientist generates evidence-grounded candidate hypotheses. It does not prove clinical efficacy or safety. Reports intentionally use cautious wording and preserve all tool/LLM provenance for human review.

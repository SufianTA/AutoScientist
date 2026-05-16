# Local AutoScientist Framework

BioAutoScientist is being shaped as a local, open-source scientific automation framework.

Core idea:

1. Install ToolUniverse and BioAutoScientist locally.
2. Register preferred LLMs and custom biomedical models.
3. Ask a scientific question.
4. The orchestrator builds a plan, assigns specialist agents, calls tools, publishes to a CLAW-like board, critiques claims, and emits a reproducible report.

## Local Run

Start the local platform:

```powershell
.\infra\scripts\start_local_platform.ps1
```

Open http://127.0.0.1:3000 for the browser workbench.

```powershell
.\infra\scripts\run_local_question.ps1 -Question "Generate a therapeutic hypothesis for ACVR1-driven FOP." -Agents 6 -Runtime 30 -Strictness balanced
```

Interactive launcher:

```powershell
.\infra\scripts\run_local_question.ps1 -Interactive
```

Flow:

1. Paste the scientific problem.
2. Choose optimized agent count or enter a number from 1-12.
3. Choose evidence strictness.
4. Watch realtime agent-state events, queued tools, tool-call counts, evidence scores, critique, and report confidence.
5. Receive the final summary plus Markdown and provenance JSON files.

Output modes:

```powershell
.\infra\scripts\run_local_question.ps1 -Question "Generate a therapeutic hypothesis for ACVR1-driven FOP." -OutputFormat summary
.\infra\scripts\run_local_question.ps1 -Question "Generate a therapeutic hypothesis for ACVR1-driven FOP." -OutputFormat json
.\infra\scripts\run_local_question.ps1 -Question "Generate a therapeutic hypothesis for ACVR1-driven FOP." -OutputFormat markdown -OutputFile .\outputs\acvr1_fop_report.md
.\infra\scripts\run_local_question.ps1 -Question "Generate a therapeutic hypothesis for ACVR1-driven FOP." -OutputFormat markdown -OutputFile .\outputs\acvr1_fop_report.md -ProvenanceFile .\outputs\acvr1_fop_provenance.json
```

`-ProvenanceFile` writes the full agent-step trace and normalized tool-call outputs as JSON for audit/replay work.

## Model Onboarding

Use `/models` or the Models UI to register:

- local HTTP models,
- OpenAI-compatible endpoints,
- Hugging Face models,
- custom Python model wrappers.

Each registration produces a ToolUniverse-style config object. That config is the bridge between the agent framework and specialized scientific models.

Executable providers in the local prototype:

- `mock`: deterministic local model response for testing onboarding and provenance.
- `local_http`: POSTs the model payload to `endpoint_url` and expects a JSON object response.

Other providers can be registered as metadata and exported as ToolUniverse-style configs, but the local runner marks them as partial until a constrained executor is added.

Run integration:

1. Register a model in `/models`.
2. Select it on `/objectives/new`, or pass `"model_tool_names": ["your_model_name"]` in `run_config`.
3. The API resolves the names to stored configs.
4. LangGraph includes the model in `FIND_TOOLS`.
5. `EXECUTE_EVIDENCE_COLLECTION` invokes the model and records the normalized result in `tool_calls`, trace output, and evidence.

## Agent Runtime

Default:

- LangGraph.

Available/fallback:

- built-in deterministic state machine.

Optional future adapter:

- OpenClaw.

OpenClaw should remain optional because this project needs constrained, auditable biomedical execution. LangGraph is the right default for the scientific workflow state machine.

Current LangGraph node sequence:

1. `plan_research`
2. `find_tools`
3. `execute_evidence_collection`
4. `score_evidence`
5. `generate_hypotheses`
6. `critique_and_refine`
7. `propose_experiments`
8. `generate_report`

Every node appends an auditable trace entry with inputs, outputs, agent name, state name, and timestamp. If LangGraph is unavailable in the local environment, the same node functions run sequentially so the framework still works.

## LLM Providers

The framework supports provider config for:

- `mock`
- `openai`
- `anthropic`
- `gemini`
- `openai_compatible`
- `local_http`

Pass keys through environment variables rather than storing raw secrets in the database.

Example:

```powershell
$env:OPENAI_API_KEY = "..."
.\infra\scripts\run_local_question.ps1 -Question "Generate a therapeutic hypothesis for ACVR1-driven FOP." -LlmProvider openai -LlmModel gpt-4.1
```

## Execution Backends

Current:

- `inline`: run immediately in the API process.
- `background`: run via FastAPI background task.
- `queued`: persist run and execute with `python -m app.services.queue_worker`.

Planned:

- Docker worker.
- Cloud Run Job.
- Google Cloud Batch.
- Slurm/HPC adapter.

## Guardrail

This framework automates evidence-gathering and hypothesis generation. It does not validate clinical efficacy, safety, or therapeutic benefit.

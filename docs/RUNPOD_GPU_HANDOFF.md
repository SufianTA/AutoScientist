# RunPod GPU Handoff

This is the GPU handoff for the current AutoScientist benchmark path. Use the GPU only after local CPU validation passes; the GPU run is for scale, neural SciFlow Policy training, strict live-model evaluation, and final shareable artifacts.

## Prepared Locally

- `tools/run_autoscientist_bench.py`: public biomedical benchmark, ablations, realness gates, SciState Graph export, and model packaging.
- `tools/machine_preflight.py`: checks Python, packages, GPU, disk, API keys, network, and ToolUniverse readiness.
- `tools/build_public_benchmark_dataset.py`: generates public-data tasks from Open Targets and NCBI/PubMed.
- `tools/analyze_autoscientist_benchmark.py`: turns benchmark outputs into publishable coverage, ablation, and limitation reports.
- `tools/collect_review_package.py`: builds a sanitized review zip.
- `infra/runpod/bootstrap_autoscientist.sh`: installs the repo, dev dependencies, ToolUniverse extras, and neural policy dependencies.
- `infra/runpod/run_gpu_benchmark.sh`: runs strict GPU benchmark, trains SciFlow Policy, and packages artifacts.

## Bring Up The Machine

Use a PyTorch CUDA RunPod image on one H100 or comparable GPU. Keep `/workspace` as the persistent volume, expose SSH, and clone this repository into `/workspace/AutoScientist`.

## Bootstrap

```bash
cd /workspace
curl -L https://raw.githubusercontent.com/SufianTA/AutoScientist/main/infra/runpod/bootstrap_autoscientist.sh -o bootstrap_autoscientist.sh
bash bootstrap_autoscientist.sh
```

## Add Keys

Create `/workspace/AutoScientist/.env` with only the provider keys you plan to use:

```bash
cd /workspace/AutoScientist
nano .env
```

Example:

```text
ANTHROPIC_API_KEY=...
GEMINI_API_KEY=...
OPENAI_API_KEY=...
```

Do not commit this file.

## Preflight

```bash
cd /workspace/AutoScientist
/opt/autosci-venv/bin/python tools/machine_preflight.py --require-gpu --output-dir outputs/preflight
```

## Strict GPU Run

The RunPod script is strict by default: it requires a real LLM, live public context, SciFlow Policy, neural policy training, expected integrations, completion gates, score gates, and state-graph gates.

Small acceptance run:

```bash
cd /workspace/AutoScientist
LLM_PROVIDER=anthropic \
LLM_MODEL=claude-sonnet-4-6 \
LLM_API_KEY_ENV_VAR=ANTHROPIC_API_KEY \
LIMIT=12 \
REPLICATES=1 \
bash infra/runpod/run_gpu_benchmark.sh
```

Target a specific public-data case/template:

```bash
LLM_PROVIDER=anthropic \
LLM_MODEL=claude-sonnet-4-6 \
LLM_API_KEY_ENV_VAR=ANTHROPIC_API_KEY \
CASE_IDS="il6_rheumatoid_arthritis" \
TEMPLATE_IDS="experiment_design" \
LIMIT=1 \
REPLICATES=1 \
bash infra/runpod/run_gpu_benchmark.sh
```

Larger run:

```bash
LIMIT=100 REPLICATES=3 EPOCHS=120 bash infra/runpod/run_gpu_benchmark.sh
```

## Expected Outputs

- `outputs/preflight/`: machine readiness reports.
- `outputs/autoscientist_bench/<timestamp>/benchmark_summary.md`: main benchmark result.
- `outputs/autoscientist_bench/<timestamp>/benchmark_summary.json`: machine-readable benchmark result.
- `outputs/autoscientist_bench/<timestamp>/scistate_graph.json`: SciState Graph export.
- `outputs/autoscientist_bench/<timestamp>/models/`: SciFlow Policy artifacts.
- `outputs/autoscientist_bench/<timestamp>/packages/`: package from `package_policy_model`.
- `outputs/autoscientist_bench/<timestamp>/analysis/`: post-run benchmark analysis.
- `outputs/review_packages/*.zip`: sanitized shareable bundle.

## Stop Criteria

Stop the machine after:

- preflight is not failing,
- `benchmark_summary.md` exists,
- `Realness Gates` passed,
- `analysis/benchmark_analysis_*.md` exists,
- a review package zip exists,
- secret scan in `package_result.json` reports zero matches,
- the package has been copied or pushed somewhere durable.

## What To Look For

The result is worth sharing if:

- `full` completes all strict-gated runs,
- `full` beats `no_memory` on replay/provenance value,
- `full` beats `no_public_tools` on grounding value,
- `full` beats `no_sciflow` or shows controller coverage after a policy exists,
- every manifest-declared expected integration executes for matching tasks,
- SciState Graph has hypotheses, entities, experiments, tools, and replay nodes,
- the package includes a model card, graph export, benchmark summary, analysis report, and replay examples.

Do not claim biomedical discovery superiority unless the run includes expert or rubric-scored biological correctness labels. The defensible claim is stronger: AutoScientist is a reproducible scientific execution runtime with public-data grounding, persistent state, ablation evidence, and a trained workflow controller.

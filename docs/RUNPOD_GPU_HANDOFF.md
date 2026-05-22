# RunPod GPU Handoff

This is the exact handoff for the later H100 run. The goal is that the GPU machine is used only
for scale, neural policy training, and final artifact generation.

## What Is Already Prepared Locally

- `tools/run_autoscientist_bench.py`: public benchmark, ablations, scoring, state graph export, model package handoff.
- `tools/machine_preflight.py`: checks Python, packages, GPU, disk, keys, network, ToolUniverse, and Medea adapter availability.
- `tools/collect_review_package.py`: builds a sanitized zip for sharing.
- `benchmarks/autoscientist_bench_v0_1.json`: public biomedical benchmark seed cases.
- `infra/runpod/bootstrap_autoscientist.sh`: machine bootstrap.
- `infra/runpod/run_gpu_benchmark.sh`: full GPU benchmark and packaging command.

## Bring Up The Machine

Use a PyTorch CUDA image on RunPod with an H100 or comparable GPU. A smaller GPU can run the
runtime, but the H100 is useful for larger neural-policy training and future local foundation-model
serving.

Expose SSH and keep `/workspace` as the persistent volume.

## Bootstrap

SSH into the pod and run:

```bash
cd /workspace
curl -L https://raw.githubusercontent.com/SufianTA/AutoScientist/main/infra/runpod/bootstrap_autoscientist.sh -o bootstrap_autoscientist.sh
bash bootstrap_autoscientist.sh
```

Optional full Medea install:

```bash
INSTALL_MEDEA=1 bash bootstrap_autoscientist.sh
```

Medea’s own README recommends cloning `mims-harvard/Medea`, using `uv`, creating a Python 3.10
environment, installing editable, and optionally downloading MedeaDB for full data-backed analysis.
Without MedeaDB, AutoScientist should treat Medea as adapter/smoke integration rather than a full
module-level omics run.

## Add Keys

Create `/workspace/AutoScientist/.env` with only the keys you want to use:

```bash
cd /workspace/AutoScientist
nano .env
```

Example:

```text
ANTHROPIC_API_KEY=...
GEMINI_API_KEY=...
OPENROUTER_API_KEY=...
MEDEA_PYTHON=/opt/medea-py310/bin/python
```

Do not commit this file.

## Preflight

```bash
cd /workspace/AutoScientist
/opt/autosci-venv/bin/python tools/machine_preflight.py --require-gpu --output-dir outputs/preflight
```

If using Medea:

```bash
/opt/autosci-venv/bin/python tools/machine_preflight.py --require-gpu --require-medea --output-dir outputs/preflight
```

## Full GPU Run

Mock-provider scale run:

```bash
cd /workspace/AutoScientist
bash infra/runpod/run_gpu_benchmark.sh
```

Live frontier-model subset:

```bash
LLM_PROVIDER=anthropic \
LLM_MODEL=claude-sonnet-4-6 \
LLM_API_KEY_ENV_VAR=ANTHROPIC_API_KEY \
REQUIRE_REAL_LLM=1 \
LIMIT=12 \
REPLICATES=1 \
bash infra/runpod/run_gpu_benchmark.sh
```

Medea adapter smoke included:

```bash
MEDEA_PYTHON=/opt/medea-py310/bin/python \
LIMIT=12 \
REPLICATES=1 \
bash infra/runpod/run_gpu_benchmark.sh
```

Larger run:

```bash
LIMIT=100 REPLICATES=3 EPOCHS=120 bash infra/runpod/run_gpu_benchmark.sh
```

## Expected Outputs

- `outputs/preflight/`: machine readiness reports.
- `outputs/autoscientist_bench/<timestamp>/benchmark_summary.md`: main result.
- `outputs/autoscientist_bench/<timestamp>/benchmark_summary.json`: machine-readable result.
- `outputs/autoscientist_bench/<timestamp>/scistate_graph.json`: SciState Graph export.
- `outputs/autoscientist_bench/<timestamp>/models/`: SciFlow Policy artifacts.
- `outputs/autoscientist_bench/<timestamp>/packages/`: package created by `package_policy_model`.
- `outputs/review_packages/*.zip`: sanitized shareable bundle.

## Stop Criteria

Stop the machine after:

- preflight is not failing,
- benchmark summary exists,
- review package zip exists,
- secret scan in `package_result.json` reports zero matches,
- the zip has been copied or pushed somewhere durable.

## What To Look For

The result is worth sharing if:

- `full` completes most runs,
- `full` beats `no_memory` on replay/provenance value,
- `full` beats `no_public_tools` on grounding value,
- `full` records SciFlow controller advice after a policy exists,
- the state graph has hypotheses, entities, experiments, tools, and replay nodes,
- the package includes a model card and replay examples.

Do not claim discovery superiority unless the run includes expert or rubric-scored biomedical tasks
and no-memory/no-controller ablations.

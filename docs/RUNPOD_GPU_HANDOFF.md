# RunPod GPU Handoff

This handoff is for the final paid GPU pass. Keep the scope narrow: biomedical therapeutic discovery tasks grounded in public evidence, with ablations that test whether memory, public tools, and SciFlow Policy add measurable value.

## What Is Ready

- `benchmarks/autoscientist_bench_v0_2_public.json`: public biomedical target-disease tasks generated from Open Targets and NCBI/PubMed context.
- `tools/run_autoscientist_bench.py`: benchmark runner with ablations, realness gates, SciState Graph export, replay bundles, and policy packaging.
- `tools/machine_preflight.py`: Python, GPU, disk, API key, network, ToolUniverse, and package checks.
- `tools/analyze_autoscientist_benchmark.py`: post-run report for coverage, ablation deltas, controller value, and limitations.
- `tools/collect_review_package.py`: sanitized shareable package builder.
- `infra/runpod/bootstrap_autoscientist.sh`: one-command pod bootstrap.
- `infra/runpod/run_gpu_benchmark.sh`: two-phase GPU benchmark: seed a SciFlow model, then run strict live evaluation.

## Why The Script Has Two Phases

A fresh RunPod clone does not include the local SQLite memory database or prior policy artifacts. The script therefore runs:

1. `seed` phase: bounded live biomedical runs that create replay traces and train the first SciFlow Policy.
2. `strict` phase: live biomedical evaluation with `full`, `no_memory`, `no_public_tools`, and `no_sciflow` ablations, using the seeded policy as the controller.

Do not skip the seed phase on a fresh pod unless a valid policy model is already present.

## Bring Up The Machine

Use one H100-class GPU with a PyTorch CUDA image. Mount persistent storage at `/workspace`, expose SSH, and keep the pod running only while executing the commands below.

Recommended defaults:

- GPU: H100 80GB or equivalent.
- Template: PyTorch CUDA.
- Persistent volume: `/workspace`.
- HTTP port: `8888` optional for Jupyter.
- SSH: enabled.

## Bootstrap

```bash
cd /workspace
curl -L https://raw.githubusercontent.com/SufianTA/AutoScientist/main/infra/runpod/bootstrap_autoscientist.sh -o bootstrap_autoscientist.sh
bash bootstrap_autoscientist.sh
```

## Add Keys

Create `/workspace/AutoScientist/.env` with provider keys only. Do not commit it.

```bash
cd /workspace/AutoScientist
nano .env
```

Example:

```text
GEMINI_API_KEY=...
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
```

The final commands below use Gemini by default because it is the currently configured live provider path. Qworld is disabled by default in the GPU script to avoid uncontrolled criteria-generation cost during the final benchmark.

## Preflight

```bash
cd /workspace/AutoScientist
/opt/autosci-venv/bin/python tools/machine_preflight.py --require-gpu --output-dir outputs/preflight
```

Do not continue if this fails.

## Controlled Acceptance Run

Run this first. It is sized to prove the full path without burning the whole budget.

```bash
cd /workspace/AutoScientist
LLM_PROVIDER=gemini \
LLM_MODEL=gemini-2.5-flash \
LLM_API_KEY_ENV_VAR=GEMINI_API_KEY \
MANIFEST=benchmarks/autoscientist_bench_v0_2_public.json \
SEED_POLICY=1 \
SEED_LIMIT=8 \
SEED_REPLICATES=1 \
LIMIT=12 \
REPLICATES=1 \
EPOCHS=80 \
LLM_MAX_TOKENS=512 \
PUBLIC_TIMEOUT_SECONDS=8 \
STRATEGY_REPAIR_MAX_QUERIES=2 \
DISABLE_QWORLD=1 \
bash infra/runpod/run_gpu_benchmark.sh
```

Expected outputs:

- `outputs/preflight/`: GPU and environment checks.
- `outputs/autoscientist_bench/<seed_timestamp>/`: seed run, first policy model, replay traces.
- `outputs/autoscientist_bench/<strict_timestamp>/benchmark_summary.md`: main result to read first.
- `outputs/autoscientist_bench/<strict_timestamp>/benchmark_summary.json`: machine-readable result.
- `outputs/autoscientist_bench/<strict_timestamp>/scistate_graph.json`: SciState Graph export.
- `outputs/autoscientist_bench/<strict_timestamp>/models/`: SciFlow Policy artifacts.
- `outputs/autoscientist_bench/<strict_timestamp>/analysis/`: benchmark analysis.
- `outputs/review_packages/*.zip`: sanitized package for sharing.

## Larger Run

Only run this after the controlled acceptance run passes.

```bash
cd /workspace/AutoScientist
LLM_PROVIDER=gemini \
LLM_MODEL=gemini-2.5-flash \
LLM_API_KEY_ENV_VAR=GEMINI_API_KEY \
MANIFEST=benchmarks/autoscientist_bench_v0_2_public.json \
SEED_POLICY=1 \
SEED_LIMIT=16 \
SEED_REPLICATES=1 \
LIMIT=48 \
REPLICATES=2 \
EPOCHS=120 \
LLM_MAX_TOKENS=512 \
PUBLIC_TIMEOUT_SECONDS=8 \
STRATEGY_REPAIR_MAX_QUERIES=2 \
DISABLE_QWORLD=1 \
bash infra/runpod/run_gpu_benchmark.sh
```

## Single-Case Debug Run

Use this only if the acceptance run fails and you need a cheap diagnosis.

```bash
cd /workspace/AutoScientist
LLM_PROVIDER=gemini \
LLM_MODEL=gemini-2.5-flash \
LLM_API_KEY_ENV_VAR=GEMINI_API_KEY \
CASE_IDS="il6_rheumatoid_arthritis" \
TEMPLATE_IDS="experiment_design" \
SEED_POLICY=1 \
SEED_LIMIT=1 \
LIMIT=1 \
REPLICATES=1 \
EPOCHS=40 \
DISABLE_QWORLD=1 \
bash infra/runpod/run_gpu_benchmark.sh
```

## Pass Criteria

The final result is worth sharing only if:

- `Realness Gates` passed.
- `full` completion rate is `1.0`.
- `full` strict scientific quality beats `no_public_tools`.
- `full` shows replay runs, public biomedical calls, ToolUniverse/OpenTargets calls, and SciFlow controller applications.
- `no_sciflow` has zero controller applications.
- SciState Graph contains hypotheses, entities, experiments, tools, and replay nodes.
- The review package has zero secret-scan matches.
- The analysis report names limitations honestly.

The most defensible claim is not "the model discovers better biology." The defensible claim is: AutoScientist is a reproducible biomedical scientific execution runtime with public-data grounding, persistent scientific state, ablation evidence, replayable provenance, and a trained workflow controller.

## Stop Criteria

Stop the pod after:

- `outputs/review_packages/*.zip` exists,
- `benchmark_summary.md` exists for the strict run,
- `analysis/benchmark_analysis_*.md` exists,
- `package_result.json` reports no secret matches,
- the package has been copied to durable storage or pushed through a safe release workflow.

Do not leave the pod running after the package is secured.

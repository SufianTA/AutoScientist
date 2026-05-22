# AutoScientist-Bench v0.1

AutoScientist-Bench is the pre-GPU validation path for AutoScientist. It creates public biomedical
tasks, runs the runtime through controlled ablations, exports traces and the SciState Graph, then
packages the latest SciFlow Policy model for review.

## What This Proves

It is meant to prove integration and infrastructure value before spending on GPU time:

- AutoScientist can run repeatable public biomedical tasks.
- Full runtime output can be compared with `no_memory`, `no_sciflow`, `no_medea`, and `no_public_tools` ablations.
- Runs leave replay bundles, tool traces, state graph exports, and model packages.
- SciFlow Policy is used as a workflow-controller advisory layer when enabled.

It does not prove biomedical discovery superiority by itself. That requires larger public benchmarks,
expert scoring, and live-model validation.

## CPU Dry Run

Use this first on a laptop or CPU VM:

```bash
python tools/run_autoscientist_bench.py \
  --limit 3 \
  --ablations full no_memory no_public_tools \
  --offline-public-context
```

Expected outputs:

- `outputs/autoscientist_bench/<timestamp>/benchmark_tasks.json`
- `outputs/autoscientist_bench/<timestamp>/benchmark_summary.json`
- `outputs/autoscientist_bench/<timestamp>/benchmark_summary.md`
- `outputs/autoscientist_bench/<timestamp>/scistate_graph.json`
- `outputs/autoscientist_bench/<timestamp>/packages/`

## Machine Preflight

Before a larger local or GPU run:

```bash
python tools/machine_preflight.py --output-dir outputs/preflight
```

On RunPod:

```bash
python tools/machine_preflight.py --require-gpu --output-dir outputs/preflight
```

## Live Public-Context Dry Run

Once the offline run works, allow public metadata prefetching from NCBI and Open Targets:

```bash
python tools/run_autoscientist_bench.py \
  --limit 6 \
  --ablations full no_memory no_public_tools
```

This does not require paid model keys if `--llm-provider mock` is left as default. It still exercises
public biomedical grounding paths where available.

## Build A Public-Data Manifest

Generate a benchmark manifest from live Open Targets target-disease associations and NCBI/PubMed counts:

```bash
python tools/build_public_benchmark_dataset.py \
  --output-manifest benchmarks/autoscientist_bench_v0_2_public.json \
  --max-targets 8 \
  --associations-per-target 3 \
  --include-omics-template
```

This writes:

- `benchmarks/autoscientist_bench_v0_2_public.json`
- `benchmarks/autoscientist_bench_v0_2_public.jsonl`
- `benchmarks/autoscientist_bench_v0_2_public.md`

Use this manifest for serious runs:

```bash
python tools/run_autoscientist_bench.py \
  --manifest benchmarks/autoscientist_bench_v0_2_public.json \
  --limit 24 \
  --ablations full no_memory no_public_tools no_sciflow \
  --llm-provider anthropic \
  --llm-model claude-sonnet-4-6 \
  --llm-api-key-env-var ANTHROPIC_API_KEY \
  --require-real-llm \
  --enable-sciflow-policy \
  --train-neural-policy \
  --strict-real-run \
  --require-expected-integrations
```

## SciFlow Controller Check

After one benchmark run has trained a policy artifact, verify that the runtime uses SciFlow as an
advisory controller:

```bash
python tools/run_autoscientist_bench.py \
  --limit 1 \
  --ablations full \
  --offline-public-context \
  --enable-sciflow-policy \
  --skip-policy-training \
  --skip-package
```

In `benchmark_summary.md`, `Controller runs` should be `1`.

## Frontier-Model Smoke Run

After the CPU dry run passes, run a small live-model smoke:

```bash
python tools/run_autoscientist_bench.py \
  --limit 3 \
  --ablations full no_memory \
  --llm-provider anthropic \
  --llm-model claude-sonnet-4-6 \
  --llm-api-key-env-var ANTHROPIC_API_KEY \
  --require-real-llm \
  --enable-sciflow-policy
```

Use `--llm-provider gemini --llm-api-key-env-var GEMINI_API_KEY` if testing Gemini instead.

## RunPod GPU Scale-Up

Only rent the H100 after the CPU run produces valid artifacts and the summary shows all full runs
completed. For a real acceptance run, require hard gates:

```bash
python tools/run_autoscientist_bench.py \
  --limit 100 \
  --replicates-per-case 3 \
  --ablations full no_memory no_medea no_public_tools no_sciflow \
  --llm-provider anthropic \
  --llm-model claude-sonnet-4-6 \
  --llm-api-key-env-var ANTHROPIC_API_KEY \
  --require-real-llm \
  --enable-sciflow-policy \
  --train-neural-policy \
  --neural-epochs 120 \
  --strict-real-run \
  --require-expected-integrations \
  --min-full-completion-rate 1.0 \
  --min-full-mean-score 85 \
  --min-neural-holdout-top1 0.5 \
  --min-state-graph-nodes 1
```

To force an omics/Medea task instead of relying on the first tasks in the manifest:

```bash
python tools/run_autoscientist_bench.py \
  --case-ids il6_rheumatoid_arthritis \
  --template-ids experiment_design \
  --limit 1 \
  --ablations full \
  --llm-provider anthropic \
  --llm-model claude-sonnet-4-6 \
  --llm-api-key-env-var ANTHROPIC_API_KEY \
  --require-real-llm \
  --medea-python /opt/medea-py310/bin/python \
  --enable-sciflow-policy \
  --train-neural-policy \
  --strict-real-run \
  --require-expected-integrations
```

Then package a shareable bundle:

```bash
python tools/package_policy_model.py \
  --output-dir outputs/packages \
  --replay-limit 50 \
  --graph-limit 2000
```

## How To Read The Results

Open `benchmark_summary.md` first.

Key checks:

- `Realness Gates` should say `Passed: true` for strict live runs.
- `full` mean score should be higher than `no_memory` and `no_public_tools`.
- `full` should have replay runs and public-tool runs.
- `full` should show controller advice runs once a SciFlow model exists.
- tasks whose manifest declares `medea`, `tooluniverse`, or `sciflow_policy` should show those integrations executed.
- `scistate_graph.json` should contain hypotheses, entities, experiments, replay nodes, and tool nodes.
- The package zip should include a model card, manifest, state graph, and replay examples.

Then generate the analysis report:

```bash
python tools/analyze_autoscientist_benchmark.py \
  --bench-dir outputs/autoscientist_bench/<timestamp>
```

Read `analysis/benchmark_analysis_*.md` for integration coverage, ablation deltas, policy metrics,
supported claims, and limitations.

## What To Share

For a serious review package, share:

- `benchmark_summary.md`
- `benchmark_summary.json`
- `scistate_graph.json`
- `analysis/benchmark_analysis_*.md`
- the latest package zip from `packages/`
- a short note explaining that SciFlow Policy is a controller layer, not a replacement for foundation models.

Create the shareable zip:

```bash
python tools/collect_review_package.py
```

## Next Credibility Step

The next research-grade step is `AutoScientist-Bench v0.2`:

- 100 to 500 public biomedical tasks.
- Live frontier-model subset.
- No-memory and no-controller ablations.
- Expert or rubric scoring.
- Full Medea module-level omics tasks, not only smoke execution.
- Held-out evaluation for SciFlow Policy.

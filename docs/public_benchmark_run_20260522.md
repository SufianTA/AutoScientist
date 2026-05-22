# AutoScientist Public Benchmark Run - 2026-05-22

This run evaluates AutoScientist as a persistent scientific execution system using live Gemini reasoning, public biomedical tools, ToolUniverse/OpenTargets, SciState Graph memory/replay, and the SciFlow Policy workflow controller.

## Run Configuration

- Machine: RunPod NVIDIA H100 80GB HBM3.
- Benchmark: `benchmarks/autoscientist_bench_v0_2_public.json`.
- Domains: PCSK9/familial hypercholesterolemia, CFTR/cystic fibrosis, ACVR1/fibrodysplasia ossificans progressiva, TNF/rheumatoid arthritis, EGFR/non-small-cell lung carcinoma, APP/Alzheimer disease.
- Tasks: 24 task prompts, 96 total executions across `full`, `no_memory`, `no_public_tools`, and `no_sciflow`.
- LLM: Gemini 2.5 Flash via `GEMINI_API_KEY`.
- Strict gates: passed.

## Main Result

| Ablation | Runs | Completed | Mean Score | Replay Runs | Controller Applied | Mean Evidence | Mean Tool Calls |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| full | 24 | 24 | 100.00 | 24 | 24 | 7.75 | 15.25 |
| no_memory | 24 | 24 | 94.33 | 0 | 0 | 4.92 | 9.58 |
| no_public_tools | 24 | 24 | 95.33 | 24 | 0 | 2.00 | 2.00 |
| no_sciflow | 24 | 24 | 100.00 | 24 | 0 | 4.96 | 9.71 |

## What This Supports

- Persistent memory/replay adds measurable benchmark value: full runtime outscored `no_memory` by 5.67 mean points and produced 24/24 replayable runs.
- Public biomedical grounding adds measurable value: full runtime outscored `no_public_tools` by 4.67 mean points and increased mean evidence from 2.00 to 7.75 items.
- SciFlow Policy now changes execution behavior: score tied `no_sciflow` because the score is capped at 100, but full runtime added +5.54 mean tool calls, +2.79 mean evidence items, +1.96 public biomedical calls, and +0.84 ToolUniverse calls versus `no_sciflow`.
- The run produced a larger SciState Graph with 1,828 nodes, 7,372 edges, 192 hypotheses, 475 entities, 576 experiments, and 9 tools.

## SciFlow Policy Model

- Type: PyTorch neural workflow-policy controller, not a biomedical foundation model.
- Training examples: 10,727 workflow examples.
- Holdout examples: 2,240.
- Holdout top-1 accuracy: 0.8540.
- Holdout top-3 accuracy: 1.0000.
- Holdout MRR: 0.9242.
- Majority baseline top-1: 0.1866.

## Local Artifacts

- Review package: `outputs/runpod_downloads/autoscientist_public_24task_sciflow_20260522.zip`.
- Benchmark summary: `outputs/runpod_downloads/benchmark_summary.md`.
- Benchmark analysis: `outputs/runpod_downloads/benchmark_analysis_1779439327.md`.
- Packaged SciFlow model: `outputs/runpod_downloads/neural_scientific_workflow_policy_20260522084143.zip`.

## Caveats

- These metrics are integration, execution, provenance, replay, and controller-behavior metrics; they are not expert-scored biological discovery claims.
- `no_sciflow` tied full on capped score, so SciFlow's demonstrated value here is operational retrieval depth, not yet expert-validated answer quality.
- The next credibility step is expert/rubric scoring on biomedical correctness and an uncapped scientific-quality metric.

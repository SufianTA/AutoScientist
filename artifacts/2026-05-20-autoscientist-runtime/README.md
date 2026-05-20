# AutoScientist Runtime Artifact Bundle - 2026-05-20

This folder contains the sanitized artifacts from the May 20, 2026 AutoScientist harvest run.

## System Names

- **SciState Graph**: persistent scientific memory and provenance graph for hypotheses, evidence, entities, experiments, tool traces, and confidence signals.
- **SciFlow Policy**: PyTorch workflow-controller model trained from AutoScientist execution traces to predict next scientific actions, tool choices, and workflow states.

## Compute

- Provider: RunPod
- GPU: single NVIDIA H100 PCIe, 80 GB VRAM
- Driver/CUDA visible to container: NVIDIA driver 580.159.04, CUDA 13.0
- Training runtime: Python 3.12, PyTorch CUDA runtime in `/opt/autosci-venv`
- Training scope: SciFlow Policy controller model, not a foundation LLM

## Key Results

- 50-task harvest: 50/50 completed
- Average benchmark value score: 83.0
- Integrations exercised in the 50-task harvest: Medea smoke 50/50, public biomedical tools 50/50, local board/replay 50/50, ToolUniverse/OpenTargets 15/50
- SciFlow Policy training examples: 2,257 trace examples
- SciFlow Policy holdout metrics: top-1 0.9205, top-3 1.0, MRR 0.9603
- SciState Graph export: 1,106 nodes, 2,795 edges, 69 hypotheses, 615 entities, 207 proposed experiments

## Files

| File | What it is |
| --- | --- |
| `autoscientist_all_run_outputs_1779257902.tar.gz` | Full sanitized artifact archive with benchmark outputs, model artifacts, package zips, graph exports, replay data, docs, and SQLite memory snapshot. |
| `sciflow_policy_package_20260520065055.zip` | Portable package for the final SciFlow Policy model, including model weights, manifest, model card, replay bundles, and graph context. |
| `sciflow_policy_model_20260520065055.pt` | Raw PyTorch weights for the final SciFlow Policy model. |
| `sciflow_policy_manifest_20260520065055.json` | Training manifest with architecture, dataset summary, train/holdout split, and metrics. |
| `sciflow_policy_model_card_20260520065055.md` | Short model card explaining intended use, limitations, and next validation work. |
| `fifty_task_harvest_1779257902.md` | Human-readable summary of the 50-task benchmark harvest. |
| `fifty_task_harvest_1779257902.json` | Machine-readable benchmark summary with per-case run IDs, scores, integration counts, and postprocessing logs. |
| `scistate_graph_1779259857.md` | Human-readable SciState Graph export summary. |
| `scistate_graph_1779259857.json` | Machine-readable SciState Graph export. |
| `live_anthropic_smoke_run_5e48621eb8f0.json` | Live Anthropic smoke run proving a real frontier-model path can complete with the runtime. |
| `gemini_quota_smoke_run_3de4964d7909.json` | Gemini smoke run artifact showing fast provider execution until quota exhaustion. |
| `medea_tool_smoke_run_2a5da95eefb4.json` | Medea plus public biomedical tool smoke run artifact. |

## Interpretation

These artifacts demonstrate a working persistent scientific runtime: objective classification, tool routing, evidence capture, Medea smoke execution, replay logging, SciState Graph persistence, and SciFlow Policy training. The 50-task harvest is a reproducible systems/integration benchmark, not a final claim of biomedical discovery superiority.

## Next Validation Work

- Run a larger live-provider benchmark with Claude/Gemini/open-source models under stable quota.
- Add expert or rubric-based biomedical output scoring.
- Compare against no-memory, no-policy, static-workflow, and majority-action baselines.
- Expand ToolUniverse/OpenTargets and Medea beyond smoke coverage.
- Train SciFlow Policy on higher-quality traces and evaluate whether it improves live autonomous-science workflows.

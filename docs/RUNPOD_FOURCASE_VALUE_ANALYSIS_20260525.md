# RunPod Four-Case Value Analysis - 2026-05-25

This document summarizes the strict real RunPod benchmark completed on 2026-05-25 for the BioTruth v0.2 four-case canary.

## Run Configuration

- Machine: RunPod H100 pod with 80 GB GPU memory.
- Code commit: `781a08c`.
- Mode: strict real run.
- LLM provider: Anthropic.
- Model: `claude-sonnet-4-6`.
- Scoring mode: heuristic BioTruth triage.
- Cases: 4 target-disease tasks selected to cover strong support, moderate support, conflicting evidence, and insufficient evidence.
- Ablations: `full`, `plain_llm`, `no_memory`, `no_public_tools`, `no_sciflow`.
- Result count: 20 task/ablation artifacts.
- Export archive: `outputs/runpod_exports/fourcase_value_run_20260525_175307.tar.gz`.

## Artifacts

- Benchmark summary: `outputs/runpod_exports/outputs/autoscientist_bench_v02_fourcase_value/20260525_175307/benchmark_summary.md`
- BioTruth scores: `outputs/runpod_exports/outputs/autoscientist_bench_v02_fourcase_value/20260525_175307/biotruth_scores.md`
- Benchmark analysis: `outputs/runpod_exports/outputs/autoscientist_bench_v02_fourcase_value/20260525_175307/analysis/benchmark_analysis_1779735631.md`
- Scientific state graph: `outputs/runpod_exports/outputs/autoscientist_bench_v02_fourcase_value/20260525_175307/scistate_graph.json`
- Neural workflow policy: `outputs/runpod_exports/outputs/autoscientist_bench_v02_fourcase_value/20260525_175307/models/neural_scientific_workflow_policy_20260525190017/manifest.json`

## What Worked

The strict realness gates passed. All four full-system runs completed, and all required full-system integrations executed: public biomedical tools, ToolUniverse, local board logging, memory replay, and SciFlow policy.

The full system produced much richer evidence than plain LLM mode. Across the four cases, full mode averaged 31.75 evidence items and 52.25 tool calls, while plain LLM mode averaged 2 evidence items and 0 tool calls.

The full system strongly outperformed the no-public-tools and plain-LLM baselines under the current integration/provenance scoring:

| Comparison | Full Mean | Ablation Mean | Delta |
| --- | ---: | ---: | ---: |
| Full vs plain LLM | 100 | 82 | +18 |
| Full vs no public tools | 100 | 65 | +35 |
| Full vs no memory | 100 | 100 | 0 |
| Full vs no SciFlow | 100 | 100 | 0 |

Under the BioTruth heuristic correctness triage, full mode was also stronger than the non-grounded baselines:

| Ablation | Mean BioTruth Score | Pass Rate | Critical Failure Rate |
| --- | ---: | ---: | ---: |
| full | 83.25 | 0.50 | 0.25 |
| no_memory | 82.25 | 0.50 | 0.25 |
| no_sciflow | 83.25 | 0.50 | 0.25 |
| plain_llm | 50.25 | 0.00 | 1.00 |
| no_public_tools | 51.25 | 0.00 | 1.00 |

This is the clearest value signal from the run: public biomedical grounding is not cosmetic; removing it sharply reduces score, auditability, and decision quality.

## What Failed

The overall strict acceptance failed because the full system made a critical abstention/calibration error on the insufficient-evidence case:

- Case: `egfr_rheumatoid_arthritis_insufficient`
- Expected decision: `abstain`
- Full BioTruth score: `66`
- Failure: `incorrect_abstention_behavior`
- Low dimensions: `scientific_decision_correctness`, `counterevidence_and_abstention`

This is the most important technical finding. The system can gather evidence and produce auditable outputs, but it is still too willing to proceed when the benchmark expects abstention.

The full system also underperformed the pass threshold on the strong TNF/rheumatoid arthritis case because the heuristic scorer penalized counterevidence/abstention handling:

- Case: `tnf_rheumatoid_arthritis_strong`
- Expected decision: `support_allowed`
- Full BioTruth score: `85`
- Failure type: not critical, but minimum-dimension failure in `counterevidence_and_abstention`

That may be partly scoring calibration, but it still identifies a real presentation problem: even when supporting a target, the report needs clearer counterevidence and limitation structure.

Memory and SciFlow showed weaker score impact than public tools in this run. They increased evidence/tool-call depth, but they did not improve decision accuracy relative to no-memory or no-SciFlow on this small canary. That does not mean they are useless; it means their value is not yet strongly demonstrated by this benchmark.

## Model Result

The neural Scientific Workflow Policy trained successfully from the accumulated execution traces:

- Examples: 47,320
- Holdout top-1 accuracy: 0.8373
- Holdout top-3 accuracy: 0.9786
- Holdout MRR: 0.9037
- Majority baseline top-1: 0.2312

This shows the policy model learns workflow-action patterns from traces, but it is not yet proof that the model improves scientific correctness. The next benchmark must test policy-driven behavior against stronger decision-quality outcomes.

## What This Proves

This run proves that the system can execute a strict, real, auditable biomedical workflow end to end on a GPU machine using live LLM calls, live public biomedical tools, ToolUniverse, persistent memory, replay artifacts, and policy training.

It also proves that public biomedical grounding materially improves the current system over plain LLM and no-public-tool baselines.

## What This Does Not Prove Yet

This run does not prove that the system is a validated AI scientist. It does not establish expert-level biological correctness, and it does not yet show that memory or SciFlow policy materially improve correctness across diverse cases.

The biggest blocker is abstention. A credible system must know when not to make a therapeutic-target claim.

## Next Engineering Priority

The next system improvement should be an evidence-calibrated decision gate before final report generation.

The gate should force the final decision into one of:

- `support_allowed`
- `tentative_only`
- `conflicting`
- `abstain`

The gate should use structured signals already present in the run:

- OpenTargets association strength and rank.
- PubMed count and evidence availability.
- ToolUniverse execution status.
- Clinical or translational precedence.
- Contradiction/counterevidence flags.
- Safety and failure evidence.
- Memory/replay consistency.
- BioTruth expected capability coverage.

For low-evidence cases, the system should default toward abstention unless enough independent evidence supports proceeding. This should be implemented as a general calibrated decision layer, not as case-specific hardcoding.

## Recommended Next Benchmark

After implementing the decision gate, rerun the same four-case canary first. The acceptance target should be:

- Full completion rate: 1.0
- Full BioTruth mean score: at least 85
- Full pass rate: at least 0.75
- Full critical failure rate: 0
- Abstention accuracy: 1.0 on insufficient-evidence cases
- Full still beating `plain_llm` and `no_public_tools` by at least 15 points

Only after passing that should the project run the larger 20- or 48-task suite.

# End-to-End Discovery Case Studies

AutoScientist is evaluated here as a scientific discovery acceleration system, not only as a set of isolated components.

The core question is:

> Can the system start from a biomedical target-disease question, gather public evidence, synthesize a bounded scientific position, propose next experiments, preserve provenance, and produce an artifact a scientist can audit?

## What Was Generated

The discovery-case-study generator converts raw benchmark traces into scientist-facing dossiers.

Each dossier includes:

- the original scientific objective;
- the target-disease position produced by the system;
- evidence highlights from public tools and ToolUniverse/OpenTargets;
- weak or failed evidence branches preserved by the system;
- prioritized next experiments and decision gates;
- ablation evidence when available;
- paths to full replayable traces and the SciState graph.

## Artifacts

- `outputs/discovery_case_studies/biotruth_100_breadth_cases/`: 25 target-disease case studies from the 100-task breadth run.
- `outputs/discovery_case_studies/biotruth_100_breadth_cases.zip`: shareable archive of those 25 case studies.
- `outputs/discovery_case_studies/biotruth_20_ablation_cases/`: 5 target-disease case studies with full/no-memory/no-public-tools/no-SciFlow comparisons.
- `outputs/discovery_case_studies/biotruth_20_ablation_cases.zip`: shareable archive of those ablation case studies.
- `pod_artifacts/autoscientist_discovery_case_studies_100_breadth.zip`: local copy of the 100-task case-study archive.
- `pod_artifacts/autoscientist_discovery_case_studies_20_ablation.zip`: local copy of the ablation case-study archive.

## What The 100-Task Run Shows

The 100-task breadth run completed 100/100 tasks using the full system.

It exercised:

- public biomedical calls;
- ToolUniverse/OpenTargets calls;
- SciFlow workflow policy guidance;
- replayable memory/provenance;
- state-graph export;
- neural workflow policy training.

The judge-scored BioTruth review reported:

- mean weighted score: 85.64;
- median weighted score: 91.0;
- pass rate: 0.91;
- critical failure rate: 0.08;
- high evidence certainty on 86/100 scored outputs.

This supports the claim that AutoScientist can produce useful, inspectable biomedical research artifacts across many known target-disease settings.

## What The 20-Task Ablation Shows

The 20-task ablation run completed 80/80 runs:

| Mode | Runs | Mean score | Strict quality | Mean evidence | Mean tool calls |
| --- | ---: | ---: | ---: | ---: | ---: |
| full | 20 | 100 | 100 | 16.65 | 21.1 |
| no_memory | 20 | 100 | 95 | 13.55 | 16.7 |
| no_public_tools | 20 | 65 | 54 | 2.0 | 0 |
| no_sciflow | 20 | 100 | 95 | 13.7 | 16.9 |

The strongest demonstrated dependency is public biomedical execution: removing public tools caused the largest drop.

Memory and SciFlow did not change the headline score on this easier subset, but they improved strict quality, traceability, evidence depth, and tool coverage.

## Model Layer

The SciFlow neural policy is a workflow controller, not a biomedical foundation model.

In the ablation run it trained on 31,836 workflow examples using PyTorch:

- holdout top-1 accuracy: 0.8601;
- holdout top-3 accuracy: 0.9981;
- holdout MRR: 0.9259;
- majority baseline top-1 accuracy: 0.1942.

Its role is to guide scientific workflow actions such as tool execution, evidence scoring, replay, and follow-up searches.

## Honest Claim

AutoScientist now has evidence for the following claim:

> It can execute end-to-end biomedical target-disease research workflows that gather public evidence, synthesize a bounded scientific position, propose next experiments, and preserve auditable traces.

It should not yet be described as autonomously proving new biology.

## Remaining Scientific Gaps

The main gaps are:

- stronger expert biological correctness review;
- harder tasks where memory and workflow policy must change final decisions, not only trace quality;
- better filtering of irrelevant literature branches;
- larger prospective runs on unfamiliar or under-characterized target-disease questions;
- direct comparison against human-curated baselines and simpler LLM-only pipelines.

## How To Regenerate

```bash
python tools/build_discovery_case_study.py \
  --bench-dir tmp_breadth_extract/autoscientist_biotruth_100_task_breadth/benchmark_run \
  --output-dir outputs/discovery_case_studies/biotruth_100_breadth_cases

python tools/build_discovery_case_study.py \
  --bench-dir tmp_ablation_extract/20260523_182607 \
  --output-dir outputs/discovery_case_studies/biotruth_20_ablation_cases
```


# AutoScientist Baseline: 2026-05-24

This document freezes the current AutoScientist baseline before the scientific validation upgrade work begins.

## Baseline Identity

- Git tag: `autosci-baseline-biotru-4case-20260524`
- Commit: `cbc9d71`
- Baseline run: BioTruth 4-case canary
- Run mode: strict real run
- LLM provider: Anthropic
- Model used in run: `claude-sonnet-4-6`
- Machine: RunPod H100-class GPU pod
- Local artifact package: `pod_artifacts/biotruth_4_case_canary/autoscientist_biotruth_4_case_canary_20260524_145750_complete.zip`
- Repo summary artifacts: `docs/results/biotruth_4_case_canary_20260524/`

## What Was Tested

The canary ran four target-disease cases:

1. `IL6` and rheumatoid arthritis.
2. `TNF` and inflammatory bowel disease.
3. `BRAF` and melanoma.
4. `EGFR` and lung adenocarcinoma.

Each case ran under four variants:

1. `full`
2. `no_memory`
3. `no_public_tools`
4. `no_sciflow`

Total outputs:

- 4 cases.
- 4 variants per case.
- 16/16 run artifacts completed.

## Baseline Results

Runtime gates:

- Strict real-run gates passed.
- Required full integrations present:
  - `local_board`
  - `memory_replay`
  - `public_biomedical`
  - `sciflow_policy`
  - `tooluniverse`
- Full completion rate: `1.0`
- Full internal mean score: `100.0`
- Neural holdout top-1: `0.8434`
- State graph nodes: `4,405`

Judge scores:

| Variant | Count | Mean weighted score | Pass rate | Critical failure rate |
| --- | ---: | ---: | ---: | ---: |
| full | 4 | 79.5 | 0.75 | 0.0 |
| no_memory | 4 | 74.5 | 0.5 | 0.0 |
| no_public_tools | 4 | 56.75 | 0.0 | 0.0 |
| no_sciflow | 4 | 76.75 | 0.5 | 0.0 |

Domain scores:

| Domain | Count | Mean weighted score | Pass rate |
| --- | ---: | ---: | ---: |
| autoimmune_inflammation | 8 | 69.0 | 0.125 |
| oncology | 8 | 74.75 | 0.75 |

Policy and memory:

- Neural workflow policy examples: `42,552`
- Neural holdout top-1: `0.8434`
- Neural holdout top-3: `0.9998`
- State graph nodes: `4,405`
- State graph edges: `31,459`
- Hypotheses: `599`
- Entities: `1,000`
- Experiments: `1,000`
- Tools: `9`

## What This Proves

1. The full runtime can execute end-to-end on real biomedical cases.
2. Public biomedical grounding is the strongest proven value driver.
3. The system can produce replayable, memory-backed, traceable artifacts.
4. ToolUniverse/public biomedical tools materially improve benchmark quality compared with no-public-tools.
5. Memory and SciFlow are functional and measurable, but their current incremental judge-score gains are modest.
6. The workflow policy model can be trained from accumulated traces and packaged as an artifact.

## What This Does Not Prove

1. It does not prove autonomous scientific discovery.
2. It does not prove clinical utility.
3. It does not prove expert-level biological correctness.
4. It does not prove generalization beyond the four canary cases.
5. It does not prove memory or SciFlow are currently transformative.
6. It does not prove the internal score is calibrated; internal `100` and judge `79.5` show score inflation.

## Key Diagnosis

The system has become a serious biomedical agent workbench, but the next bottleneck is scientific judgment.

The highest-value next improvements are:

1. BioTruth critic layer.
2. Evidence hierarchy.
3. Contradiction detection.
4. Abstention policy.
5. Adaptive tool planning.
6. Deeper biomedical tools.
7. Leaderboard-style benchmark with strong, weak, conflicting, and abstention-required cases.

## Reproducibility

Local baseline verification:

```bash
python -m pytest tools/tests/test_biotruth_benchmark.py tools/tests/test_biotruth_pipeline.py tools/tests/test_score_biomedical_correctness.py
```

RunPod canary command:

```bash
bash infra/runpod/run_biotruth_4_case_canary.sh
```

Primary local artifacts:

```text
pod_artifacts/biotruth_4_case_canary/
  autoscientist_biotruth_4_case_canary_20260524_145750_complete.zip
  benchmark_summary.json
  benchmark_summary.md
  biotruth_pipeline_1779634688.json
  biotruth_scores.json
  biotruth_scores.md
```

Repo summary artifacts:

```text
docs/results/biotruth_4_case_canary_20260524/
  benchmark_summary.json
  benchmark_summary.md
  biotruth_scores.json
  biotruth_scores.md
```

## Baseline Claim Boundary

The defensible baseline claim is:

> AutoScientist is an auditable biomedical discovery runtime that can run real target-disease evidence workflows with live biomedical tools, ToolUniverse support, persistent memory, replayable provenance, and a trained workflow-policy layer.

The non-defensible claim is:

> AutoScientist is already a validated autonomous AI scientist.

The upgrade work should close that gap by making correctness, contradiction handling, abstention, and evidence quality first-class parts of the runtime.

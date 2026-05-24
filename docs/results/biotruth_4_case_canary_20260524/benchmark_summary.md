# AutoScientist-Bench v0.1 Run

Status: `completed`
Tasks: `4`
Results: `16`
Elapsed seconds: `4728.67`

## Ablation Summary

| Ablation | Runs | Completed | Mean score | Strict quality | Replay runs | Controller advice | Controller applied | Strategy repairs | Mean evidence | Mean tool calls | Public-tool runs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| full | 4 | 4 | 100 | 100 | 4 | 4 | 4 | 0 | 23.5 | 34 | 4 |
| no_memory | 4 | 4 | 100 | 95 | 0 | 0 | 0 | 0 | 20.5 | 30 | 4 |
| no_public_tools | 4 | 4 | 65 | 54 | 4 | 4 | 0 | 0 | 2 | 0 | 0 |
| no_sciflow | 4 | 4 | 100 | 95 | 4 | 0 | 0 | 0 | 20.25 | 30 | 4 |

## Full vs Ablation Deltas

```json
{
  "no_memory": {
    "mean_score_delta_vs_full": 0,
    "mean_scientific_quality_delta_vs_full": 5,
    "controller_runs_delta_vs_full": 4,
    "controller_applied_runs_delta_vs_full": 4,
    "strategy_repair_runs_delta_vs_full": 0,
    "replay_runs_delta_vs_full": 4,
    "public_tool_runs_delta_vs_full": 0,
    "mean_tool_calls_delta_vs_full": 4,
    "mean_evidence_count_delta_vs_full": 3.0,
    "mean_public_biomedical_calls_delta_vs_full": 2.0,
    "mean_tooluniverse_calls_delta_vs_full": 1.0
  },
  "no_public_tools": {
    "mean_score_delta_vs_full": 35,
    "mean_scientific_quality_delta_vs_full": 46,
    "controller_runs_delta_vs_full": 0,
    "controller_applied_runs_delta_vs_full": 4,
    "strategy_repair_runs_delta_vs_full": 0,
    "replay_runs_delta_vs_full": 0,
    "public_tool_runs_delta_vs_full": 4,
    "mean_tool_calls_delta_vs_full": 34,
    "mean_evidence_count_delta_vs_full": 21.5,
    "mean_public_biomedical_calls_delta_vs_full": 11.25,
    "mean_tooluniverse_calls_delta_vs_full": 10.25
  },
  "no_sciflow": {
    "mean_score_delta_vs_full": 0,
    "mean_scientific_quality_delta_vs_full": 5,
    "controller_runs_delta_vs_full": 4,
    "controller_applied_runs_delta_vs_full": 4,
    "strategy_repair_runs_delta_vs_full": 0,
    "replay_runs_delta_vs_full": 0,
    "public_tool_runs_delta_vs_full": 0,
    "mean_tool_calls_delta_vs_full": 4,
    "mean_evidence_count_delta_vs_full": 3.25,
    "mean_public_biomedical_calls_delta_vs_full": 2.0,
    "mean_tooluniverse_calls_delta_vs_full": 1.0
  }
}
```

## Realness Gates

- Passed: `True`
- Strict real run: `True`
- Required full integrations: `local_board, memory_replay, public_biomedical, sciflow_policy, tooluniverse`
- Full completion: `1.0` / required `1.0`
- Full mean score: `100.0` / required `85.0`
- Neural holdout top-1: `0.8434` / required `0.5`

## Policy Package

- Transparent policy: `outputs/autoscientist_bench/20260524_145808/models/scientific_workflow_policy_20260524160600.json`
- Examples: `42552`
- Neural policy: `outputs/autoscientist_bench/20260524_145808/models/neural_scientific_workflow_policy_20260524161627/manifest.json`
- Package: `outputs/autoscientist_bench/20260524_145808/packages/neural_scientific_workflow_policy_20260524161627.zip`

## State Graph

- Export: `outputs/autoscientist_bench/20260524_145808/scistate_graph.json`
- Summary: `{"nodes": 4405, "edges": 31459, "hypotheses": 599, "entities": 1000, "experiments": 1000, "tools": 9}`

## Top Full Results

| Task | Run | Score | Confidence | Artifact |
| --- | --- | ---: | ---: | --- |
| il6_rheumatoid_arthritis__target_validity_review__r1 | `run_311418762daa` | 100 | 0.75 | `outputs/autoscientist_bench/20260524_145808/il6_rheumatoid_arthritis__target_validity_review__r1__full.json` |
| tnf_inflammatory_bowel_disease__target_validity_review__r1 | `run_26981d0f25c8` | 100 | 0.72 | `outputs/autoscientist_bench/20260524_145808/tnf_inflammatory_bowel_disease__target_validity_review__r1__full.json` |
| braf_melanoma__target_validity_review__r1 | `run_3ca09bb511fe` | 100 | 0.82 | `outputs/autoscientist_bench/20260524_145808/braf_melanoma__target_validity_review__r1__full.json` |
| egfr_lung_adenocarcinoma__target_validity_review__r1 | `run_93dd3b2c0b87` | 100 | 0.78 | `outputs/autoscientist_bench/20260524_145808/egfr_lung_adenocarcinoma__target_validity_review__r1__full.json` |

## GPU Scale-Up Command

```bash
python tools/run_biotruth_pipeline.py --mode full --limit 100 --ablations full no_memory no_public_tools no_sciflow --llm-provider auto --train-neural-policy --neural-epochs 120 --strict-real-run --require-expected-integrations --min-full-completion-rate 1.0 --min-full-mean-score 85 --min-neural-holdout-top1 0.5 --min-state-graph-nodes 1 --score-mode judge
```
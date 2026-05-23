# RunPod 100-Task Deep Discovery Runbook

This runbook is for the next paid RunPod session.

The goal is a 100-task full-system discovery campaign, not another broad ablation run.

## Why 100 Tasks

The campaign uses 25 carefully selected target-disease cases and 4 workflows per case:

- target validity review;
- mechanism and safety review;
- experiment decision plan;
- evidence grade and replay.

This produces enough breadth to judge end-to-end scientific usefulness while staying within a practical RunPod budget.

## Expected Cost Shape

The previous 100-task full run took about 3 hours on an H100-class pod, plus extra time for scoring and packaging.

Budget expectation:

- likely: 3-5 hours;
- cautious upper bound: 6-8 hours if Gemini/tool latency is high;
- do not run 4-way ablations unless explicitly needed, because that multiplies runtime.

## Before Starting

Confirm the repo branch contains:

- `infra/runpod/run_deep_discovery_campaign.sh`;
- `tools/build_discovery_case_study.py`;
- `tools/build_discovery_insight_report.py`;
- `docs/BIOTRUTH_100_CASE_SELECTION.md`;
- `docs/END_TO_END_DISCOVERY_CASE_STUDIES.md`.

Confirm the pod has:

- GPU available via `nvidia-smi`;
- repo at `/workspace/AutoScientist`;
- `.env` with `GEMINI_API_KEY`;
- network volume mounted at `/workspace`.

## Command

From the pod:

```bash
cd /workspace/AutoScientist
git pull --ff-only
bash infra/runpod/run_deep_discovery_campaign.sh
```

Optional explicit environment:

```bash
LIMIT=100 \
MAX_CASES=25 \
TEMPLATES_PER_CASE=4 \
LLM_PROVIDER=gemini \
LLM_MODEL=gemini-2.5-flash \
LLM_API_KEY_ENV_VAR=GEMINI_API_KEY \
JUDGE_LLM_PROVIDER=gemini \
JUDGE_LLM_MODEL=gemini-2.5-flash \
JUDGE_LLM_API_KEY_ENV_VAR=GEMINI_API_KEY \
bash infra/runpod/run_deep_discovery_campaign.sh
```

## What It Produces

The script produces:

- benchmark output directory under `outputs/autoscientist_bench/`;
- `benchmark_summary.json` and `benchmark_summary.md`;
- `biotruth_scores.json`, `biotruth_scores.md`, and scoring packets;
- trained SciFlow neural policy package;
- `scistate_graph.json`;
- 25 discovery case studies;
- cross-case discovery insight report;
- final ZIP under `outputs/review_packages/`.

## What To Inspect First

Start with:

1. `discovery_insight_report.md`;
2. the strongest 3-5 case-study Markdown files;
3. weakest/highest-risk case-study files;
4. `biotruth_scores.md`;
5. `benchmark_summary.md`;
6. model card for the neural workflow policy.

## Success Criteria

A useful run should show:

- 100/100 full-system tasks completed;
- public biomedical and ToolUniverse calls executed in full runs;
- replay/state graph artifacts produced;
- 25 case-study dossiers generated;
- mean judge score around or above the previous 85.64 baseline;
- critical failure rate lower than or comparable to the previous 0.08;
- clear scientific insight report with strongest cases, weak branches, and experiment themes.

## Stop Conditions

Stop early if:

- preflight fails;
- Gemini key is missing or returning quota/rate errors for most calls;
- public tools cannot execute;
- no benchmark result files appear after 20-30 minutes;
- the run is accidentally executing 4 ablations for all 100 tasks.

## After Completion

Copy the final package locally:

```powershell
scp -P <PORT> -i "$env:USERPROFILE\.ssh\runpod_shared_autoscientist" `
  root@<HOST>:/workspace/AutoScientist/outputs/review_packages/<PACKAGE>.zip `
  .\pod_artifacts\
```

Then stop the pod.


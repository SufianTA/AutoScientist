# BioTruth 20-Case Gate Salvage Report

Date: 2026-05-24 UTC

## Verdict

The 20-case gate is not publishable as a completed benchmark.

The run generated 80 result files across 20 disease-target cases and four ablations, but only 26 completed successfully; 54 failed after the live LLM provider stopped accepting requests.

## What Worked

- RunPod H100 execution started correctly.
- Repo revision `00e9ae9` was deployed on the pod.
- GPU, ToolUniverse import, public network checks, and Anthropic live preflight initially passed.
- The first completed cases produced real artifacts with live public biomedical evidence, ToolUniverse/OpenTargets traces, memory/replay metadata, SciFlow policy metadata, hypotheses, evidence, guardrails, and proposed experiments.
- A salvage package was created on the pod at:
  - `/workspace/AutoScientist/outputs/review_packages/biotruth_20_case_gate_salvage_20260524.zip`
  - `/workspace/AutoScientist/outputs/review_packages/biotruth_20_case_gate_salvage_20260524/salvage_summary.md`

## What Failed

- Anthropic began returning: credit balance too low.
- Gemini preflight then failed with: monthly spending cap exceeded.
- Once Anthropic failed, later benchmark artifacts became failed placeholders rather than scientific outputs.
- Final judge scoring could not be trusted because the provider was not available for the full run.

## Counts

- Total result artifacts: 80
- Completed result artifacts: 26
- Failed result artifacts: 54
- Fully completed cases before provider failure: 6
- Seventh case partially completed before provider failure

## Honest Interpretation

This run proves that the infrastructure can launch, execute real tools, produce auditable scientific artifacts, and detect failures instead of silently passing them.

It does not prove that AutoScientist performs well across the 20-case benchmark, because the majority of cases failed due to external LLM billing/quota limits.

## Next Paid Run Gate

Do not start another pod run until this exact command passes for the selected provider:

```bash
python tools/machine_preflight.py \
  --workspace /workspace/AutoScientist \
  --output-dir outputs/preflight \
  --min-free-gb 10 \
  --require-gpu \
  --require-tooluniverse \
  --execute-tooluniverse \
  --llm-provider <provider> \
  --llm-model <model> \
  --llm-api-key-env-var <KEY_ENV_VAR> \
  --test-llm
```

For the next run, also use a smaller live canary first:

```bash
LIMIT=4 MAX_SCORE_RESULTS=16 bash infra/runpod/run_biotruth_20_case_gate.sh
```

Only run the full 20-case gate if the canary completes with 16/16 completed artifacts and judge scoring passes.

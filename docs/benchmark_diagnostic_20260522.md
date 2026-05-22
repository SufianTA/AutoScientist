# AutoScientist Benchmark Diagnostic - 2026-05-22

This note records the honest interpretation of the RunPod benchmark artifacts after re-checking them with stricter quality criteria.

## What The Run Proved

- The runtime completed 96 benchmark executions: 24 public biomedical tasks across `full`, `no_memory`, `no_public_tools`, and `no_sciflow` ablations.
- The full runtime exercised public biomedical tools, ToolUniverse/OpenTargets paths, SciState memory capture, replay artifacts, and SciFlow controller traces.
- The neural SciFlow policy trained on 10,727 workflow examples and separated itself from a majority-class baseline on trace prediction.
- The architecture produced a real provenance and audit trail, not just chat transcripts.

## What The Run Did Not Prove

- It did not prove superior biomedical discovery quality.
- The original benchmark score was too generous because it saturated at 100 and allowed bonuses to hide failed checks.
- `no_sciflow` tied `full` on the old top-line score, so that score could not support a strong controller-value claim.
- `no_public_tools` still scored highly under the old metric, which means the old score rewarded orchestration structure more than live scientific evidence.

## Defects Found

- Generated API reports dropped `next_experiments`, so the benchmark marked `experiments_proposed` as failed even when the board post contained experiments.
- JSON-like context strings could pass into PubMed as search queries, producing malformed PubMed calls such as serialized `primary_genes` / `diseases` payloads instead of biomedical search text.
- Saved benchmark artifacts expose top-level `tool_calls` and controller fields, while some scoring helpers only inspected nested provenance fields.

## Fixes Applied

- `agents/app/langgraph_workflow.py` now rejects serialized context strings as PubMed queries and regenerates clean biomedical fallback queries.
- `apps/api/app/routes/reports.py` now exports `next_experiments` and `experiments` from the hypothesis board post.
- `tools/run_integration_benchmark.py` now recovers experiments from board posts, checks stored PubMed tool inputs, and supports top-level benchmark artifact traces.
- `tools/run_autoscientist_bench.py` now emits a separate `scientific_quality` score so execution success is not confused with scientific value.

## Re-Scored Interpretation

Using the stricter scientific-quality score on the existing 96 artifacts:

| Ablation | Mean Strict Quality | Interpretation |
| --- | ---: | --- |
| `full` | 74/100 | Promising infrastructure value, not yet a strong scientific-performance claim. |
| `no_memory` | 67.83/100 | Memory and controller features add measurable value, but the gap is not yet decisive. |
| `no_public_tools` | 54/100 | Public biomedical tools are necessary for credible scientific output. |
| `no_sciflow` | 67.83/100 | SciFlow improves execution depth, but current evidence does not yet prove better final answers. |

## Decision Rule Before More GPU Spend

Do not run another large paid benchmark until a small fixed run passes these gates:

- No malformed PubMed queries.
- `experiments_proposed` passes from exported reports.
- `full` beats `no_sciflow` and `no_memory` on strict scientific quality, not only tool-call volume.
- `no_public_tools` stays clearly below `full`.
- A human-readable artifact shows citations, tool traces, proposed experiments, limitations, and replay metadata for each task.

## Honest Current Rating

Current system value: useful and real as a persistent scientific execution/provenance runtime.

Current scientific-performance claim: not strong enough yet; it needs the fixed benchmark rerun and harder expert-style scoring before being presented as evidence that the model improves discovery quality.

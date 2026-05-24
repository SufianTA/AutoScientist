# Deep Discovery Run Findings - 2026-05-23

## What Ran

AutoScientist ran a 100-task BioTruth deep discovery campaign on a RunPod H100 pod across 25 target-disease cases and 4 workflow templates per case.

The campaign generated 100 result artifacts, case-study reports, a discovery insight report, a SciState graph export, and a packaged SciFlow policy model.

## Main Result

The run demonstrates that AutoScientist can execute a broad, auditable biomedical triage campaign over real public biomedical sources, but it should not be presented as a fully validated autonomous-discovery success yet.

The benchmark status was `failed_gates`, not because the 100 tasks failed to produce artifacts, but because the strict realness gate required ToolUniverse to be healthy and recorded as executed in every full result.

## Quantitative Summary

- Tasks: 100
- Results: 100
- Runtime: 11,872.53 seconds
- Domains covered: autoimmune/inflammation, oncology, rare Mendelian disease, neurodegeneration, cardiometabolic disease, hematology, ophthalmology
- SciState graph: 4,277 nodes and 29,521 edges
- Stored hypotheses: 567
- Stored entities: 1,000
- Stored proposed experiments: 1,000
- Policy training examples: 39,602
- Neural policy holdout top-1: 0.8382

## What The System Did Well

- It completed a broad 25-case biomedical campaign rather than a single toy example.
- It preserved traceable outputs: benchmark JSON, case studies, state graph, policy model package, and review zips.
- It gathered real public biomedical evidence through live public biomedical paths.
- It produced reusable scientific state: hypotheses, entities, experiments, evidence, tool traces, and case-level summaries.
- It trained a workflow policy model from execution traces rather than claiming to replace frontier models.

## What Failed

The strict integration gate failed because ToolUniverse was not successfully available during the 100-task run.

The root cause on the pod was a missing Linux runtime library required by RDKit through ToolUniverse/ADMET dependencies:

```text
ImportError: libXrender.so.1: cannot open shared object file: No such file or directory
```

After installing `libxrender1`, `libxext6`, and `libsm6`, ToolUniverse became importable and passed machine preflight.

## Post-Repair Validation

After the dependency repair:

- ToolUniverse health check passed.
- ToolUniverse listed 638 tools.
- A direct ToolUniverse OpenTargets call succeeded for rheumatoid arthritis (`EFO_0000685`) and returned associated targets.
- A deterministic mock-provider integration benchmark completed after the repair with 5/5 ToolUniverse calls successful, 7/7 public biomedical calls successful, and local board logging enabled.

However, a 20-task strict validation run did not validate the full autonomous loop because Gemini returned:

```text
429 RESOURCE_EXHAUSTED: project has exceeded its monthly spending cap
```

That means the repaired live validation failed before LLM-driven workflow execution could reach public tools, memory, ToolUniverse, or board logging.

The mock-provider validation is not evidence of scientific reasoning quality, but it is useful engineering evidence that the repaired runtime can execute the ToolUniverse/public-tool/local-board layer when not blocked by LLM quota.

## Interpretation

The 100-task run is valuable as an infrastructure and traceability artifact, not as final proof of autonomous scientific discovery quality.

The strongest defensible claim is:

AutoScientist now has a working campaign harness that can generate broad biomedical trace artifacts, train a workflow policy model from those traces, and export a persistent scientific state graph, but the next credible milestone is a clean strict run after fixing pod bootstrap dependencies and restoring LLM quota.

## What To Say Externally

Do not say the system has proven autonomous discovery.

Say:

AutoScientist has moved from a prototype agent toward a persistent scientific runtime with benchmarkable workflows, replayable traces, a scientific state graph, and a learned workflow policy layer. A 100-task run produced complete artifacts across 25 biomedical target-disease cases, while also surfacing two important engineering gaps: missing ToolUniverse system dependencies and provider quota fragility. Both are now actionable and measurable.

## Next Run Criteria

The next run should be considered shareable only if all of these pass:

- Machine preflight passes with `--require-tooluniverse`.
- LLM provider quota is confirmed before launch.
- Strict run completes with full completion rate >= 1.0.
- Mean score >= 85.
- ToolUniverse, public biomedical tools, memory replay, local board, and SciFlow policy are recorded in results.
- Judge scoring completes or is intentionally disabled with `SCORE_MODE=heuristic` and clearly labeled.
- At least one independent expert-review rubric is applied to a sampled subset before making biological correctness claims.

## RunPod Bootstrap Fix

The RunPod campaign script now installs the system libraries needed by ToolUniverse/RDKit before preflight:

```bash
apt-get install -y --no-install-recommends libxrender1 libxext6 libsm6 libglib2.0-0 libgl1
```

The campaign preflight now requires ToolUniverse before launching the expensive benchmark.

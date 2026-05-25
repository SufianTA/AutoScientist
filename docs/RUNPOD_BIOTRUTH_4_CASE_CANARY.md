# RunPod BioTruth 4-Case Canary

Use this before any larger paid run.

## Purpose

This canary runs 4 disease-target cases across 4 ablations, producing 16 result artifacts with live public biomedical tools, ToolUniverse/OpenTargets, SciFlow policy, memory/replay, neural policy packaging, and BioTruth judge scoring.

It is designed to answer one question: is the system, provider credit, and benchmark path healthy enough to justify a larger run?

## Selected Cases

- `il6_rheumatoid_arthritis`
- `tnf_inflammatory_bowel_disease`
- `braf_melanoma`
- `egfr_lung_adenocarcinoma`

These were selected because they completed cleanly in the interrupted 20-case gate and cover immunology, inflammatory disease, oncology, and precision oncology.

## Required Pass Criteria

- hard machine preflight passes;
- Anthropic live LLM preflight passes before generation;
- public biomedical execution preflight passes for NCBI Gene, PubMed, ClinicalTrials.gov, Reactome, and openFDA;
- ToolUniverse execution preflight passes;
- 16/16 result artifacts complete;
- `plain_llm` baseline is present so the full system can be compared against a weak no-tools/no-memory/no-controller baseline;
- full ablation completion rate is 1.0;
- full mean score is at least 85;
- full-system critical failure rate is at most 0.05;
- final review package is generated.

## Pod Command

```bash
cd /workspace/AutoScientist
git pull origin main
source /opt/autosci-venv/bin/activate
set -a && source .env && set +a
bash infra/runpod/run_biotruth_4_case_canary.sh
```

## Expected Artifacts

- `outputs/autoscientist_bench/<timestamp>/benchmark_summary.md`
- `outputs/autoscientist_bench/<timestamp>/biotruth_scores.md`
- `outputs/discovery_case_studies/biotruth_20_case_gate_<timestamp>/discovery_insight_report.md`
- `outputs/review_packages/autoscientist_biotruth_4_case_canary_<timestamp>_complete.zip`

## Stop Rule

If preflight fails for Anthropic credit, Gemini cap, ToolUniverse execution, or GPU availability, stop the pod immediately and do not run the benchmark.

If the canary passes, the next reasonable step is the 20-case gate, not a 100-case run.

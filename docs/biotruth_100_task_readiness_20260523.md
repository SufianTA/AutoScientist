# BioTruth 100-Task Readiness

Date: 2026-05-23

## What Changed Before the 100-Task Run

- Added a reusable clinical-status classifier in `tools/custom_tools/clinical_status.py`.
- Expanded target and disease alias matching beyond TNF/IBD to cover common benchmark cases in autoimmune disease, oncology, rare disease, neurodegeneration, and cardiometabolic disease.
- Hardened PubMed evidence scoring so titles must match both the target and disease context before they can support a claim.
- Split relevant literature into clinical-precedence, safety, mechanism, genetic, and general literature categories.
- Updated hypothesis synthesis to classify each target-disease pair as:
  - `established_or_clinically_precedented`
  - `genetically_or_publicly_grounded`
  - `early_or_indirect`
  - `speculative_or_insufficient`
- Rebuilt the BioTruth manifest so the full run is actually 25 cases x 4 templates = 100 tasks.

## Local Validation

Full local tests:

```text
68 passed, 2 warnings
```

Manifest validation:

```text
25 seed cases
4 task templates
100 expanded tasks
7 domains:
autoimmune_inflammation, cardiometabolic, hematology, neurodegeneration, oncology, ophthalmology, rare_mendelian
```

Local diverse smoke run:

```text
Run: outputs/autoscientist_bench/20260523_142039
Mode: smoke
Tasks: 12
Cases: IL6/rheumatoid arthritis, BRAF/melanoma, CFTR/cystic fibrosis
Ablation: full
LLM provider: mock
Strict real run: false
Status: completed
Acceptance: passed
```

Smoke heuristic BioTruth results:

```text
Mean weighted score: 88.0
Pass rate: 1.0
Critical failure rate: 0.0
Evidence certainty: high for 8 tasks, moderate for 4 tasks
```

## What This Does and Does Not Prove

This local work proves the code path is ready for a pod-scale run: the manifest has 100 tasks, the hardened synthesis logic passes tests, and a diverse local smoke run completes.

It does not prove broad biological correctness because the local smoke used mock LLM mode and heuristic scoring. The real claim requires the pod run with live frontier-model reasoning and judge scoring.

## Recommended Pod Run

Use the pod only for this next step:

```bash
python tools/run_biotruth_pipeline.py \
  --mode full \
  --skip-build \
  --limit 100 \
  --ablations full no_memory no_public_tools no_sciflow \
  --llm-provider gemini \
  --llm-model gemini-3-flash-preview \
  --llm-api-key-env-var GEMINI_API_KEY \
  --strict-real-run \
  --require-expected-integrations \
  --train-neural-policy \
  --neural-epochs 120 \
  --score-mode judge \
  --judge-llm-provider gemini \
  --judge-llm-model gemini-3-flash-preview \
  --judge-llm-api-key-env-var GEMINI_API_KEY \
  --judge-llm-max-tokens 8192 \
  --disable-qworld \
  --review-package-name autoscientist_biotruth_100_task_full
```

Expected outputs to inspect after the pod run:

- `benchmark_summary.md`
- `biotruth_scores.md`
- `biotruth_scores.json`
- full/no-memory/no-public-tools/no-SciFlow ablation deltas
- neural workflow policy package
- state graph export
- review package zip with no secret-like matches

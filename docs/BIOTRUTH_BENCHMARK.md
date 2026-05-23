# BioTruth Benchmark

BioTruth is the correctness layer that was missing from the earlier AutoScientist benchmark. The previous benchmark proved execution, memory, provenance, ablations, and public-tool coverage; BioTruth asks the harder question: did the system produce biologically credible, grounded, useful target-disease reasoning?

## What Was Added

- `benchmarks/biotruth_seed_cases_v0_1.json`: 25 curated target-disease seed cases across autoimmune/inflammation, oncology, rare disease, neurodegeneration, cardiometabolic disease, hematology, and ophthalmology.
- `benchmarks/biotruth_rubric_v0_1.json`: weighted biomedical correctness rubric with critical failure flags, evidence-certainty levels, and pass criteria.
- `benchmarks/autoscientist_biotruth_v0_1.json`: generated live public-data manifest with 25/25 Open Targets matches.
- `benchmarks/autoscientist_biotruth_v0_1_tasks.jsonl`: 100 expanded tasks, four task types per target-disease case.
- `tools/build_biotruth_benchmark.py`: rebuilds the benchmark from public sources.
- `tools/score_biomedical_correctness.py`: exports expert-review packets, deterministic triage scores, or model-judged rubric scores.

## Public Sources Used

- Open Targets Platform: target-disease evidence is mapped to Ensembl and EFO identifiers, grouped by evidence data types, and scored by source-specific frameworks. This is used for public target-disease grounding and association labels: https://platform-docs.opentargets.org/evidence
- Open Targets target-disease associations: used only as ranking/evidence context, not as clinical truth: https://platform-docs.opentargets.org/associations
- Therapeutics Data Commons: its leaderboard protocol motivates fixed train/validation/test style evaluation and repeated seeds; TDC recommends multiple independent runs for robust reporting: https://tdcommons.ai/benchmark/overview/
- BioASQ: its biomedical QA framework motivates exact/ideal answer scoring and expert/manual answer review: https://www.bioasq.org/sites/default/files/PublicDocuments/BioASQ_D4.1-EvaluationFrameworkSpecification_final.pdf
- PubMedQA: provides a precedent for expert-labeled biomedical QA with yes/no/maybe answers grounded in abstracts: https://pubmedqa.github.io/
- Cochrane RoB 2 and GRADE: motivate explicit risk-of-bias, uncertainty, and certainty-of-evidence language: https://www.cochrane.org/learn/courses-and-resources/cochrane-methodology/risk-bias/about-risk-bias-2-rob-2 and https://www.cochrane.org/learn/courses-and-resources/cochrane-methodology/grade-approach/grade-handbook

## Model Direction

The core custom model remains SciFlow Policy: a workflow-controller model trained on AutoScientist traces to recommend the next scientific action, tool, or strategy branch. BioTruth is not a replacement for SciFlow Policy; it is the evaluation layer that tells whether SciFlow-guided runs actually improve biological correctness.

For a local open-source reasoning model on the H100, use Qwen3-32B first because its official model card lists 32.8B parameters, agent/tool-use capability, native 32k context, vLLM/SGLang serving support, and Apache-2.0 licensing: https://huggingface.co/Qwen/Qwen3-32B

For biomedical baseline comparisons, BioMistral-7B is a credible lightweight option because it is further pretrained from Mistral on PubMed Central and evaluated on medical QA tasks: https://arxiv.org/abs/2402.10373

The strongest setup is not "replace the foundation model"; it is:

1. Qwen3-32B or a frontier API generates and critiques scientific reasoning.
2. SciFlow Policy controls workflow strategy and next action selection.
3. SciState Graph preserves memory, provenance, failed branches, and evidence lineage.
4. BioTruth scores whether the resulting outputs are biologically credible across 100 public cases.

## Current Generated Dataset

The live-generated manifest currently contains:

- 25 target-disease cases.
- 100 expanded tasks.
- 7 biomedical domains.
- 25/25 Open Targets association matches.
- Public PubMed/Gene count labels for each target-disease pair.

Generated summary:

```powershell
python tools/build_biotruth_benchmark.py --max-cases 25 --templates-per-case 4 --association-scan-size 150 --public-timeout-seconds 20
```

## How To Run On The Pod

Preferred one-command path:

```bash
python tools/run_biotruth_pipeline.py \
  --mode smoke \
  --limit 8 \
  --ablations full no_memory no_public_tools no_sciflow \
  --llm-provider auto \
  --strict-real-run \
  --score-mode heuristic
```

Full review run:

```bash
python tools/run_biotruth_pipeline.py \
  --mode full \
  --limit 100 \
  --ablations full no_memory no_public_tools no_sciflow \
  --llm-provider auto \
  --strict-real-run \
  --train-neural-policy \
  --neural-epochs 120 \
  --score-mode judge
```

Run a small validation first:

```bash
python tools/run_autoscientist_bench.py \
  --manifest benchmarks/autoscientist_biotruth_v0_1.json \
  --limit 8 \
  --ablations full no_memory no_public_tools no_sciflow \
  --llm-provider auto \
  --require-real-llm \
  --enable-sciflow-policy \
  --train-neural-policy \
  --strict-real-run
```

Run the full 100-task benchmark after the smoke run passes:

```bash
python tools/run_autoscientist_bench.py \
  --manifest benchmarks/autoscientist_biotruth_v0_1.json \
  --limit 100 \
  --ablations full no_memory no_public_tools no_sciflow \
  --llm-provider auto \
  --require-real-llm \
  --enable-sciflow-policy \
  --train-neural-policy \
  --strict-real-run
```

Export review packets for human or external review:

```bash
python tools/score_biomedical_correctness.py \
  --bench-dir outputs/autoscientist_bench/<RUN_ID> \
  --mode export \
  --ablations full no_memory no_public_tools no_sciflow
```

Run deterministic triage scoring:

```bash
python tools/score_biomedical_correctness.py \
  --bench-dir outputs/autoscientist_bench/<RUN_ID> \
  --mode heuristic \
  --ablations full no_memory no_public_tools no_sciflow
```

Run rubric-judge scoring with a real model:

```bash
python tools/score_biomedical_correctness.py \
  --bench-dir outputs/autoscientist_bench/<RUN_ID> \
  --mode judge \
  --ablations full no_memory no_public_tools no_sciflow \
  --llm-provider gemini \
  --llm-model gemini-2.5-flash
```

For a local open-source judge/server, start Qwen3-32B through vLLM and use the existing OpenAI-compatible path:

```bash
vllm serve Qwen/Qwen3-32B --host 0.0.0.0 --port 8000
python tools/score_biomedical_correctness.py \
  --bench-dir outputs/autoscientist_bench/<RUN_ID> \
  --mode judge \
  --ablations full \
  --llm-provider openai_compatible \
  --llm-model Qwen/Qwen3-32B \
  --llm-base-url http://127.0.0.1:8000/v1
```

## What Counts As A Respectable Result

A publishable internal result should show:

- Full system beats `no_public_tools` on BioTruth score by a large margin.
- Full system beats or matches `no_memory` while producing more replayable provenance.
- Full system beats or matches `no_sciflow` on correctness or efficiency, not just tool-call volume.
- Critical failure rate stays near zero.
- Scores are stable across disease domains, not only autoimmune tasks.
- At least a sampled subset receives human or expert-model review.

## What This Does Not Prove Yet

BioTruth does not prove novel discovery. It makes the next GPU run honest by separating three claims:

- Execution claim: the system can run, collect public evidence, and preserve traces.
- Biological correctness claim: outputs are grounded, calibrated, and useful under a rubric.
- Discovery claim: the system identifies genuinely new, experimentally valuable hypotheses.

Only the first two are in scope now. The discovery claim requires expert review or later experimental validation.

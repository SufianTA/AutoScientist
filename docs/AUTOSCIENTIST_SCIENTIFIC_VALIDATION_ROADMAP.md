# AutoScientist Scientific Validation Roadmap

This document is the implementation plan for moving AutoScientist from a strong biomedical agent workbench toward a more credible auditable biomedical discovery runtime.

The goal is not to claim that the system replaces biomedical researchers. The goal is to make a defensible claim that AutoScientist can run reproducible biomedical evidence workflows, identify target-disease evidence gaps, produce audit-ready hypotheses, and improve its tool-use policy from execution traces.

## Operating Rules

1. Do not run expensive GPU or live-LLM benchmarks until local preflight, smoke tests, and artifact expectations are green.
2. Every phase must produce at least one durable artifact: code, tests, benchmark output, or documentation.
3. Every scientific claim must be tied to a benchmark result, a trace, a score packet, or a reviewer-readable report.
4. Mock tests are allowed only for local correctness. Strict-real claims require real LLM calls, public biomedical tools, ToolUniverse where available, memory, replay, and trace capture.
5. Internal runtime scores are not enough. Biological correctness must be evaluated with BioTruth judge scoring and, later, expert spot checks.
6. The system should be allowed to abstain. A correct "insufficient evidence" result is better than a polished overclaim.
7. Improvements must be measured against ablations: `full`, `no_public_tools`, `no_memory`, `no_sciflow`, and eventually `no_critic`.
8. Keep the repo free of private names, private correspondence, and unreleased claims. Public docs should describe the system, artifacts, and limitations.

## Current Baseline

Baseline tag: `autosci-baseline-biotru-4case-20260524`

Baseline commit: `cbc9d71`

Baseline artifact directory:

`docs/results/biotruth_4_case_canary_20260524/`

Local complete artifact package:

`pod_artifacts/biotruth_4_case_canary/autoscientist_biotruth_4_case_canary_20260524_145750_complete.zip`

Baseline headline result:

- 4 BioTruth disease cases.
- 4 ablations per case.
- 16/16 run artifacts completed.
- Strict real-run gates passed.
- Full system judge score: `79.5`.
- No-memory judge score: `74.5`.
- No-public-tools judge score: `56.75`.
- No-SciFlow judge score: `76.75`.
- Neural workflow policy holdout top-1: `0.8434`.
- State graph: `4,405` nodes and `31,459` edges.

Interpretation:

- Public biomedical grounding is the strongest proven value driver.
- Memory and SciFlow are useful, but their gains are still modest on the small canary.
- Internal runtime score is too generous compared with judge score and must be recalibrated.
- The system is credible as an auditable biomedical discovery workbench, not yet as a fully validated autonomous scientist.

## Implementation Status as of 2026-05-24

Completed locally:

- Phase 0: baseline tag, baseline report, and copied 4-case canary artifacts.
- Phase 1: BioTruth critic integrated into runtime, benchmark artifacts, score packets, and tests.
- Phase 2: evidence hierarchy classifier and summary integrated into planning, scoring, and reports.
- Phase 3: contradiction detection integrated into critique, abstention, benchmark outputs, and score packets.
- Phase 4: abstention policy integrated as a first-class scientific decision layer.
- Phase 5: adaptive tool planner integrated with evidence-gap-driven follow-up recommendations.
- Phase 6: ClinicalTrials.gov public API tool added, registered, live-smoked, and evidence-tiered.
- Phase 7: BioTruth v0.2 stratified benchmark, rubric, manifest, task JSONL, and label/decision score breakdowns.
- Phase 8: SciFlow training examples now include scientific outcome labels such as critic verdict, abstention decision, evidence hierarchy, contradictions, and adaptive gaps.
- Phase 9: review package now includes an artifact guide and claims/limitations document.

Verified locally:

```bash
python -m compileall apps/api/app/services agents/app tools
python -m pytest
```

Latest local result:

- `98 passed`
- `2 warnings` from existing FastAPI startup-event deprecation notices.

Local preflight artifacts:

- Prepared v0.2 manifest: `outputs/local_preflight/bench/`
- Mock/offline v0.2 smoke package: `outputs/local_preflight/review/local_v02_labeled_smoke_review.zip`

Important interpretation:

- The local mock/offline smoke is expected to fail scientific acceptance because BioTruth v0.2 correctly marks it as very-low-certainty and not real enough.
- The next meaningful claim requires a strict-real run with real LLM calls, live public tools, replay, memory, and judge/expert scoring.

## Phase 0: Freeze, Baseline, and Reproducibility

### Objective

Make the current system state reproducible and reviewable before changing scientific behavior.

### Engineering Tasks

1. Create a baseline git tag at the current clean `main`.
2. Copy the 4-case canary summary artifacts into a stable repo path.
3. Write a baseline report that explains what the 4-case canary proves and does not prove.
4. Add a reproducibility section with exact local and RunPod commands.
5. Add a claims boundary section so future docs do not overstate the result.
6. Verify that current tests still pass before Phase 1 work begins.

### Artifacts

- `docs/AUTOSCIENTIST_BASELINE_20260524.md`
- `docs/results/biotruth_4_case_canary_20260524/benchmark_summary.md`
- `docs/results/biotruth_4_case_canary_20260524/biotruth_scores.md`
- `docs/results/biotruth_4_case_canary_20260524/benchmark_summary.json`
- `docs/results/biotruth_4_case_canary_20260524/biotruth_scores.json`

### Verification

Run:

```bash
python -m pytest tools/tests/test_biotruth_benchmark.py tools/tests/test_biotruth_pipeline.py tools/tests/test_score_biomedical_correctness.py
```

Pass criteria:

- Tests pass.
- Baseline tag exists.
- Baseline docs exist.
- The copied summary files are parseable.

### Exit Criteria

Phase 0 is complete only when a reviewer can inspect the baseline result without opening RunPod.

## Phase 1: BioTruth Critic Layer

### Objective

Add a stricter internal scientific critic that evaluates every generated hypothesis before final reporting.

The critic should be structured, deterministic where possible, and auditable. It should not replace the final external judge; it should improve the runtime before outputs are produced.

### Scientific Questions the Critic Must Answer

1. Is the target actually relevant to the disease, not just co-mentioned?
2. Is there causal support, or only correlation?
3. Is the disease context specific enough, including subtype when relevant?
4. Is there human evidence, animal evidence, cell evidence, genetics evidence, or only literature frequency?
5. Is there counterevidence?
6. Is there translational support such as approved drugs, clinical trials, or tractability?
7. Are there safety or adverse-effect concerns?
8. Is the evidence strong enough to make a hypothesis, or should the system abstain?

### Proposed Component

Add:

`apps/api/app/services/biotruth_critic.py`

Core API:

```python
def evaluate_hypothesis(
    *,
    task: dict[str, Any],
    hypothesis: dict[str, Any],
    evidence: list[dict[str, Any]],
    tool_calls: list[dict[str, Any]],
    public_labels: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ...
```

Expected output schema:

```json
{
  "schema": "autosci.biotruth_critic.v0.1",
  "verdict": "support|weak_support|conflicting|abstain",
  "weighted_score": 0.0,
  "confidence": 0.0,
  "dimension_scores": {
    "disease_relevance": 0,
    "causal_support": 0,
    "mechanistic_plausibility": 0,
    "human_evidence": 0,
    "translational_support": 0,
    "contradiction_handling": 0,
    "safety_awareness": 0,
    "uncertainty_calibration": 0
  },
  "evidence_tier_counts": {},
  "contradictions": [],
  "missing_evidence": [],
  "abstention_reasons": [],
  "rationale": "short reviewer-readable explanation"
}
```

### Scoring Dimensions

`disease_relevance`

- 0: Target and disease are not connected.
- 1: Only weak co-mention.
- 2: Some disease relevance but vague or nonspecific.
- 3: Disease-specific evidence exists.
- 4: Strong disease-specific evidence exists.
- 5: Strong disease/subtype-specific evidence with clear label support.

`causal_support`

- 0: No causal evidence.
- 1: Only association language.
- 2: Weak mechanistic or preclinical support.
- 3: Plausible causal mechanism or genetics signal.
- 4: Multiple causal evidence types.
- 5: Strong causal evidence across genetics/perturbation/clinical mechanism.

`mechanistic_plausibility`

- 0: No mechanism.
- 1: Generic pathway claim.
- 2: Broad pathway match.
- 3: Plausible disease mechanism.
- 4: Strong mechanism with named pathway/cell/process.
- 5: Mechanism connects target, disease biology, intervention, and expected outcome.

`human_evidence`

- 0: None.
- 1: Literature co-mentions only.
- 2: human observational or weak association.
- 3: human genetics, clinical association, or patient-derived evidence.
- 4: strong human evidence.
- 5: strong human evidence plus clinical or therapeutic validation.

`translational_support`

- 0: no tractability or clinical evidence.
- 1: unclear tractability.
- 2: druggability or tractability signal.
- 3: compounds/trials/approved drug in adjacent context.
- 4: disease-relevant clinical or approved-drug support.
- 5: strong disease-relevant therapeutic validation.

`contradiction_handling`

- 0: no counterevidence considered.
- 1: mentions limitations vaguely.
- 2: weak limitations.
- 3: explicit counterevidence search.
- 4: counterevidence considered and integrated.
- 5: balanced conclusion changes based on counterevidence.

`safety_awareness`

- 0: no safety discussion.
- 1: generic caveat.
- 2: target-level safety concern noted.
- 3: disease/intervention-specific safety issue noted.
- 4: safety affects experiment or translational recommendation.
- 5: safety is integrated into final decision.

`uncertainty_calibration`

- 0: overconfident unsupported conclusion.
- 1: weak caveat but strong conclusion.
- 2: some uncertainty.
- 3: calibrated confidence.
- 4: calibrated plus specific missing evidence.
- 5: abstains or downgrades when evidence is insufficient.

### Integration Points

Primary integration:

- After hypothesis generation and critique, before final report.

Secondary integration:

- Benchmark artifacts should include critic output.
- Final report should include critic verdict and abstention reasons.
- Memory should store critic verdict and score.
- Benchmark scoring should include critic pass/fail fields.

Likely files:

- `apps/api/app/services/biotruth_critic.py`
- `agents/app/langgraph_workflow.py`
- `tools/run_autoscientist_bench.py`
- `tools/score_biomedical_correctness.py`
- tests under `tools/tests/` or `apps/api/tests/`

### Tests

Add unit tests for:

1. Strong evidence returns `support`.
2. Only PubMed co-mention returns `weak_support` or `abstain`.
3. Missing disease relevance returns `abstain`.
4. Contradictory evidence returns `conflicting`.
5. Safety warning lowers score.
6. Empty evidence never passes.
7. Output schema is stable.

### Local Verification

Run:

```bash
python -m pytest tools/tests/test_biotruth_critic.py
python -m pytest tools/tests/test_biotruth_benchmark.py tools/tests/test_biotruth_pipeline.py
```

### Strict-Real Verification

Only after local tests pass:

```bash
bash infra/runpod/run_biotruth_4_case_canary.sh
```

Expected improvement:

- Full-system judge score should not regress materially.
- Critic output appears in every full result.
- Weak or under-evidenced outputs should have lower internal scores.
- Internal `100` inflation should be reduced or explained.

### Exit Criteria

Phase 1 is complete when critic outputs exist in benchmark artifacts and local tests prove abstention/conflict behavior.

## Phase 2: Evidence Hierarchy

### Objective

Replace flat evidence counting with evidence-tier reasoning.

### Evidence Tiers

Tier 1: high-confidence clinical/translational evidence

- approved therapy in disease
- disease-specific clinical trial evidence
- strong clinical genetics
- validated diagnostic or therapeutic target

Tier 2: strong human biological evidence

- GWAS/rare variant support
- patient expression or single-cell evidence
- disease-relevant tissue/cell evidence
- strong OpenTargets association with meaningful evidence types

Tier 3: functional/mechanistic evidence

- perturbation experiment
- pathway mechanism
- cell/animal model
- target modulation affects disease-relevant phenotype

Tier 4: tractability/supporting context

- druggability
- protein structure or ligandability
- pathway membership
- known compounds outside disease

Tier 5: weak literature context

- PubMed co-mentions
- broad review statements
- generic pathway association
- unverified LLM assertions

### Engineering Tasks

1. Add an evidence classifier.
2. Attach `evidence_tier` and `evidence_type` to every evidence item where possible.
3. Penalize final confidence when high-tier evidence is absent.
4. Make the final report show evidence grouped by tier.
5. Add benchmark metrics:
   - high-tier evidence count
   - weak-only evidence flag
   - evidence diversity score
   - public evidence coverage score

### Proposed Component

`apps/api/app/services/evidence_hierarchy.py`

Core API:

```python
def classify_evidence_item(item: dict[str, Any]) -> dict[str, Any]:
    ...

def summarize_evidence_hierarchy(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    ...
```

### Tests

1. Approved drug evidence maps to Tier 1.
2. OpenTargets genetics evidence maps to Tier 2.
3. PubMed count-only evidence maps to Tier 5.
4. Empty evidence has zero diversity.
5. Mixed evidence produces higher hierarchy score than weak-only evidence.

### Exit Criteria

Phase 2 is complete when benchmark artifacts expose evidence-tier metrics and reports no longer treat every evidence item equally.

## Phase 3: Contradiction Detection

### Objective

Force the system to search for evidence against its own hypothesis.

### Contradiction Types

1. Failed clinical trial.
2. Negative or weak association.
3. Disease-subtype mismatch.
4. Target effect opposite to desired biology.
5. Toxicity or intolerable safety signal.
6. Redundant pathway or compensation.
7. Biomarker-only relevance with no therapeutic implication.
8. Evidence from the wrong organism, tissue, or disease context.

### Engineering Tasks

1. Add contradiction search queries for each target-disease pair.
2. Store contradiction evidence separately.
3. Include contradiction coverage in critic scoring.
4. Require final reports to include a "counterevidence and limitations" section.
5. Lower confidence when contradictions are not searched or not addressed.

### Proposed Component

`apps/api/app/services/contradiction_detector.py`

Core API:

```python
def build_contradiction_queries(task: dict[str, Any]) -> list[str]:
    ...

def detect_contradictions(
    *,
    task: dict[str, Any],
    evidence: list[dict[str, Any]],
    tool_calls: list[dict[str, Any]],
) -> dict[str, Any]:
    ...
```

### Tests

1. Negative trial wording is detected.
2. "No association" wording is detected.
3. Wrong disease context is flagged.
4. Contradiction search absent lowers critic score.
5. Contradictions appear in final artifact.

### Exit Criteria

Phase 3 is complete when the system can produce a credible "supporting and opposing evidence" packet.

## Phase 4: Abstention Policy

### Objective

Make abstention a first-class scientific outcome.

### Abstention Conditions

1. No disease-specific evidence.
2. Evidence is mostly weak co-mention.
3. Contradictions dominate support.
4. No public tool evidence is available in strict-real mode.
5. Tool failures prevent evidence coverage.
6. Human/translational evidence is absent for high-risk claims.
7. Critic score falls below a threshold.

### Engineering Tasks

1. Add `abstention_policy.py`.
2. Add final report state: `supported`, `tentative`, `conflicting`, `abstained`.
3. Store abstention reason in trace, memory, and benchmark outputs.
4. Add benchmark metrics:
   - correct abstention rate
   - overclaim rate
   - unsupported support rate

### Tests

1. Empty evidence abstains.
2. Weak-only evidence abstains or returns tentative.
3. Strong known positive does not abstain.
4. Contradiction-heavy case abstains or returns conflicting.

### Exit Criteria

Phase 4 is complete when the system can refuse to support weak hypotheses and benchmarks track that as success, not failure.

## Phase 5: Adaptive Tool Planning

### Objective

Move from mostly fixed tool execution to gap-driven tool selection.

### Evidence Gap Types

1. Disease relevance gap.
2. Causal support gap.
3. Human evidence gap.
4. Mechanism gap.
5. Translational support gap.
6. Safety gap.
7. Contradiction gap.
8. Ontology/entity resolution gap.

### Engineering Tasks

1. Add evidence gap detection after initial retrieval.
2. Map each gap to tool families.
3. Add retry and fallback logic.
4. Add a tool budget policy.
5. Make SciFlow policy propose next useful tool/action based on gaps.
6. Record whether the planner followed or rejected policy suggestions.

### Tool Selection Policy

Example:

- If disease relevance gap: OpenTargets, disease ontology, PubMed target-disease query.
- If human evidence gap: OpenTargets genetics/evidence, PubMed clinical query.
- If mechanism gap: pathway lookup, GO/Reactome, literature mechanism query.
- If translational gap: clinical trials, drugs, tractability, PubChem.
- If contradiction gap: PubMed negative query, clinical trial failure query.
- If safety gap: drug adverse event/safety lookup where available.

### Tests

1. Missing human evidence triggers human-evidence tool request.
2. Missing contradiction search triggers contradiction tool request.
3. Failed primary tool triggers fallback.
4. Tool budget stops runaway retries.
5. Trace shows gap-to-tool rationale.

### Exit Criteria

Phase 5 is complete when traces show tool calls are selected because of evidence gaps, not just a fixed sequence.

## Phase 6: Tool Depth Expansion

### Objective

Add deeper biomedical evidence sources while keeping each adapter small, testable, and failure-tolerant.

### Tool Candidates

Pathway and mechanism:

- Reactome API or static Reactome mapping.
- GO annotations.
- WikiPathways where practical.

Clinical and translational:

- ClinicalTrials.gov API.
- DrugBank only if licensing allows; otherwise avoid.
- OpenTargets tractability and known drugs.
- PubChem compound context.

Safety:

- openFDA adverse event signals where practical.
- SIDER if accessible and license-compatible.

Perturbation/expression:

- LINCS/CMap if practical.
- Expression Atlas or curated static starter set.
- DepMap for oncology target dependency when practical.

KG reasoning:

- OpenTargets evidence graph fields.
- Hetionet or RTX-KG2-style public resources if manageable.
- Keep this optional until API reliability is clear.

### Engineering Tasks

1. Add one tool family at a time.
2. Each tool gets:
   - adapter
   - schema
   - timeout
   - health check
   - unit test
   - smoke test
   - benchmark trace field
3. Add tool usefulness scoring.
4. Add source attribution in final reports.

### Priority Order

1. ClinicalTrials.gov.
2. Reactome/GO pathway lookup.
3. OpenTargets evidence-type extraction improvements.
4. Safety/adverse-event lookup.
5. Perturbation/expression source.
6. KG reasoning layer.

### Exit Criteria

Phase 6 is complete when new tools demonstrably improve evidence hierarchy coverage and appear in strict-real traces.

## Phase 7: BioTruth v0.2 Benchmark

### Objective

Create a more credible benchmark with positive, weak, conflicting, and abstention-required cases.

### Dataset Design

Case categories:

1. Strong positive target-disease pairs.
2. Moderate support target-disease pairs.
3. Weak/co-mention-only pairs.
4. Contradiction-heavy pairs.
5. Wrong disease/subtype pairs.
6. Safety-limited pairs.
7. Insufficient-evidence pairs.

Domains:

1. Oncology.
2. Autoimmune/inflammation.
3. Neurodegeneration.
4. Metabolic disease.
5. Rare disease.
6. Infectious disease.

Gold labels:

- `strong_support`
- `moderate_support`
- `weak_support`
- `conflicting`
- `insufficient_evidence`
- `contraindicated_or_safety_limited`

### Engineering Tasks

1. Build `benchmarks/biotruth_seed_cases_v0_2.json`.
2. Build `benchmarks/biotruth_rubric_v0_2.json`.
3. Add benchmark builder support for gold labels.
4. Add leaderboard summary.
5. Add per-domain and per-label failure analysis.
6. Add a `--case-stratification` or equivalent report.

### Verification

Local:

```bash
python tools/build_biotruth_benchmark.py --seed-cases benchmarks/biotruth_seed_cases_v0_2.json --rubric benchmarks/biotruth_rubric_v0_2.json --output-manifest outputs/biotruth_v0_2_manifest.json --max-cases 12
```

Strict-real canary:

- 6 cases.
- `full`, `no_public_tools`, `no_critic`.

Full run:

- 25 to 50 cases first.
- 100 cases only after the 25-case run gives useful signal.

### Exit Criteria

Phase 7 is complete when benchmark outputs show correctness by domain, label, and ablation.

## Phase 8: SciFlow Policy Model Upgrade

### Objective

Train the workflow policy on richer scientific outcomes, not just next-action traces.

### Current Model Weakness

The current policy model can predict workflow actions, but the benchmark only shows modest value from SciFlow. It needs labels that reflect scientific usefulness.

### New Training Signals

1. Critic score.
2. Evidence hierarchy score.
3. Contradiction coverage.
4. Correct abstention.
5. Tool usefulness.
6. Wasted tool calls.
7. Successful gap closure.
8. Judge score.

### New Prediction Targets

1. Next best evidence gap to close.
2. Next best tool family.
3. Whether to stop, continue, retry, or abstain.
4. Expected value of a tool call.
5. Risk of overclaim.

### Engineering Tasks

1. Extend workflow policy examples with critic/gap labels.
2. Add training export schema.
3. Add model metrics:
   - top-1 next useful action
   - tool value ranking
   - abstention accuracy
   - wasted-call reduction
4. Add ablation:
   - `no_sciflow`
   - `old_sciflow`
   - `new_sciflow`

### Exit Criteria

Phase 8 is complete when SciFlow improves judge score, reduces wasted calls, or improves abstention/critic outcomes beyond current modest gains.

## Phase 9: Reviewer Package and Communication Artifacts

### Objective

Make the system easy to review without running it.

### Package Contents

1. One-page executive summary.
2. Architecture diagram.
3. Benchmark summary.
4. BioTruth score report.
5. Ablation table.
6. Per-case case studies.
7. Critic outputs.
8. Evidence hierarchy report.
9. Contradiction report.
10. Abstention report.
11. State graph export.
12. Replay bundles.
13. Model card for SciFlow.
14. Claims and limitations.
15. Reproducibility commands.

### Engineering Tasks

1. Extend `tools/collect_review_package.py`.
2. Add `docs/CLAIMS_AND_LIMITATIONS.md`.
3. Add model card generation.
4. Add benchmark card generation.
5. Add artifact manifest with file descriptions.

### Exit Criteria

Phase 9 is complete when a reviewer can open the zip and understand what was tested, what improved, and what remains unproven.

## Phase 10: Final Strict-Real Run

### Objective

Run a cost-controlled strict-real benchmark only after the improved local system is ready.

### Preflight Gates

1. Local unit tests pass.
2. Integration tests pass.
3. Benchmark builder works locally.
4. Mock/export pipeline works.
5. API keys validated.
6. ToolUniverse health check passes.
7. Public biomedical API smoke tests pass.
8. Expected artifact list is defined.
9. Run budget is defined.
10. Stop/pull instructions are tested.

### Run Sequence

1. 2-case strict-real smoke.
2. 6-case critic canary.
3. 12-case benchmark.
4. 25-case benchmark if results are stable.
5. 50 or 100 cases only if the 25-case benchmark demonstrates useful signal.

### Final Success Criteria

The system is meaningfully stronger if it shows:

1. Higher judge score than the baseline full run.
2. Clear advantage over no-public-tools.
3. Clear advantage over no-critic.
4. Reduced overclaim rate.
5. Correct abstention on weak/contradictory cases.
6. Stronger evidence hierarchy coverage.
7. Reviewer package with traceable evidence and limitations.

### Exit Criteria

Phase 10 is complete when the final package contains enough evidence for a serious research discussion, not just a demo.

## Implementation Order

1. Phase 0: freeze and baseline.
2. Phase 1: BioTruth Critic.
3. Phase 2: Evidence Hierarchy.
4. Phase 4: Abstention.
5. Phase 3: Contradiction Detection.
6. Phase 5: Adaptive Tool Planning.
7. Phase 6: Tool Depth Expansion.
8. Phase 7: BioTruth v0.2.
9. Phase 8: SciFlow upgrade.
10. Phase 9: Reviewer package.
11. Phase 10: strict-real final run.

The ordering intentionally puts critic, hierarchy, and abstention before deeper tool expansion. Tool depth helps only if the system can judge evidence correctly.

## Local Pre-Pod Readiness Update: 2026-05-24

### Completed Before GPU Benchmarking

1. Phase 0 baseline artifacts were created, including the baseline document, canary output directory, and explicit claims/limitations boundary.
2. Phase 1 BioTruth Critic is implemented as an auditable runtime critic with weighted dimensions for disease relevance, causal support, mechanism, human evidence, translation, contradiction handling, safety awareness, and uncertainty calibration.
3. Phase 2 Evidence Hierarchy is implemented and classifies evidence into clinical/translational, human biology, mechanistic, tractability, literature-context, and unknown tiers.
4. Phase 3 Contradiction Detection is implemented and records contradiction-search status and findings for downstream abstention and scoring.
5. Phase 4 Abstention Policy is implemented and forces claim boundaries when evidence is weak, contradictory, or missing.
6. Phase 5 Adaptive Tool Planning is implemented and recommends follow-up evidence tools from evidence gaps instead of blindly running a fixed tool list.
7. Phase 6 Tool Depth Expansion now includes real public biomedical paths for NCBI Gene, PubMed, ClinicalTrials.gov, Reactome pathway search, openFDA adverse-event search, and ToolUniverse/OpenTargets where available.
8. Phase 7 BioTruth v0.2 exists as a seed benchmark, task generator, rubric, score packets, heuristic scorer, and review-package path.
9. Phase 8 SciFlow Policy now trains from richer trace examples that include critic outcome, abstention decision, evidence hierarchy, contradiction status, and adaptive-plan context.
10. Phase 9 Review Package generation includes an artifact guide, benchmark summary, score packets, state graph, model package, claims/limitations, and reproducibility context.

### Bugs Found And Fixed During Readiness

1. The strict real benchmark artifact was initially missing validation fields because `build_report` did not expose board-post validation controls; this is fixed and covered by regression tests.
2. The persisted hypothesis board post was initially missing the evidence hierarchy; this is fixed in run persistence.
3. The BioTruth critic initially lost benchmark task metadata during workflow execution, causing a false abstention on a strong TNF/rheumatoid arthritis case; the workflow now lifts benchmark context into runtime state and the regression checks disease relevance.

### Verified Local Gates

1. Full unit/integration test suite: `103 passed`.
2. Python compile check for API services, routes, agents, and tools: passed.
3. Live public biomedical smoke tests: NCBI Gene, PubMed, ClinicalTrials.gov, Reactome, and openFDA all returned successful live responses.
4. Machine preflight: critical checks passed; local warnings remain for low disk space and missing local NVIDIA GPU, both expected on the laptop.
5. ToolUniverse preflight: ready and executable.
6. Anthropic preflight: live key call succeeded; Gemini key remains invalid/rate-limited and should not be used for the next strict run.
7. Privacy scan for private-person names in tracked docs/code paths returned no hits.

### Latest Strict Real Local Smoke

Artifact directory: `outputs/local_preflight/real_anthropic_contextfixed_onecase/20260524_202825`

Review package: `outputs/local_preflight/review/local_real_anthropic_contextfixed_onecase_review.zip`

Observed result:

1. One TNF/rheumatoid arthritis strict-real task completed.
2. Anthropic LLM executed.
3. Public biomedical tools executed: 22 calls, 22 successes.
4. ToolUniverse executed: 9 calls, 9 successes.
5. Total tool calls: 53.
6. Validation controls present in the final report: BioTruth critic, abstention policy, contradiction analysis, evidence hierarchy, and adaptive tool plan.
7. BioTruth critic verdict: `support`.
8. Abstention policy decision: `support_allowed`.
9. BioTruth heuristic weighted score: `85.0`.
10. Critical failure rate: `0.0`.
11. State graph export: 3,033 nodes, 10,999 edges, 376 hypotheses, 518 entities, 1,000 experiments, 11 tools.
12. Neural policy holdout top-1: `0.8724`.

### Remaining Caveats Before A Public Claim

1. The strict real result is still a one-case smoke, not a benchmark claim.
2. The BioTruth score was heuristic, not expert-scored or LLM-judge-scored.
3. The next pod run should start with a small strict real canary before any 20-case or 100-case benchmark.
4. A credible research claim still requires full versus ablation comparisons across diverse cases.

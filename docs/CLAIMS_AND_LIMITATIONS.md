# AutoScientist Claims and Limitations

## What Can Be Claimed

AutoScientist is an auditable biomedical hypothesis-generation and evidence-workflow runtime.

The current system can:

- Parse biomedical objectives into target, disease, intervention, and evidence needs.
- Run public biomedical tools such as PubMed, NCBI Gene, PubChem, ClinicalTrials.gov, and ToolUniverse/OpenTargets when available.
- Produce traceable hypothesis cards, evidence summaries, critique outputs, proposed experiments, replay bundles, and scientific memory records.
- Use SciState Graph to retain hypotheses, entities, evidence, tool calls, experiments, confidence signals, and replay lineage across runs.
- Use SciFlow Policy as a workflow-controller model that learns from traces and scientific outcome labels.
- Benchmark full-system behavior against ablations such as no public tools, no memory, and no SciFlow.

## What Must Not Be Claimed Yet

AutoScientist is not a validated clinical decision system.

The current system does not prove:

- New biological discovery.
- Clinical efficacy or safety.
- That a target should be used in patients.
- That benchmark score alone equals expert biological correctness.
- That SciFlow Policy replaces foundation models or biomedical experts.

## Current Evidence

The strongest completed result is the 4-case strict-real BioTruth canary:

- Full system judge score: 79.5.
- No-public-tools judge score: 56.75.
- No-memory judge score: 74.5.
- No-SciFlow judge score: 76.75.
- 16/16 run artifacts completed.

Interpretation:

- Public biomedical grounding is the largest proven source of value.
- Memory and SciFlow show useful but still modest gains on the small canary.
- The system is strongest as reproducible biomedical research infrastructure.

## Validation Requirements Before Stronger Claims

Before making stronger claims, run:

- BioTruth v0.2 stratified benchmark with strong, moderate, weak, conflicting, safety-limited, and insufficient-evidence cases.
- Full vs no-public-tools vs no-memory vs no-SciFlow vs no-critic ablations.
- Judge scoring plus human expert spot checks.
- Failure analysis by disease area, gold label, evidence tier, and expected decision.
- Review of representative replay bundles and score packets.

## Correct Framing

Best current framing:

AutoScientist is a persistent biomedical evidence-workflow system that can help researchers generate, audit, and stress-test target-disease hypotheses with public tools, provenance, memory, and learned workflow control.

Avoid framing it as:

- A replacement for scientists.
- A clinical advisor.
- A model that has discovered validated therapies.
- A frontier biomedical foundation model.

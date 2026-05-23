# BioTruth 100-Task Case Selection

This 100-task campaign uses 25 target-disease cases and 4 task templates per case.

The goal is not to maximize task count. The goal is to produce a compact but comprehensive scientific stress test that asks whether AutoScientist can generate useful, auditable research dossiers across different kinds of biomedical evidence.

## Design

Each case is expanded into four workflows:

- target validity review;
- mechanism and safety review;
- experiment decision plan;
- evidence grade and replay.

Together, these test whether the system can move from a target-disease question to a bounded scientific position, evidence synthesis, translational caveats, and next experiments.

## Case Families

### Clinically Precedented Targets

These cases test whether the system can recognize mature biology without pretending it made a novel discovery.

- `IL6 / rheumatoid arthritis`
- `TNF / inflammatory bowel disease`
- `BRAF / melanoma`
- `EGFR / lung adenocarcinoma`
- `ERBB2 / breast cancer`
- `PCSK9 / familial hypercholesterolemia`
- `VEGFA / age-related macular degeneration`

### Strong Genetics, Hard Translation

These cases test whether the system separates disease association from therapeutic actionability.

- `NOD2 / Crohn disease`
- `PTPN22 / rheumatoid arthritis`
- `APOE / Alzheimer disease`
- `LRRK2 / Parkinson disease`
- `HTT / Huntington disease`
- `DMD / Duchenne muscular dystrophy`

### Precision Oncology And Biomarker Context

These cases test mutation specificity, resistance reasoning, patient selection, and safety.

- `ALK / lung cancer`
- `PARP1 / ovarian cancer`
- `KRAS / pancreatic cancer`
- `BRAF / melanoma`
- `EGFR / lung adenocarcinoma`
- `ERBB2 / breast cancer`

### Rare And Monogenic Disease

These cases test causal biology, modality choice, delivery constraints, and genotype specificity.

- `CFTR / cystic fibrosis`
- `SMN1 / spinal muscular atrophy`
- `ACVR1 / fibrodysplasia ossificans progressiva`
- `GAA / Pompe disease`
- `F9 / hemophilia B`

### Neurodegeneration Stress Tests

These cases are intentionally difficult because evidence can be strong biologically but weak translationally.

- `APP / Alzheimer disease`
- `APOE / Alzheimer disease`
- `LRRK2 / Parkinson disease`
- `SOD1 / amyotrophic lateral sclerosis`
- `HTT / Huntington disease`

### Safety And Translational Nuance

These cases test whether the system avoids simplistic ranking and surfaces risk.

- `SLC5A2 / type 2 diabetes mellitus`
- `TYK2 / psoriasis`
- `VEGFA / age-related macular degeneration`
- `IL6 / rheumatoid arthritis`
- `TNF / inflammatory bowel disease`

## Why This Is Comprehensive

The panel covers:

- autoimmune and inflammatory disease;
- oncology;
- rare Mendelian disease;
- neurodegeneration;
- cardiometabolic disease;
- hematology;
- ophthalmology.

It also covers different evidence types:

- public target-disease associations;
- human genetics;
- clinical precedent;
- druggability and tractability;
- safety and adverse-effect context;
- literature-rich and translationally ambiguous cases;
- monogenic causal biology;
- biomarker-defined precision medicine.

## What A Strong Result Should Show

A strong AutoScientist output should:

- stay grounded in public evidence;
- avoid claiming proof of new biology;
- distinguish mature targets from uncertain hypotheses;
- preserve weak and failed branches;
- propose concrete experiments with decision gates;
- produce replayable traces and state-graph artifacts;
- surface cross-case insights that help a scientist decide where to spend attention.

## What Would Count As Failure

Failure modes include:

- wrong target or disease;
- fabricated citations or identifiers;
- unsupported causal claims;
- treating Open Targets scores as clinical proof;
- hiding weak evidence branches;
- proposing generic experiments without controls, readouts, or decision gates;
- overclaiming discovery instead of research acceleration.


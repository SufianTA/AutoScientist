# Evidence Scorer

Milestone 5 will replace the current rule-based scorer with a lightweight biomedical evidence classifier.

Planned model:

- Encoder: PubMedBERT, BioLinkBERT, or SciBERT.
- Inputs: hypothesis, evidence text, evidence source, entity context.
- Labels: strong_support, weak_support, mechanistic_relevant, irrelevant, contradicts, safety_concern.
- Metrics: macro-F1, calibration, abstention behavior.


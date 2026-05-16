# ACVR1 pathway modulation as a candidate strategy for FOP

Run: `run_0c5a5801d22f`
Status: `completed`
Confidence: `0.61`

## Candidate Hypothesis

Modulating ACVR1-linked BMP signaling is a candidate, evidence-supported but not validated therapeutic hypothesis for FOP.

## Evidence

| Source | Label | Score | Evidence |
| --- | --- | --- | --- |
| acvr1_target_profile_tool | strong_support | 0.84 | ACVR1 activating variants are linked to FOP and BMP/osteogenic signaling. |
| fop_disease_profile_tool | strong_support | 0.84 | FOP is a rare disorder with progressive heterotopic ossification and strong ACVR1 causal link. |

## Research Board Posts

### hypothesis by publisher_agent

```json
{
  "title": "ACVR1 pathway modulation as a candidate strategy for FOP",
  "hypothesis": "Modulating ACVR1-linked BMP signaling is a candidate, evidence-supported but not validated therapeutic hypothesis for FOP.",
  "evidence": [
    {
      "source": "acvr1_target_profile_tool",
      "text": "ACVR1 activating variants are linked to FOP and BMP/osteogenic signaling.",
      "structured": {
        "gene_symbol": "ACVR1",
        "name": "Activin A receptor type 1",
        "mechanism_notes": [
          "ACVR1 encodes a BMP type I receptor involved in osteogenic signaling.",
          "FOP is commonly associated with activating ACVR1 variants such as R206H.",
          "Therapeutic modulation should be framed as pathway-level hypothesis, not validated efficacy."
        ],
        "pathways": [
          "BMP signaling",
          "TGF-beta superfamily signaling",
          "osteogenic differentiation"
        ],
        "known_variants": [
          {
            "variant": "R206H",
            "context": "canonical FOP-associated activating variant"
          }
        ]
      },
      "score": {
        "label": "strong_support",
        "score": 0.84,
        "evidence_type": "mechanistic",
        "rationale": "Rule-based prototype scorer. Replace with PubMedBERT/SciBERT classifier for Milestone 5.",
        "warnings": [
          "Prototype score is not a validation claim."
        ]
      }
    },
    {
      "source": "fop_disease_profile_tool",
      "text": "FOP is a rare disorder with progressive heterotopic ossification and strong ACVR1 causal link.",
      "structured": {
        "disease": "Fibrodysplasia Ossificans Progressiva",
        "abbreviation": "FOP",
        "summary": "Rare genetic disorder characterized by progressive heterotopic ossification.",
        "causal_links": [
          {
            "gene": "ACVR1",
            "relationship": "strong genetic association"
          }
        ],
        "phenotypes": [
          "heterotopic ossification",
          "flare-ups",
          "progressive mobility restriction"
        ],
        "guardrail": "Candidate interventions require experimental and clinical validation."
      },
      "score": {
        "label": "strong_support",
        "score": 0.84,
        "evidence_type": "mechanistic",
        "rationale": "Rule-based prototype scorer. Replace with PubMedBERT/SciBERT classifier for Milestone 5.",
        "warnings": [
          "Prototype score is not a validation claim."
        ]
      }
    }
  ],
  "contradictions": [],
  "confidence": 0.61,
  "limitations": [
    "Mock evidence requires replacement with live ToolUniverse and literature calls.",
    "No clinical efficacy or safety claim is made.",
    "Compound specificity and translational risk remain unresolved."
  ],
  "next_experiments": [
    {
      "name": "Validate ACVR1/FOP evidence with live target-disease and literature tools",
      "type": "computational",
      "cost": "low",
      "feasibility": "high",
      "expected_information_gain": "high"
    },
    {
      "name": "Prioritize candidate inhibitors by potency, selectivity, and ADMET evidence",
      "type": "computational",
      "cost": "low-medium",
      "feasibility": "medium",
      "expected_information_gain": "high"
    },
    {
      "name": "Test BMP pathway readouts in disease-relevant cellular model",
      "type": "wet_lab",
      "cost": "medium",
      "feasibility": "medium",
      "expected_information_gain": "high"
    }
  ],
  "critique": {
    "critique_type": "translation_gap",
    "severity": "medium",
    "critique": "The mechanism is plausible, but mock evidence is not sufficient to rank clinical candidates or claim efficacy.",
    "recommended_fix": "Replace mock profiles with ToolUniverse target-disease, literature, ChEMBL, and safety calls before escalation.",
    "abstention_required": false
  },
  "run_config": {
    "agent_count": 6,
    "max_runtime_minutes": 30,
    "tool_budget_usd": 10.0,
    "evidence_strictness": "balanced",
    "human_review_required": true,
    "execution_mode": "inline",
    "execution_backend": "local_process",
    "agent_framework": "langgraph",
    "openclaw_enabled": false,
    "llm_provider": "mock",
    "llm_model": "mock-scientist",
    "llm_api_key_env_var": "",
    "model_tool_names": [],
    "model_tool_configs": []
  }
}
```

### critique by critic_agent

```json
{
  "critique_type": "translation_gap",
  "severity": "medium",
  "critique": "The mechanism is plausible, but mock evidence is not sufficient to rank clinical candidates or claim efficacy.",
  "recommended_fix": "Replace mock profiles with ToolUniverse target-disease, literature, ChEMBL, and safety calls before escalation.",
  "abstention_required": false
}
```

## Guardrails

- Candidate hypothesis only.
- Computationally prioritized and evidence-supported, not validated.
- Requires experimental validation before clinical interpretation.

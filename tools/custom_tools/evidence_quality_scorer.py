import re

from tools.custom_tools.base import ScientificTool, ToolResult

# Oncology driver genes commonly studied in drug-target hypotheses
_ONCOGENE_SYMBOLS = frozenset({
    "egfr", "kras", "braf", "ret", "met", "alk", "ros1", "ntrk",
    "erbb2", "her2", "pik3ca", "pten", "tp53", "brca1", "brca2",
    "cdkn2a", "rb1", "apc", "vhl", "flt3", "npm1", "jak2", "myd88",
    "idh1", "idh2", "nras", "hras", "nf1", "nf2", "stk11", "keap1",
    "mtor", "fgfr1", "fgfr2", "fgfr3", "pdgfra", "kit", "cdk4", "cdk6",
    "bcr", "abl", "myc", "mycn", "mdm2", "atm", "chek2", "palb2",
    "arid1a", "smad4", "tsc1", "tsc2", "hras", "rhoa", "notch1",
    "ctnnb1", "axin1", "fbxw7", "map2k1", "map2k2",
})

_CANCER_TERMS = frozenset({
    "cancer", "carcinoma", "adenocarcinoma", "lymphoma", "leukemia",
    "leukaemia", "melanoma", "sarcoma", "glioma", "glioblastoma",
    "myeloma", "tumor", "tumour", "neoplasm", "malignancy", "blastoma",
    "nsclc", "sclc", "dlbcl", "aml", "cll", "cml", "hcc", "rcc",
    "metastasis", "metastatic", "oncology", "oncogenic", "driver mutation",
    "targeted therapy", "immunotherapy", "checkpoint inhibitor",
    "resistance", "progression", "relapse", "remission",
    "proliferation", "apoptosis", "senescence", "angiogenesis",
})


class EvidenceQualityScorerTool(ScientificTool):
    name = "evidence_quality_scorer_tool"
    description = "Scores whether evidence supports, contradicts, or is irrelevant to a therapeutic hypothesis."
    example_input = {
        "hypothesis": "Inhibiting ACVR1 may reduce aberrant osteogenic signaling in FOP.",
        "evidence_text": "ACVR1 variants activate BMP signaling in FOP models.",
        "evidence_source": "mock_literature",
    }

    def _run(self, payload: dict) -> ToolResult:
        text = str(payload.get("evidence_text", "")).lower()
        hypothesis = str(payload.get("hypothesis", "")).lower()
        source = str(payload.get("evidence_source", "")).lower()
        hypothesis_terms = {
            term
            for term in re.split(r"[\s/\-,;]+", hypothesis)
            if len(term) >= 4 and term not in {
                "candidate", "hypothesis", "mechanisms", "relevant",
                "modulating", "targeting", "inhibiting", "activating",
                "linked", "context", "disease", "therapy", "therapeutic",
            }
        }
        overlap = sum(1 for term in hypothesis_terms if term in text)

        # ---- source-type short-circuits ----
        if source.startswith("local_objective_context"):
            label, score, evidence_type = "mechanistic_relevance", 0.35, "planning_context"
            return self._result(label, score, evidence_type, payload)
        if source.startswith("local_retrieval_plan"):
            label, score, evidence_type = "irrelevant", 0.1, "retrieval_plan"
            return self._result(label, score, evidence_type, payload)

        # ---- safety / toxicity ----
        if any(term in text for term in ["toxicity", "unsafe", "adverse", "safety", "side effect"]):
            label, score, evidence_type = "safety_concern", 0.72, "safety"
            return self._result(label, score, evidence_type, payload)

        # ---- contradiction ----
        if "contradict" in text or "no association" in text or "failed" in text and "trial" in text:
            label, score, evidence_type = "contradicts", 0.69, "literature"
            return self._result(label, score, evidence_type, payload)

        # ---- domain-specific strong-support rules ----
        # FOP / ACVR1 / BMP
        if (
            "acvr1" in text
            and ("fop" in text or "fibrodysplasia" in text)
            and ("bmp" in text or "osteogenic" in text or "ossification" in text)
        ):
            label, score, evidence_type = "strong_support", 0.84, "mechanistic"
            return self._result(label, score, evidence_type, payload)

        # Oncology driver gene + cancer context
        hyp_oncogenes = _ONCOGENE_SYMBOLS.intersection(hypothesis_terms)
        text_has_cancer = any(term in text for term in _CANCER_TERMS)
        text_oncogenes = {sym for sym in _ONCOGENE_SYMBOLS if sym in text}
        shared_oncogenes = hyp_oncogenes.intersection(text_oncogenes)
        if shared_oncogenes and text_has_cancer:
            if overlap >= 3:
                label, score, evidence_type = "strong_support", 0.82, "mechanistic"
            elif overlap >= 2:
                label, score, evidence_type = "strong_support", 0.76, "mechanistic"
            else:
                label, score, evidence_type = "weak_support", 0.65, "mechanistic"
            return self._result(label, score, evidence_type, payload)

        # Oncology gene in hypothesis but only cancer context in text (no gene overlap)
        if hyp_oncogenes and text_has_cancer and overlap >= 1:
            label, score, evidence_type = "weak_support", 0.62, "mechanistic"
            return self._result(label, score, evidence_type, payload)

        # Generic overlap scoring
        if overlap >= 3:
            label, score, evidence_type = "strong_support", 0.76, "mechanistic"
        elif overlap >= 2:
            label, score, evidence_type = "weak_support", 0.61, "mechanistic"
        elif overlap >= 1 and any(
            term in text for term in ["mutation", "mutations", "associated", "association", "therapeutic target"]
        ):
            label, score, evidence_type = "weak_support", 0.58, "mechanistic"
        elif "acvr1" in text or "bmp" in text or "fibrodysplasia" in text or "ossification" in text:
            label, score, evidence_type = "weak_support", 0.58, "mechanistic"
        elif text_has_cancer and overlap >= 1:
            label, score, evidence_type = "weak_support", 0.55, "mechanistic"
        elif "pubchem" in text or "candidate" in text or "compound" in text:
            label, score, evidence_type = "mechanistic_relevance", 0.46, "chemical"
        else:
            label, score, evidence_type = "irrelevant", 0.31, "unknown"

        return self._result(label, score, evidence_type, payload)

    def _result(self, label: str, score: float, evidence_type: str, payload: dict) -> ToolResult:
        return ToolResult(
            status="success",
            input=payload,
            output={
                "label": label,
                "score": score,
                "evidence_type": evidence_type,
                "rationale": (
                    "Deterministic evidence scorer using safety terms, oncology gene/cancer keyword overlap, "
                    "and domain-specific mechanism cues. Strict runs can replace this with a real LLM scorer."
                ),
                "warnings": ["Score is not a validation claim."],
            },
            sources=[{"name": "Deterministic evidence scorer", "id": "evidence-scorer-v0.3"}],
            confidence=score,
        )

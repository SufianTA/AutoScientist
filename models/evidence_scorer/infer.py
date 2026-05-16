from tools.custom_tools.evidence_quality_scorer import EvidenceQualityScorerTool


def score(hypothesis: str, evidence_text: str, evidence_source: str = "manual") -> dict:
    tool = EvidenceQualityScorerTool()
    return tool.run(
        {
            "hypothesis": hypothesis,
            "evidence_text": evidence_text,
            "evidence_source": evidence_source,
        }
    ).output


if __name__ == "__main__":
    print(
        score(
            "Inhibiting ACVR1 may reduce aberrant osteogenic signaling in FOP.",
            "ACVR1 variants activate BMP signaling in FOP models.",
        )
    )


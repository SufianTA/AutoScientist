import re

from tools.custom_tools.base import ScientificTool, ToolResult


class ExperimentRecommendationTool(ScientificTool):
    name = "experiment_recommendation_tool"
    description = "Ranks computational and wet-lab validation steps for a hypothesis card."
    example_input = {"hypothesis_card": {"title": "Target modulation in a disease context"}}

    # Maps (lowercased keyword set) → (wet-lab readout, intervention ranking description)
    _DOMAIN_READOUTS: list[tuple[tuple[str, ...], str, str]] = [
        # FOP / BMP / ACVR1
        (
            ("acvr1", "bmp", "ossification", "fibrodysplasia", "fop"),
            "Test disease-relevant BMP/activin pathway readouts in appropriate cellular or animal models",
            "Rank candidate interventions by target potency, pathway selectivity, exposure, and ADMET liabilities",
        ),
        # PCSK9 / LDL / cholesterol
        (
            ("pcsk9", "ldlr", "cholesterol", "ldl"),
            "Test LDL receptor abundance, LDL uptake, and cholesterol-clearance readouts in hepatocyte models",
            "Rank candidate interventions by PCSK9/LDLR mechanism, durability, exposure, and safety liabilities",
        ),
        # CFTR / cystic fibrosis
        (
            ("cftr", "cystic fibrosis"),
            "Test epithelial ion transport, protein processing, and rescue readouts in disease-relevant airway models",
            "Rank candidate interventions by target engagement, rescue magnitude, exposure, and safety liabilities",
        ),
        # EGFR / lung cancer
        (
            ("egfr", "lung cancer", "nsclc", "non-small cell"),
            "Test EGFR phosphorylation, downstream MAPK/PI3K signaling, and cell-viability readouts in EGFR-mutant "
            "lung cancer cell lines; include resistance mutant panels (T790M, C797S, exon 20 insertions)",
            "Rank candidate interventions by EGFR mutant selectivity, wild-type sparing, CNS penetration, "
            "acquired-resistance profile, and ADMET liabilities",
        ),
        # KRAS / NRAS / HRAS
        (
            ("kras", "nras", "hras", "ras mutation", "ras-driven"),
            "Test RAS effector pathway suppression (RAF/MEK/ERK, PI3K/AKT), growth inhibition, and apoptosis "
            "in RAS-mutant tumor cell lines and patient-derived organoids",
            "Rank candidate interventions by RAS isoform/allele selectivity, feedback-reactivation liability, "
            "combination synergy (SOS1i, MEKi), and ADMET liabilities",
        ),
        # BRAF / MEK / RAF
        (
            ("braf", "v600", "braf v600e", "braf v600k", "raf"),
            "Test BRAF-pathway flux (p-ERK, p-MEK), proliferation block, and paradoxical-activation risk "
            "in BRAF-mutant cell lines and patient-derived melanoma or CRC models",
            "Rank candidate interventions by BRAF mutation selectivity, paradoxical-activation profile, "
            "combination potential (MEKi, immunotherapy), and ADMET liabilities",
        ),
        # RET fusion / thyroid / lung
        (
            ("ret", "ret fusion", "thyroid cancer", "papillary thyroid"),
            "Test RET kinase activity, downstream RAS/MAPK/PI3K signaling, and anti-proliferative readouts "
            "in RET-fusion or RET-mutant cell lines (thyroid and lung)",
            "Rank candidate interventions by RET selectivity vs. wild-type, solvent-front resistance "
            "mutation coverage, and ADMET liabilities",
        ),
        # MET exon 14 / MET amplification
        (
            ("met", "met exon 14", "met amplification", "hepatocyte growth factor", "hgf"),
            "Test MET phosphorylation, HGF-driven invasive growth, and 3D invasion readouts in MET-exon-14-skip "
            "or MET-amplified models; include bypass resistance assays (KRAS, EGFR)",
            "Rank candidate interventions by MET exon-14 vs. amplification coverage, CNS penetration, "
            "resistance bypass profile, and ADMET liabilities",
        ),
        # ALK / ROS1 / NTRK fusions
        (
            ("alk", "ros1", "ntrk", "trk fusion", "alk fusion"),
            "Test ALK/ROS1/NTRK kinase inhibition, downstream signaling suppression, and tumor regression "
            "in fusion-positive cell lines and xenograft models; include CNS penetration assays",
            "Rank candidate interventions by fusion-partner coverage, CNS exposure, next-generation selectivity "
            "over on-target resistance mutations, and ADMET liabilities",
        ),
        # CDK4/6 / cell cycle
        (
            ("cdk4", "cdk6", "rb1", "cyclin d", "cell cycle"),
            "Test Rb phosphorylation, G1 arrest, senescence induction, and combination effects with "
            "endocrine or PI3K-pathway agents in CDK4/6-dependent tumor models",
            "Rank candidate interventions by CDK4/6 selectivity, combination synergy (fulvestrant, alpelisib), "
            "resistance profile (CCND1 amp, Rb loss), and ADMET liabilities",
        ),
        # BRCA / HRD / PARP
        (
            ("brca1", "brca2", "parp", "homologous recombination", "hrd", "hrd-positive"),
            "Test PARP trapping, replication-fork collapse, and synthetic lethality in BRCA-deficient tumor models; "
            "include HRD biomarker profiling",
            "Rank candidate interventions by PARP trapping potency, reversion-mutation resistance risk, "
            "combination potential (platinum, immunotherapy), and ADMET liabilities",
        ),
        # PI3K / AKT / mTOR
        (
            ("pik3ca", "pten", "akt", "mtor", "pi3k"),
            "Test PI3K/AKT/mTOR pathway flux, feedback reactivation (RTK upregulation), and anti-tumor "
            "efficacy in PIK3CA-mutant or PTEN-null models",
            "Rank candidate interventions by isoform selectivity, feedback-loop resistance profile, "
            "combination synergy (CDK4/6i, endocrine), and ADMET liabilities",
        ),
        # Immunotherapy / checkpoint / PD-1 / PD-L1
        (
            ("pd-1", "pd-l1", "ctla-4", "checkpoint", "immunotherapy", "car-t", "car t"),
            "Test tumor immune infiltration, T-cell activation readouts, and combination efficacy in "
            "co-culture or syngeneic tumor models; include biomarker (TMB, MSI) stratification",
            "Rank candidate interventions by response-biomarker correlation, combination modality "
            "(PD-1/L1, CTLA-4, ADC), resistance mechanism coverage, and manufacturing/safety liabilities",
        ),
    ]

    def _run(self, payload: dict) -> ToolResult:
        hypothesis_card = payload.get("hypothesis_card", {})
        case_profile = hypothesis_card.get("case_profile", {}) if isinstance(hypothesis_card.get("case_profile"), dict) else {}
        title = str(hypothesis_card.get("title", "candidate hypothesis"))
        hypothesis = str(hypothesis_card.get("hypothesis", ""))
        if " pathway modulation" in title:
            target = title.split(" pathway modulation", 1)[0].strip() or "the target"
        elif " clinical-precedence" in title:
            target = title.split(" clinical-precedence", 1)[0].strip() or "the target"
        else:
            target = title.split(" ", 1)[0].strip() or "the target"
        disease = title.rsplit(" for ", 1)[-1].strip() if " for " in title else "the disease context"
        if disease == title:
            disease = "the disease context"
        profile_entities = case_profile.get("entities", {}) if isinstance(case_profile.get("entities"), dict) else {}
        primary_genes = [str(g) for g in (profile_entities.get("genes") or profile_entities.get("context_primary_genes") or [])]
        primary_diseases = [str(d) for d in (profile_entities.get("diseases") or profile_entities.get("context_diseases") or [])]
        if primary_genes:
            target = primary_genes[0]
        if primary_diseases:
            disease = primary_diseases[0]
        lowered = f"{target} {disease} {title} {hypothesis}".lower()
        has_safety = bool(hypothesis_card.get("contradictions"))

        wet_lab_readout, intervention_ranking = self._select_domain_readouts(
            lowered,
            primary_genes=primary_genes,
            primary_diseases=primary_diseases,
        )

        return ToolResult(
            status="success",
            input=payload,
            output={
                "experiments": [
                    {
                        "name": (
                            f"Resolve the highest-uncertainty {target} / {disease} evidence gap with targeted "
                            "Open Targets, literature, clinical-precedence, and safety review"
                        ),
                        "type": "computational",
                        "cost": "low",
                        "feasibility": "high",
                        "expected_information_gain": "high",
                        "decision_gate": (
                            "Proceed only if the result changes target validity, clinical-precedence "
                            "interpretation, safety risk, or patient-stratification strategy."
                        ),
                        "failure_modes": [
                            "Evidence is indirect or about a related receptor/pathway rather than the target itself.",
                            "Clinical-precedence evidence is retrieved but not separated from new-discovery questions.",
                        ],
                    },
                    {
                        "name": intervention_ranking,
                        "type": "computational",
                        "cost": "low-medium",
                        "feasibility": "medium",
                        "expected_information_gain": "high",
                        "decision_gate": (
                            "Advance only if the ranking distinguishes established intervention precedent "
                            "from unresolved translational gaps."
                        ),
                    },
                    {
                        "name": (
                            "Run safety-first triage before efficacy assays: exposure margins, off-target biology, "
                            "and disease-context tolerability"
                            if has_safety
                            else wet_lab_readout
                        ),
                        "type": "computational_plus_wet_lab" if has_safety else "wet_lab",
                        "cost": "medium",
                        "feasibility": "medium",
                        "expected_information_gain": "high",
                        "success_criteria": [
                            "Uses disease-relevant samples or models.",
                            "Includes positive/negative controls and a failure criterion.",
                            "Directly tests the gap identified by evidence synthesis rather than only confirming pathway activity.",
                        ],
                    },
                ]
            },
            confidence=0.7,
        )

    def _select_domain_readouts(
        self,
        lowered: str,
        primary_genes: list[str] | None = None,
        primary_diseases: list[str] | None = None,
    ) -> tuple[str, str]:
        # Score each domain by number of matching keywords to prefer more-specific matches.
        # This prevents EGFR domain (which shares "nsclc") from overriding KRAS domain
        # when "kras" appears alongside "egfr" as a bypass target in the same hypothesis.
        best_match: tuple[str, str] | None = None
        best_score = 0.0
        anchors = {item.lower() for item in (primary_genes or []) + (primary_diseases or []) if item}
        for keywords, readout, ranking in self._DOMAIN_READOUTS:
            score = 0.0
            for kw in keywords:
                if self._keyword_present(lowered, kw):
                    score += 1.0
                if kw.lower() in anchors:
                    score += 4.0
            if score > best_score:
                best_score = score
                best_match = (readout, ranking)
        if best_match and best_score > 0:
            return best_match
        return (
            "Test target-pathway and disease-phenotype readouts in disease-relevant cellular or animal models",
            "Rank candidate interventions by target engagement, selectivity, exposure, and ADMET liabilities",
        )

    def _keyword_present(self, text: str, keyword: str) -> bool:
        keyword = keyword.lower().strip()
        if not keyword:
            return False
        if " " in keyword or "-" in keyword:
            return keyword in text
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", text))

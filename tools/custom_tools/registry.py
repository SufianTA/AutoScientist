from tools.custom_tools.acvr1_target_profile import Acvr1TargetProfileTool
from tools.custom_tools.evidence_quality_scorer import EvidenceQualityScorerTool
from tools.custom_tools.experiment_recommendation import ExperimentRecommendationTool
from tools.custom_tools.fop_disease_profile import FopDiseaseProfileTool
from tools.custom_tools.hypothesis_card_generator import HypothesisCardGeneratorTool
from tools.custom_tools.live_biomedical import (
    ClinicalTrialsSearchTool,
    NCBIGeneProfileTool,
    OpenFDAAdverseEventTool,
    PubChemCandidateTool,
    PubMedLiteratureSearchTool,
    ReactomePathwaySearchTool,
)
from tools.custom_tools.rdkit_descriptor import RdkitDescriptorTool


def build_custom_tools() -> dict:
    tools = [
        Acvr1TargetProfileTool(),
        FopDiseaseProfileTool(),
        RdkitDescriptorTool(),
        EvidenceQualityScorerTool(),
        HypothesisCardGeneratorTool(),
        ExperimentRecommendationTool(),
        NCBIGeneProfileTool(),
        PubMedLiteratureSearchTool(),
        PubChemCandidateTool(),
        ClinicalTrialsSearchTool(),
        ReactomePathwaySearchTool(),
        OpenFDAAdverseEventTool(),
    ]
    return {tool.name: tool for tool in tools}

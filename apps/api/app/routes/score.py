from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from tools.custom_tools.evidence_quality_scorer import EvidenceQualityScorerTool

router = APIRouter(prefix="/score", tags=["score"])


class EvidenceScoreRequest(BaseModel):
    hypothesis: str
    evidence_text: str
    evidence_source: str = "user"
    entity_context: dict[str, Any] = Field(default_factory=dict)


@router.post("/evidence")
def score_evidence(payload: EvidenceScoreRequest) -> dict:
    result = EvidenceQualityScorerTool().run(payload.model_dump()).model_dump()
    return {"score": result["output"], "tool_result": result}

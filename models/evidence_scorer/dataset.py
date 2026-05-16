from pydantic import BaseModel, Field


class EvidenceScorerExample(BaseModel):
    hypothesis: str
    evidence_text: str
    evidence_source: str
    entity_context: dict = Field(default_factory=dict)
    label: str


from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AgentStateName(str, Enum):
    INTAKE_OBJECTIVE = "INTAKE_OBJECTIVE"
    CLASSIFY_OBJECTIVE = "CLASSIFY_OBJECTIVE"
    PLAN_RESEARCH = "PLAN_RESEARCH"
    FIND_TOOLS = "FIND_TOOLS"
    EXECUTE_EVIDENCE_COLLECTION = "EXECUTE_EVIDENCE_COLLECTION"
    GENERATE_HYPOTHESES = "GENERATE_HYPOTHESES"
    SCORE_EVIDENCE = "SCORE_EVIDENCE"
    CRITIQUE_AND_REFINE = "CRITIQUE_AND_REFINE"
    DEBATE_AND_REVISE = "DEBATE_AND_REVISE"
    PROPOSE_EXPERIMENTS = "PROPOSE_EXPERIMENTS"
    PUBLISH_BOARD_POST = "PUBLISH_BOARD_POST"
    GENERATE_REPORT = "GENERATE_REPORT"


class ResearchRunState(BaseModel):
    run_id: str
    objective_id: str
    objective: str
    current_state: AgentStateName = AgentStateName.INTAKE_OBJECTIVE
    context: dict[str, Any] = Field(default_factory=dict)
    plan: list[str] = Field(default_factory=list)
    selected_tools: list[str] = Field(default_factory=list)
    tool_outputs: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    hypothesis_card: dict[str, Any] = Field(default_factory=dict)
    critique: dict[str, Any] = Field(default_factory=dict)
    experiments: list[dict[str, Any]] = Field(default_factory=list)
    report: dict[str, Any] = Field(default_factory=dict)

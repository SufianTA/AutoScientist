from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class Base(DeclarativeBase):
    pass


class Objective(Base):
    __tablename__ = "objectives"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("obj"))
    title: Mapped[str] = mapped_column(String(255))
    objective_text: Mapped[str] = mapped_column(Text)
    constraints_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    runs: Mapped[list["Run"]] = relationship(back_populates="objective")


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("run"))
    objective_id: Mapped[str] = mapped_column(ForeignKey("objectives.id"))
    status: Mapped[str] = mapped_column(String(40), default="created")
    current_state: Mapped[str] = mapped_column(String(80), default="INTAKE_OBJECTIVE")
    run_config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    agent_count: Mapped[int] = mapped_column(Integer, default=6)
    max_runtime_minutes: Mapped[int] = mapped_column(Integer, default=30)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    queued_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    final_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    objective: Mapped[Objective] = relationship(back_populates="runs")


class AgentStep(Base):
    __tablename__ = "agent_steps"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("step"))
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    agent_name: Mapped[str] = mapped_column(String(120))
    state_name: Mapped[str] = mapped_column(String(120))
    input_json: Mapped[dict] = mapped_column(JSON, default=dict)
    output_json: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class ToolCall(Base):
    __tablename__ = "tool_calls"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("toolcall"))
    run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.id"), nullable=True)
    step_id: Mapped[str | None] = mapped_column(ForeignKey("agent_steps.id"), nullable=True)
    tool_name: Mapped[str] = mapped_column(String(160))
    tool_source: Mapped[str] = mapped_column(String(80), default="custom")
    input_json: Mapped[dict] = mapped_column(JSON, default=dict)
    output_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(40))
    latency_ms: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EvidenceItem(Base):
    __tablename__ = "evidence_items"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("ev"))
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    source: Mapped[str] = mapped_column(String(160))
    source_url_or_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    evidence_text: Mapped[str] = mapped_column(Text)
    structured_json: Mapped[dict] = mapped_column(JSON, default=dict)
    support_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    support_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Hypothesis(Base):
    __tablename__ = "hypotheses"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("hyp"))
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    title: Mapped[str] = mapped_column(String(255))
    hypothesis_text: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(80), default="candidate")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BoardPost(Base):
    __tablename__ = "board_posts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("post"))
    post_type: Mapped[str] = mapped_column(String(80))
    run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.id"), nullable=True)
    hypothesis_id: Mapped[str | None] = mapped_column(ForeignKey("hypotheses.id"), nullable=True)
    agent_author: Mapped[str] = mapped_column(String(120))
    content_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ModelScore(Base):
    __tablename__ = "model_scores"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("score"))
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    evidence_id: Mapped[str | None] = mapped_column(ForeignKey("evidence_items.id"), nullable=True)
    model_name: Mapped[str] = mapped_column(String(160))
    label: Mapped[str] = mapped_column(String(80))
    score: Mapped[float] = mapped_column(Float)
    rationale: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

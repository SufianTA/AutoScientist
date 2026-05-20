from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
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
    account_id: Mapped[str | None] = mapped_column(ForeignKey("billing_accounts.id"), nullable=True)
    payment_status: Mapped[str] = mapped_column(String(40), default="not_required")
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


class BillingAccount(Base):
    __tablename__ = "billing_accounts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("acct"))
    owner_email: Mapped[str] = mapped_column(String(255), unique=True)
    display_name: Mapped[str] = mapped_column(String(255))
    balance_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CreditLedgerEntry(Base):
    __tablename__ = "credit_ledger_entries"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("ledger"))
    account_id: Mapped[str] = mapped_column(ForeignKey("billing_accounts.id"))
    run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.id"), nullable=True)
    entry_type: Mapped[str] = mapped_column(String(40))
    amount_usd: Mapped[float] = mapped_column(Float)
    balance_after_usd: Mapped[float] = mapped_column(Float)
    description: Mapped[str] = mapped_column(Text)
    external_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CheckoutSession(Base):
    __tablename__ = "checkout_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("checkout"))
    account_id: Mapped[str] = mapped_column(ForeignKey("billing_accounts.id"))
    amount_usd: Mapped[float] = mapped_column(Float)
    provider: Mapped[str] = mapped_column(String(40), default="mock")
    status: Mapped[str] = mapped_column(String(40), default="created")
    checkout_url: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ModelTool(Base):
    __tablename__ = "model_tools"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("modeltool"))
    name: Mapped[str] = mapped_column(String(160), unique=True)
    description: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(80))
    endpoint_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    api_key_env_var: Mapped[str | None] = mapped_column(String(160), nullable=True)
    input_schema_json: Mapped[dict] = mapped_column(JSON, default=dict)
    output_schema_json: Mapped[dict] = mapped_column(JSON, default=dict)
    tooluniverse_config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(40), default="registered")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ScientificEntity(Base):
    __tablename__ = "scientific_entities"
    __table_args__ = (UniqueConstraint("entity_type", "normalized_name", name="uq_scientific_entity"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("entity"))
    entity_type: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(255))
    normalized_name: Mapped[str] = mapped_column(String(255))
    aliases_json: Mapped[list] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    first_seen_run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.id"), nullable=True)
    last_seen_run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.id"), nullable=True)
    mention_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ScientificHypothesisMemory(Base):
    __tablename__ = "scientific_hypothesis_memory"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("memhyp"))
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    hypothesis_id: Mapped[str | None] = mapped_column(ForeignKey("hypotheses.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    hypothesis_text: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(80), default="candidate")
    entity_ids_json: Mapped[list] = mapped_column(JSON, default=list)
    evidence_summary_json: Mapped[dict] = mapped_column(JSON, default=dict)
    failure_modes_json: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ScientificCausalLink(Base):
    __tablename__ = "scientific_causal_links"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("causal"))
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    source_entity_id: Mapped[str | None] = mapped_column(ForeignKey("scientific_entities.id"), nullable=True)
    target_entity_id: Mapped[str | None] = mapped_column(ForeignKey("scientific_entities.id"), nullable=True)
    relation: Mapped[str] = mapped_column(String(120))
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence_ids_json: Mapped[list] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ExperimentMemory(Base):
    __tablename__ = "experiment_memory"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("exp"))
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    hypothesis_memory_id: Mapped[str | None] = mapped_column(
        ForeignKey("scientific_hypothesis_memory.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255))
    experiment_type: Mapped[str] = mapped_column(String(120), default="unknown")
    expected_information_gain: Mapped[str | None] = mapped_column(String(120), nullable=True)
    feasibility: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(80), default="proposed")
    protocol_json: Mapped[dict] = mapped_column(JSON, default=dict)
    result_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RunReplay(Base):
    __tablename__ = "run_replays"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("replay"))
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), unique=True)
    replay_hash: Mapped[str] = mapped_column(String(80))
    bundle_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ToolBenchmark(Base):
    __tablename__ = "tool_benchmarks"
    __table_args__ = (UniqueConstraint("tool_name", "tool_source", name="uq_tool_benchmark"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("toolbench"))
    tool_name: Mapped[str] = mapped_column(String(160))
    tool_source: Mapped[str] = mapped_column(String(80))
    call_count: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    avg_usefulness: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AgentRoleMemory(Base):
    __tablename__ = "agent_role_memory"
    __table_args__ = (UniqueConstraint("agent_name", name="uq_agent_role_memory"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("agentmem"))
    agent_name: Mapped[str] = mapped_column(String(120))
    role_summary: Mapped[str] = mapped_column(Text)
    run_count: Mapped[int] = mapped_column(Integer, default=0)
    last_run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.id"), nullable=True)
    memory_json: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WorkflowPolicyExample(Base):
    __tablename__ = "workflow_policy_examples"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("policyex"))
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    step_index: Mapped[int] = mapped_column(Integer)
    state_name: Mapped[str] = mapped_column(String(120))
    action_type: Mapped[str] = mapped_column(String(80))
    action_name: Mapped[str] = mapped_column(String(160))
    context_json: Mapped[dict] = mapped_column(JSON, default=dict)
    outcome_json: Mapped[dict] = mapped_column(JSON, default=dict)
    reward: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WorkflowPolicyModel(Base):
    __tablename__ = "workflow_policy_models"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("policymodel"))
    name: Mapped[str] = mapped_column(String(160))
    version: Mapped[str] = mapped_column(String(80))
    model_type: Mapped[str] = mapped_column(String(120), default="scientific_workflow_policy")
    training_summary_json: Mapped[dict] = mapped_column(JSON, default=dict)
    artifact_path: Mapped[str] = mapped_column(String(512))
    metrics_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

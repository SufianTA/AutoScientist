from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, ToolBenchmark, WorkflowPolicyExample
from app.services.neural_workflow_policy import (
    MODEL_TYPE,
    predict_neural_workflow_policy,
    train_neural_workflow_policy_model,
)


torch = pytest.importorskip("torch")


def test_neural_workflow_policy_trains_and_predicts(tmp_path) -> None:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_cls = sessionmaker(bind=engine)
    db = session_cls()
    try:
        now = datetime.utcnow()
        actions = [
            ("START", "state_transition", "INITIALIZE_FRAMEWORK"),
            ("INITIALIZE_FRAMEWORK", "state_transition", "CLASSIFY_OBJECTIVE"),
            ("TOOL_SELECTION", "tool_call", "ncbi_gene_profile_tool"),
            ("TOOL_SELECTION", "tool_call", "evidence_quality_scorer_tool"),
        ]
        for run_index in range(6):
            objective = "PCSK9 familial hypercholesterolemia" if run_index % 2 else "ACVR1 FOP"
            for step_index, (state, action_type, action_name) in enumerate(actions):
                db.add(
                    WorkflowPolicyExample(
                        run_id=f"run_{run_index}",
                        step_index=step_index,
                        state_name=state,
                        action_type=action_type,
                        action_name=action_name,
                        context_json={
                            "objective": objective,
                            "previous_state": state,
                            "tool_source": "live_public_biomedical",
                            "run_config": {"llm_provider": "mock"},
                        },
                        outcome_json={"status": "success"},
                        reward=0.8,
                        created_at=now + timedelta(seconds=run_index * 10 + step_index),
                    )
                )
        db.add(
            ToolBenchmark(
                tool_name="ncbi_gene_profile_tool",
                tool_source="live_public_biomedical",
                call_count=6,
                success_count=6,
                failure_count=0,
                avg_latency_ms=25,
                avg_usefulness=0.7,
            )
        )
        model = train_neural_workflow_policy_model(
            db,
            artifact_dir=tmp_path,
            epochs=4,
            hidden_dim=16,
            batch_size=4,
            vocab_size=128,
        )
        db.commit()
        db.refresh(model)

        predictions = predict_neural_workflow_policy(
            {
                "objective": "PCSK9 familial hypercholesterolemia",
                "state_name": "TOOL_SELECTION",
                "tool_source": "live_public_biomedical",
            },
            model_path=model.artifact_path,
            top_k=3,
        )

        assert model.model_type == MODEL_TYPE
        assert model.metrics_json["training_examples"] >= 1
        assert model.metrics_json["top3_training_accuracy"] is not None
        assert predictions
        assert all("probability" in prediction for prediction in predictions)
    finally:
        db.close()

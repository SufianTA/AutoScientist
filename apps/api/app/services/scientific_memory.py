from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import (
    AgentRoleMemory,
    AgentStep,
    BoardPost,
    EvidenceItem,
    ExperimentMemory,
    Hypothesis,
    Objective,
    Run,
    RunReplay,
    ScientificCausalLink,
    ScientificEntity,
    ScientificHypothesisMemory,
    ToolBenchmark,
    ToolCall,
    WorkflowPolicyExample,
    WorkflowPolicyModel,
)


TOKEN_RE = re.compile(r"[A-Za-z0-9_+-]{2,}")


def persist_scientific_memory(db: Session, run: Run, state: Any | None = None) -> dict[str, Any]:
    """Project a completed run into persistent scientific memory.

    The normalized run/evidence tables remain the source of truth. These memory
    tables add cross-run retrieval, replay, benchmarking, and policy training
    views that can survive across AutoScientist sessions.
    """

    objective = db.get(Objective, run.objective_id)
    steps = db.query(AgentStep).filter(AgentStep.run_id == run.id).order_by(AgentStep.started_at.asc()).all()
    tool_calls = db.query(ToolCall).filter(ToolCall.run_id == run.id).order_by(ToolCall.created_at.asc()).all()
    evidence = db.query(EvidenceItem).filter(EvidenceItem.run_id == run.id).all()
    hypotheses = db.query(Hypothesis).filter(Hypothesis.run_id == run.id).all()
    posts = db.query(BoardPost).filter(BoardPost.run_id == run.id).all()

    entity_ids = _persist_entities(db, run, objective, evidence, posts)
    hypothesis_memory_ids = _persist_hypotheses(db, run, hypotheses, evidence, posts, entity_ids)
    causal_links = _persist_causal_links(db, run, evidence, entity_ids)
    experiments = _persist_experiments(db, run, posts, hypothesis_memory_ids)
    replay = persist_replay_bundle(db, run, objective, steps, tool_calls, evidence, hypotheses, posts)
    tool_benchmarks = update_tool_benchmarks(db, run, tool_calls, evidence)
    agent_memories = update_agent_role_memory(db, run, steps)
    policy_examples = persist_policy_examples(db, run, objective, steps, tool_calls)

    return {
        "entities": len(entity_ids),
        "hypothesis_memories": len(hypothesis_memory_ids),
        "causal_links": causal_links,
        "experiments": experiments,
        "replay_id": replay.id,
        "tool_benchmarks": tool_benchmarks,
        "agent_memories": agent_memories,
        "policy_examples": policy_examples,
    }


def persist_replay_bundle(
    db: Session,
    run: Run,
    objective: Objective | None,
    steps: list[AgentStep],
    tool_calls: list[ToolCall],
    evidence: list[EvidenceItem],
    hypotheses: list[Hypothesis],
    posts: list[BoardPost],
) -> RunReplay:
    bundle = build_replay_bundle(run, objective, steps, tool_calls, evidence, hypotheses, posts)
    replay_hash = hashlib.sha256(json.dumps(bundle, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    replay = db.query(RunReplay).filter(RunReplay.run_id == run.id).first()
    if replay is None:
        replay = RunReplay(run_id=run.id, replay_hash=replay_hash, bundle_json=bundle)
        db.add(replay)
    else:
        replay.replay_hash = replay_hash
        replay.bundle_json = bundle
    return replay


def build_replay_bundle(
    run: Run,
    objective: Objective | None,
    steps: list[AgentStep],
    tool_calls: list[ToolCall],
    evidence: list[EvidenceItem],
    hypotheses: list[Hypothesis],
    posts: list[BoardPost],
) -> dict[str, Any]:
    return {
        "schema": "autosci.run_replay.v1",
        "run": {
            "id": run.id,
            "objective_id": run.objective_id,
            "status": run.status,
            "current_state": run.current_state,
            "run_config": run.run_config_json,
            "final_confidence": run.final_confidence,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        },
        "objective": {
            "title": objective.title if objective else None,
            "text": objective.objective_text if objective else None,
            "constraints": objective.constraints_json if objective else {},
        },
        "steps": [
            {
                "agent_name": step.agent_name,
                "state_name": step.state_name,
                "input": step.input_json,
                "output": step.output_json,
                "error": step.error,
                "completed_at": step.completed_at.isoformat() if step.completed_at else None,
            }
            for step in steps
        ],
        "tool_calls": [
            {
                "tool_name": call.tool_name,
                "tool_source": call.tool_source,
                "input": call.input_json,
                "output": call.output_json,
                "status": call.status,
                "latency_ms": call.latency_ms,
            }
            for call in tool_calls
        ],
        "evidence": [
            {
                "source": item.source,
                "text": item.evidence_text,
                "structured": item.structured_json,
                "support_label": item.support_label,
                "support_score": item.support_score,
            }
            for item in evidence
        ],
        "hypotheses": [
            {
                "title": hypothesis.title,
                "text": hypothesis.hypothesis_text,
                "confidence": hypothesis.confidence,
                "status": hypothesis.status,
            }
            for hypothesis in hypotheses
        ],
        "board_posts": [
            {
                "post_type": post.post_type,
                "agent_author": post.agent_author,
                "content": post.content_json,
            }
            for post in posts
        ],
    }


def update_tool_benchmarks(
    db: Session,
    run: Run,
    tool_calls: list[ToolCall],
    evidence: list[EvidenceItem],
) -> int:
    evidence_scores_by_source: dict[str, list[float]] = defaultdict(list)
    for item in evidence:
        if item.support_score is not None:
            evidence_scores_by_source[item.source].append(float(item.support_score))

    updated = 0
    for call in tool_calls:
        benchmark = (
            db.query(ToolBenchmark)
            .filter(ToolBenchmark.tool_name == call.tool_name, ToolBenchmark.tool_source == call.tool_source)
            .first()
        )
        if benchmark is None:
            benchmark = ToolBenchmark(tool_name=call.tool_name, tool_source=call.tool_source)
            db.add(benchmark)
            db.flush()
        benchmark.call_count = benchmark.call_count or 0
        benchmark.success_count = benchmark.success_count or 0
        benchmark.failure_count = benchmark.failure_count or 0
        benchmark.avg_latency_ms = benchmark.avg_latency_ms or 0.0
        old_count = benchmark.call_count
        new_count = old_count + 1
        benchmark.call_count = new_count
        benchmark.success_count += 1 if call.status == "success" else 0
        benchmark.failure_count += 0 if call.status == "success" else 1
        benchmark.avg_latency_ms = _running_average(benchmark.avg_latency_ms, old_count, float(call.latency_ms or 0))
        scores = evidence_scores_by_source.get(call.tool_name) or evidence_scores_by_source.get(call.tool_source) or []
        if scores:
            usefulness = sum(scores) / len(scores)
            prior = benchmark.avg_usefulness if benchmark.avg_usefulness is not None else usefulness
            benchmark.avg_usefulness = _running_average(prior, old_count, usefulness)
        if call.status != "success":
            benchmark.last_error = json.dumps(call.output_json, default=str)[:1000]
        benchmark.last_run_id = run.id
        benchmark.updated_at = datetime.utcnow()
        updated += 1
    return updated


def update_agent_role_memory(db: Session, run: Run, steps: list[AgentStep]) -> int:
    by_agent: dict[str, list[AgentStep]] = defaultdict(list)
    for step in steps:
        by_agent[step.agent_name].append(step)
    for agent_name, agent_steps in by_agent.items():
        memory = db.query(AgentRoleMemory).filter(AgentRoleMemory.agent_name == agent_name).first()
        if memory is None:
            memory = AgentRoleMemory(agent_name=agent_name, role_summary="")
            db.add(memory)
        recent_states = [step.state_name for step in agent_steps[-5:]]
        memory.run_count = (memory.run_count or 0) + 1
        memory.last_run_id = run.id
        memory.role_summary = f"{agent_name} handled {', '.join(recent_states)}"
        memory.memory_json = {
            "recent_states": recent_states,
            "last_outputs": [step.output_json for step in agent_steps[-2:]],
        }
        memory.updated_at = datetime.utcnow()
    return len(by_agent)


def persist_policy_examples(
    db: Session,
    run: Run,
    objective: Objective | None,
    steps: list[AgentStep],
    tool_calls: list[ToolCall],
) -> int:
    if db.query(WorkflowPolicyExample).filter(WorkflowPolicyExample.run_id == run.id).first():
        return 0
    reward = _run_reward(run)
    objective_text = objective.objective_text if objective else ""
    count = 0
    previous_state = "START"
    for index, step in enumerate(steps):
        db.add(
            WorkflowPolicyExample(
                run_id=run.id,
                step_index=index,
                state_name=previous_state,
                action_type="state_transition",
                action_name=step.state_name,
                context_json={
                    "objective": objective_text,
                    "previous_state": previous_state,
                    "agent_name": step.agent_name,
                    "run_config": run.run_config_json,
                },
                outcome_json=step.output_json,
                reward=reward,
            )
        )
        previous_state = step.state_name
        count += 1
    for index, call in enumerate(tool_calls):
        db.add(
            WorkflowPolicyExample(
                run_id=run.id,
                step_index=len(steps) + index,
                state_name="TOOL_SELECTION",
                action_type="tool_call",
                action_name=call.tool_name,
                context_json={
                    "objective": objective_text,
                    "tool_source": call.tool_source,
                    "run_config": run.run_config_json,
                },
                outcome_json={"status": call.status, "latency_ms": call.latency_ms},
                reward=reward if call.status == "success" else min(0.0, reward - 0.25),
            )
        )
        count += 1
    return count


def train_workflow_policy_model(
    db: Session,
    *,
    name: str = "scientific_workflow_policy",
    artifact_dir: str | Path = "outputs/models",
) -> WorkflowPolicyModel:
    examples = db.query(WorkflowPolicyExample).all()
    action_counts: Counter[str] = Counter()
    feature_action_counts: dict[str, Counter[str]] = defaultdict(Counter)
    rewards: dict[str, list[float]] = defaultdict(list)
    for example in examples:
        action = f"{example.action_type}:{example.action_name}"
        action_counts[action] += 1
        rewards[action].append(float(example.reward or 0.0))
        for token in _tokens_for_context(example.context_json, example.state_name):
            feature_action_counts[token][action] += 1

    model = {
        "schema": "autosci.scientific_workflow_policy.v1",
        "name": name,
        "trained_at": datetime.utcnow().isoformat(),
        "num_examples": len(examples),
        "action_counts": dict(action_counts),
        "feature_action_counts": {feature: dict(counts) for feature, counts in feature_action_counts.items()},
        "action_rewards": {
            action: sum(values) / len(values)
            for action, values in rewards.items()
            if values
        },
    }
    artifact_dir = Path(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    version = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    artifact_path = artifact_dir / f"{name}_{version}.json"
    artifact_path.write_text(json.dumps(model, indent=2), encoding="utf-8")
    metrics = _policy_training_metrics(examples, model)
    row = WorkflowPolicyModel(
        name=name,
        version=version,
        artifact_path=str(artifact_path),
        training_summary_json={
            "num_examples": len(examples),
            "num_actions": len(action_counts),
            "top_actions": action_counts.most_common(10),
        },
        metrics_json=metrics,
    )
    db.add(row)
    return row


def predict_next_actions(
    context: dict[str, Any],
    *,
    model_path: str | Path,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    model = json.loads(Path(model_path).read_text(encoding="utf-8"))
    action_counts = Counter(model.get("action_counts", {}))
    feature_action_counts = {
        feature: Counter(counts)
        for feature, counts in model.get("feature_action_counts", {}).items()
    }
    action_rewards = model.get("action_rewards", {})
    scores: Counter[str] = Counter()
    total_actions = sum(action_counts.values()) or 1
    for action, count in action_counts.items():
        scores[action] += math.log((count + 1) / total_actions)
    for token in _tokens_for_context(context, str(context.get("state_name", ""))):
        for action, count in feature_action_counts.get(token, {}).items():
            scores[action] += math.log(1 + count)
    ranked = []
    for action, score in scores.most_common(top_k):
        ranked.append(
            {
                "action": action,
                "score": round(float(score), 4),
                "mean_reward": round(float(action_rewards.get(action, 0.0)), 4),
                "support": int(action_counts.get(action, 0)),
            }
        )
    return ranked


def memory_summary(db: Session) -> dict[str, Any]:
    latest_model = db.query(WorkflowPolicyModel).order_by(WorkflowPolicyModel.created_at.desc()).first()
    return {
        "entities": db.query(ScientificEntity).count(),
        "hypotheses": db.query(ScientificHypothesisMemory).count(),
        "causal_links": db.query(ScientificCausalLink).count(),
        "experiments": db.query(ExperimentMemory).count(),
        "replays": db.query(RunReplay).count(),
        "tool_benchmarks": db.query(ToolBenchmark).count(),
        "agent_memories": db.query(AgentRoleMemory).count(),
        "policy_examples": db.query(WorkflowPolicyExample).count(),
        "latest_policy_model": {
            "id": latest_model.id,
            "version": latest_model.version,
            "artifact_path": latest_model.artifact_path,
            "metrics": latest_model.metrics_json,
        }
        if latest_model
        else None,
    }


def _persist_entities(
    db: Session,
    run: Run,
    objective: Objective | None,
    evidence: list[EvidenceItem],
    posts: list[BoardPost],
) -> list[str]:
    candidates: list[tuple[str, str, dict[str, Any]]] = []
    objective_text = objective.objective_text if objective else ""
    candidates.extend(("keyword", token, {"source": "objective"}) for token in _salient_terms(objective_text))
    for post in posts:
        classification = post.content_json.get("objective_classification", {}) if isinstance(post.content_json, dict) else {}
        for capability in classification.get("required_capabilities", []) or []:
            candidates.append(("capability", str(capability), {"source": "objective_classification"}))
        context = post.content_json.get("biomedical_context", {}) if isinstance(post.content_json, dict) else {}
        for key, entity_type in (
            ("primary_genes", "gene"),
            ("diseases", "disease"),
            ("candidate_interventions", "intervention"),
        ):
            for value in context.get(key, []) or []:
                candidates.append((entity_type, str(value), {"source": "biomedical_context"}))
    for item in evidence:
        for token in _salient_terms(f"{item.source} {item.evidence_text}")[:8]:
            candidates.append(("evidence_term", token, {"source": item.source, "evidence_id": item.id}))
    entity_ids = []
    for entity_type, name, metadata in candidates:
        entity = _upsert_entity(db, run.id, entity_type, name, metadata)
        entity_ids.append(entity.id)
    return sorted(set(entity_ids))


def _persist_hypotheses(
    db: Session,
    run: Run,
    hypotheses: list[Hypothesis],
    evidence: list[EvidenceItem],
    posts: list[BoardPost],
    entity_ids: list[str],
) -> list[str]:
    ids = []
    for hypothesis in hypotheses:
        existing = (
            db.query(ScientificHypothesisMemory)
            .filter(ScientificHypothesisMemory.hypothesis_id == hypothesis.id)
            .first()
        )
        if existing:
            ids.append(existing.id)
            continue
        failure_modes = []
        for post in posts:
            critique = post.content_json if post.post_type == "critique" else post.content_json.get("critique", {})
            if isinstance(critique, dict):
                failure_modes.extend(critique.get("risks", []) or critique.get("limitations", []) or [])
        memory = ScientificHypothesisMemory(
            run_id=run.id,
            hypothesis_id=hypothesis.id,
            title=hypothesis.title,
            hypothesis_text=hypothesis.hypothesis_text,
            confidence=hypothesis.confidence,
            status=hypothesis.status,
            entity_ids_json=entity_ids,
            evidence_summary_json={
                "evidence_count": len(evidence),
                "avg_support_score": _avg([item.support_score for item in evidence if item.support_score is not None]),
                "sources": sorted({item.source for item in evidence}),
            },
            failure_modes_json=failure_modes[:12],
        )
        db.add(memory)
        db.flush()
        ids.append(memory.id)
    return ids


def _persist_causal_links(
    db: Session,
    run: Run,
    evidence: list[EvidenceItem],
    entity_ids: list[str],
) -> int:
    if len(entity_ids) < 2:
        return 0
    existing = db.query(ScientificCausalLink).filter(ScientificCausalLink.run_id == run.id).first()
    if existing:
        return 0
    score = _avg([item.support_score for item in evidence if item.support_score is not None])
    link = ScientificCausalLink(
        run_id=run.id,
        source_entity_id=entity_ids[0],
        target_entity_id=entity_ids[1],
        relation="hypothesized_mechanistic_relevance",
        confidence=score,
        evidence_ids_json=[item.id for item in evidence[:10]],
        metadata_json={"source": "autosci_memory_projection"},
    )
    db.add(link)
    return 1


def _persist_experiments(
    db: Session,
    run: Run,
    posts: list[BoardPost],
    hypothesis_memory_ids: list[str],
) -> int:
    if db.query(ExperimentMemory).filter(ExperimentMemory.run_id == run.id).first():
        return 0
    experiments = []
    for post in posts:
        content = post.content_json if isinstance(post.content_json, dict) else {}
        experiments.extend(content.get("next_experiments", []) or [])
    count = 0
    for experiment in experiments:
        if not isinstance(experiment, dict):
            continue
        db.add(
            ExperimentMemory(
                run_id=run.id,
                hypothesis_memory_id=hypothesis_memory_ids[0] if hypothesis_memory_ids else None,
                name=str(experiment.get("name") or "Unnamed experiment")[:255],
                experiment_type=str(experiment.get("type") or "unknown")[:120],
                expected_information_gain=str(experiment.get("expected_information_gain") or "")[:120] or None,
                feasibility=str(experiment.get("feasibility") or "")[:120] or None,
                protocol_json=experiment,
            )
        )
        count += 1
    return count


def _upsert_entity(db: Session, run_id: str, entity_type: str, name: str, metadata: dict[str, Any]) -> ScientificEntity:
    normalized = _normalize(name)
    entity = (
        db.query(ScientificEntity)
        .filter(ScientificEntity.entity_type == entity_type, ScientificEntity.normalized_name == normalized)
        .first()
    )
    if entity is None:
        entity = ScientificEntity(
            entity_type=entity_type,
            name=name[:255],
            normalized_name=normalized[:255],
            aliases_json=[],
            metadata_json=metadata,
            first_seen_run_id=run_id,
            last_seen_run_id=run_id,
            mention_count=1,
        )
        db.add(entity)
        db.flush()
    else:
        entity.last_seen_run_id = run_id
        entity.mention_count += 1
        entity.metadata_json = {**(entity.metadata_json or {}), **metadata}
        entity.updated_at = datetime.utcnow()
    return entity


def _policy_training_metrics(examples: list[WorkflowPolicyExample], model: dict[str, Any]) -> dict[str, Any]:
    if not examples:
        return {"num_examples": 0, "top1_training_accuracy": None}
    correct = 0
    artifact = {
        "action_counts": model["action_counts"],
        "feature_action_counts": model["feature_action_counts"],
        "action_rewards": model.get("action_rewards", {}),
    }
    temp_path = Path("outputs/models/.tmp_policy_eval.json")
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path.write_text(json.dumps(artifact), encoding="utf-8")
    try:
        for example in examples:
            predicted = predict_next_actions(
                {**example.context_json, "state_name": example.state_name},
                model_path=temp_path,
                top_k=1,
            )
            if predicted and predicted[0]["action"] == f"{example.action_type}:{example.action_name}":
                correct += 1
    finally:
        try:
            temp_path.unlink()
        except OSError:
            pass
    return {
        "num_examples": len(examples),
        "top1_training_accuracy": round(correct / len(examples), 4),
    }


def _tokens_for_context(context: dict[str, Any], state_name: str) -> list[str]:
    text = json.dumps(context, default=str).lower() + " " + state_name.lower()
    return sorted(set(TOKEN_RE.findall(text)))[:256]


def _salient_terms(text: str) -> list[str]:
    stop = {
        "the", "and", "for", "with", "using", "this", "that", "from", "into",
        "hypothesis", "evidence", "scientific", "therapeutic", "candidate",
    }
    terms = []
    for token in TOKEN_RE.findall(text):
        if len(token) < 3:
            continue
        if token.lower() in stop:
            continue
        if token[0].isupper() or token.isupper() or any(char.isdigit() for char in token):
            terms.append(token[:80])
    return list(dict.fromkeys(terms))[:32]


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _avg(values: list[float | None]) -> float | None:
    real = [float(value) for value in values if value is not None]
    if not real:
        return None
    return sum(real) / len(real)


def _running_average(current: float, current_count: int, value: float) -> float:
    if current_count <= 0:
        return value
    return ((current * current_count) + value) / (current_count + 1)


def _run_reward(run: Run) -> float:
    confidence = float(run.final_confidence or 0.0)
    status_bonus = 0.5 if run.status == "completed" else -0.5
    return max(-1.0, min(1.0, status_bonus + confidence))

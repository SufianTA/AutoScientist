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
    policy_examples = persist_policy_examples(
        db,
        run,
        objective,
        steps,
        tool_calls,
        reward=_run_reward(run, state),
        scientific_outcome=_scientific_outcome_context(state),
    )

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
    *,
    reward: float | None = None,
    scientific_outcome: dict[str, Any] | None = None,
) -> int:
    if db.query(WorkflowPolicyExample).filter(WorkflowPolicyExample.run_id == run.id).first():
        return 0
    reward = _run_reward(run) if reward is None else reward
    scientific_outcome = scientific_outcome or {}
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
                    "scientific_outcome": scientific_outcome,
                },
                outcome_json={**(step.output_json or {}), "scientific_outcome": scientific_outcome},
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
                    "scientific_outcome": scientific_outcome,
                },
                outcome_json={
                    "status": call.status,
                    "latency_ms": call.latency_ms,
                    "scientific_outcome": scientific_outcome,
                },
                reward=reward if call.status == "success" else min(0.0, reward - 0.25),
            )
        )
        count += 1
    return count


def _scientific_outcome_context(state: Any | None) -> dict[str, Any]:
    if state is None:
        return {}
    context = getattr(state, "context", {}) or {}
    hypothesis_card = getattr(state, "hypothesis_card", {}) or {}
    critic = context.get("biotruth_critic") or hypothesis_card.get("biotruth_critic") or {}
    abstention_policy = context.get("abstention_policy") or hypothesis_card.get("abstention_policy") or {}
    hierarchy = context.get("evidence_hierarchy") or {}
    contradictions = context.get("contradiction_analysis") or {}
    adaptive_plan = context.get("adaptive_tool_plan") or {}
    return {
        "schema": "autosci.scientific_policy_outcome.v0.1",
        "biotruth_verdict": critic.get("verdict") if isinstance(critic, dict) else None,
        "biotruth_weighted_score": critic.get("weighted_score") if isinstance(critic, dict) else None,
        "abstention_decision": abstention_policy.get("decision") if isinstance(abstention_policy, dict) else None,
        "abstention_required": abstention_policy.get("abstention_required") if isinstance(abstention_policy, dict) else None,
        "evidence_hierarchy_score": hierarchy.get("hierarchy_score") if isinstance(hierarchy, dict) else None,
        "high_tier_evidence_count": hierarchy.get("high_tier_evidence_count") if isinstance(hierarchy, dict) else None,
        "contradiction_count": (
            contradictions.get("finding_count", contradictions.get("contradiction_count"))
            if isinstance(contradictions, dict)
            else None
        ),
        "contradiction_search_attempted": contradictions.get("contradiction_search_attempted")
        if isinstance(contradictions, dict)
        else None,
        "adaptive_gaps": adaptive_plan.get("gaps", []) if isinstance(adaptive_plan, dict) else [],
    }


def train_workflow_policy_model(
    db: Session,
    *,
    name: str = "scientific_workflow_policy",
    artifact_dir: str | Path = "outputs/models",
) -> WorkflowPolicyModel:
    _refresh_policy_example_rewards(db)
    examples = db.query(WorkflowPolicyExample).all()
    train_examples, holdout_examples = _split_policy_examples_by_run(examples)
    tool_reliability = _tool_reliability_summary(db.query(ToolBenchmark).all())
    model = _fit_policy_model(
        train_examples if train_examples else examples,
        name=name,
        total_examples=len(examples),
        holdout_examples=len(holdout_examples),
        tool_reliability=tool_reliability,
    )
    artifact_dir = Path(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    version = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    artifact_path = artifact_dir / f"{name}_{version}.json"
    artifact_path.write_text(json.dumps(model, indent=2), encoding="utf-8")
    metrics = _policy_training_metrics(train_examples or examples, holdout_examples, model)
    row = WorkflowPolicyModel(
        name=name,
        version=version,
        artifact_path=str(artifact_path),
        training_summary_json={
            "num_examples": len(examples),
            "training_examples": model["training_examples"],
            "holdout_examples": model["holdout_examples"],
            "num_actions": len(model["action_counts"]),
            "top_actions": Counter(model["action_counts"]).most_common(10),
        },
        metrics_json=metrics,
    )
    db.add(row)
    return row


def _refresh_policy_example_rewards(db: Session) -> None:
    run_rewards = {
        run.id: _run_reward(run)
        for run in db.query(Run).all()
    }
    for example in db.query(WorkflowPolicyExample).all():
        reward = run_rewards.get(example.run_id)
        if reward is not None:
            example.reward = reward


def predict_next_actions(
    context: dict[str, Any],
    *,
    model_path: str | Path,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    model = json.loads(Path(model_path).read_text(encoding="utf-8"))
    return _predict_from_model(model, context, top_k=top_k)


def build_scientific_state_graph(db: Session, *, run_id: str | None = None, limit: int = 500) -> dict[str, Any]:
    """Export memory as an auditable scientific state graph.

    The graph is derived from normalized memory tables instead of being stored as
    a second source of truth. It gives reviewers a compact way to inspect which
    entities, hypotheses, causal links, proposed experiments, tools, and replay
    bundles were produced by the system.
    """

    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    def add_node(node_id: str, kind: str, label: str, **properties: Any) -> None:
        if node_id not in nodes:
            nodes[node_id] = {"id": node_id, "kind": kind, "label": label, "properties": properties}
        else:
            nodes[node_id]["properties"] = {**nodes[node_id].get("properties", {}), **properties}

    def add_edge(source: str, target: str, relation: str, **properties: Any) -> None:
        if source in nodes and target in nodes:
            edges.append({"source": source, "target": target, "relation": relation, "properties": properties})

    run_filter = [ScientificHypothesisMemory.run_id == run_id] if run_id else []
    hypotheses = (
        db.query(ScientificHypothesisMemory)
        .filter(*run_filter)
        .order_by(ScientificHypothesisMemory.created_at.desc())
        .limit(limit)
        .all()
    )
    run_ids = {item.run_id for item in hypotheses}
    if run_id:
        run_ids.add(run_id)

    entities = db.query(ScientificEntity).order_by(ScientificEntity.mention_count.desc()).limit(limit).all()
    for entity in entities:
        add_node(
            entity.id,
            "entity",
            entity.name,
            entity_type=entity.entity_type,
            mention_count=entity.mention_count,
            first_seen_run_id=entity.first_seen_run_id,
            last_seen_run_id=entity.last_seen_run_id,
            metadata=entity.metadata_json,
        )

    for hypothesis in hypotheses:
        add_node(
            hypothesis.id,
            "hypothesis",
            hypothesis.title,
            run_id=hypothesis.run_id,
            confidence=hypothesis.confidence,
            status=hypothesis.status,
            evidence_summary=hypothesis.evidence_summary_json,
            failure_modes=hypothesis.failure_modes_json,
        )
        for entity_id in hypothesis.entity_ids_json or []:
            add_edge(hypothesis.id, str(entity_id), "mentions_entity", confidence=hypothesis.confidence)

    causal_query = db.query(ScientificCausalLink)
    if run_ids:
        causal_query = causal_query.filter(ScientificCausalLink.run_id.in_(run_ids))
    for link in causal_query.order_by(ScientificCausalLink.created_at.desc()).limit(limit).all():
        add_node(
            link.id,
            "causal_link",
            link.relation,
            run_id=link.run_id,
            confidence=link.confidence,
            evidence_ids=link.evidence_ids_json,
            metadata=link.metadata_json,
        )
        if link.source_entity_id:
            add_edge(str(link.source_entity_id), link.id, "supports_relation_source", confidence=link.confidence)
        if link.target_entity_id:
            add_edge(link.id, str(link.target_entity_id), "supports_relation_target", confidence=link.confidence)

    experiment_query = db.query(ExperimentMemory)
    if run_ids:
        experiment_query = experiment_query.filter(ExperimentMemory.run_id.in_(run_ids))
    for experiment in experiment_query.order_by(ExperimentMemory.created_at.desc()).limit(limit).all():
        add_node(
            experiment.id,
            "experiment",
            experiment.name,
            run_id=experiment.run_id,
            experiment_type=experiment.experiment_type,
            expected_information_gain=experiment.expected_information_gain,
            feasibility=experiment.feasibility,
            status=experiment.status,
            protocol=experiment.protocol_json,
            result=experiment.result_json,
        )
        if experiment.hypothesis_memory_id:
            add_edge(str(experiment.hypothesis_memory_id), experiment.id, "proposes_experiment")

    replay_query = db.query(RunReplay)
    if run_ids:
        replay_query = replay_query.filter(RunReplay.run_id.in_(run_ids))
    for replay in replay_query.order_by(RunReplay.created_at.desc()).limit(limit).all():
        node_id = f"run:{replay.run_id}"
        add_node(node_id, "run", replay.run_id, replay_hash=replay.replay_hash, created_at=replay.created_at.isoformat())
        add_node(replay.id, "replay", replay.replay_hash[:12], run_id=replay.run_id, replay_hash=replay.replay_hash)
        add_edge(node_id, replay.id, "has_replay")
        for hypothesis in hypotheses:
            if hypothesis.run_id == replay.run_id:
                add_edge(node_id, hypothesis.id, "produced_hypothesis")

    tool_query = db.query(ToolBenchmark)
    for benchmark in tool_query.order_by(ToolBenchmark.call_count.desc()).limit(limit).all():
        node_id = f"tool:{benchmark.tool_source}:{benchmark.tool_name}"
        add_node(
            node_id,
            "tool",
            benchmark.tool_name,
            source=benchmark.tool_source,
            call_count=benchmark.call_count,
            success_rate=benchmark.success_count / benchmark.call_count if benchmark.call_count else None,
            avg_latency_ms=benchmark.avg_latency_ms,
            avg_usefulness=benchmark.avg_usefulness,
            last_run_id=benchmark.last_run_id,
        )
        if benchmark.last_run_id:
            add_node(f"run:{benchmark.last_run_id}", "run", benchmark.last_run_id)
            add_edge(f"run:{benchmark.last_run_id}", node_id, "used_tool")

    _add_confidence_evolution_edges(nodes, edges, hypotheses)
    if run_id:
        connected = {edge["source"] for edge in edges} | {edge["target"] for edge in edges}
        nodes = {
            node_id: node
            for node_id, node in nodes.items()
            if node["kind"] != "entity" or node_id in connected
        }
        edges = [edge for edge in edges if edge["source"] in nodes and edge["target"] in nodes]
    return {
        "schema": "autosci.scientific_state_graph.v1",
        "scope": {"run_id": run_id, "limit": limit},
        "summary": {
            "nodes": len(nodes),
            "edges": len(edges),
            "hypotheses": sum(1 for node in nodes.values() if node["kind"] == "hypothesis"),
            "entities": sum(1 for node in nodes.values() if node["kind"] == "entity"),
            "experiments": sum(1 for node in nodes.values() if node["kind"] == "experiment"),
            "tools": sum(1 for node in nodes.values() if node["kind"] == "tool"),
        },
        "nodes": list(nodes.values()),
        "edges": edges,
    }


def _fit_policy_model(
    examples: list[WorkflowPolicyExample],
    *,
    name: str,
    total_examples: int,
    holdout_examples: int,
    tool_reliability: dict[str, Any],
) -> dict[str, Any]:
    action_counts: Counter[str] = Counter()
    state_action_counts: dict[str, Counter[str]] = defaultdict(Counter)
    feature_action_counts: dict[str, Counter[str]] = defaultdict(Counter)
    rewards: dict[str, list[float]] = defaultdict(list)
    transition_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for example in examples:
        action = f"{example.action_type}:{example.action_name}"
        action_counts[action] += 1
        state_action_counts[example.state_name][action] += 1
        rewards[action].append(float(example.reward or 0.0))
        previous_state = str(example.context_json.get("previous_state") or example.state_name)
        transition_counts[previous_state][action] += 1
        for token in _tokens_for_context(example.context_json, example.state_name):
            feature_action_counts[token][action] += 1

    return {
        "schema": "autosci.scientific_workflow_policy.v2",
        "name": name,
        "trained_at": datetime.utcnow().isoformat(),
        "num_examples": total_examples,
        "training_examples": len(examples),
        "holdout_examples": holdout_examples,
        "action_counts": dict(action_counts),
        "state_action_counts": {state: dict(counts) for state, counts in state_action_counts.items()},
        "feature_action_counts": {feature: dict(counts) for feature, counts in feature_action_counts.items()},
        "transition_counts": {state: dict(counts) for state, counts in transition_counts.items()},
        "action_rewards": {
            action: sum(values) / len(values)
            for action, values in rewards.items()
            if values
        },
        "tool_reliability": tool_reliability,
        "scoring": {
            "prior_weight": 1.0,
            "state_weight": 1.4,
            "feature_weight": 1.0,
            "reward_weight": 2.0,
            "tool_reliability_weight": 1.2,
        },
    }


def _predict_from_model(model: dict[str, Any], context: dict[str, Any], *, top_k: int = 5) -> list[dict[str, Any]]:
    action_counts = Counter(model.get("action_counts", {}))
    feature_action_counts = {
        feature: Counter(counts)
        for feature, counts in model.get("feature_action_counts", {}).items()
    }
    state_action_counts = {
        state: Counter(counts)
        for state, counts in model.get("state_action_counts", {}).items()
    }
    action_rewards = model.get("action_rewards", {})
    tool_reliability = model.get("tool_reliability", {})
    weights = {
        "prior_weight": 1.0,
        "state_weight": 1.4,
        "feature_weight": 1.0,
        "reward_weight": 2.0,
        "tool_reliability_weight": 1.2,
        **(model.get("scoring") or {}),
    }
    scores: Counter[str] = Counter()
    total_actions = sum(action_counts.values()) or 1
    num_actions = max(len(action_counts), 1)
    for action, count in action_counts.items():
        scores[action] += weights["prior_weight"] * math.log((count + 1) / (total_actions + num_actions))
        scores[action] += weights["reward_weight"] * float(action_rewards.get(action, 0.0))
        if action.startswith("tool_call:"):
            tool_name = action.split(":", 1)[1]
            reliability = tool_reliability.get(tool_name, {})
            success_rate = reliability.get("success_rate")
            usefulness = reliability.get("avg_usefulness")
            if success_rate is not None:
                scores[action] += weights["tool_reliability_weight"] * float(success_rate)
            if usefulness is not None:
                scores[action] += 0.5 * weights["tool_reliability_weight"] * float(usefulness)
    state_name = str(context.get("state_name", ""))
    for action, count in state_action_counts.get(state_name, {}).items():
        scores[action] += weights["state_weight"] * math.log(1 + count)
    for token in _tokens_for_context(context, state_name):
        for action, count in feature_action_counts.get(token, {}).items():
            scores[action] += weights["feature_weight"] * math.log(1 + count)
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


def _split_policy_examples_by_run(
    examples: list[WorkflowPolicyExample],
) -> tuple[list[WorkflowPolicyExample], list[WorkflowPolicyExample]]:
    if not examples:
        return [], []
    by_run: dict[str, list[WorkflowPolicyExample]] = defaultdict(list)
    for example in examples:
        by_run[example.run_id].append(example)
    if len(by_run) < 4:
        return examples, []
    ordered_runs = sorted(
        by_run,
        key=lambda run_id: (
            min(example.created_at for example in by_run[run_id]),
            run_id,
        ),
    )
    holdout_run_count = max(1, round(len(ordered_runs) * 0.2))
    holdout_runs = set(ordered_runs[-holdout_run_count:])
    train = [example for example in examples if example.run_id not in holdout_runs]
    holdout = [example for example in examples if example.run_id in holdout_runs]
    return train, holdout


def _tool_reliability_summary(benchmarks: list[ToolBenchmark]) -> dict[str, Any]:
    summary = {}
    for benchmark in benchmarks:
        success_rate = benchmark.success_count / benchmark.call_count if benchmark.call_count else None
        summary[benchmark.tool_name] = {
            "tool_source": benchmark.tool_source,
            "call_count": benchmark.call_count,
            "success_rate": success_rate,
            "avg_latency_ms": benchmark.avg_latency_ms,
            "avg_usefulness": benchmark.avg_usefulness,
        }
    return summary


def _policy_training_metrics(
    train_examples: list[WorkflowPolicyExample],
    holdout_examples: list[WorkflowPolicyExample],
    model: dict[str, Any],
) -> dict[str, Any]:
    train_metrics = _policy_eval_metrics(train_examples, model)
    holdout_metrics = _policy_eval_metrics(holdout_examples, model)
    return {
        "num_examples": int(model.get("num_examples") or len(train_examples) + len(holdout_examples)),
        "training_examples": len(train_examples),
        "holdout_examples": len(holdout_examples),
        "top1_training_accuracy": train_metrics["top1_accuracy"],
        "top3_training_accuracy": train_metrics["top3_accuracy"],
        "mrr_training": train_metrics["mrr"],
        "top1_holdout_accuracy": holdout_metrics["top1_accuracy"],
        "top3_holdout_accuracy": holdout_metrics["top3_accuracy"],
        "mrr_holdout": holdout_metrics["mrr"],
    }


def _policy_eval_metrics(examples: list[WorkflowPolicyExample], model: dict[str, Any]) -> dict[str, Any]:
    if not examples:
        return {"top1_accuracy": None, "top3_accuracy": None, "mrr": None}
    top1 = 0
    top3 = 0
    reciprocal_rank = 0.0
    for example in examples:
        expected = f"{example.action_type}:{example.action_name}"
        predicted = _predict_from_model(
            model,
            {**example.context_json, "state_name": example.state_name},
            top_k=10,
        )
        actions = [item["action"] for item in predicted]
        if actions[:1] == [expected]:
            top1 += 1
        if expected in actions[:3]:
            top3 += 1
        if expected in actions:
            reciprocal_rank += 1.0 / (actions.index(expected) + 1)
    total = len(examples)
    return {
        "top1_accuracy": round(top1 / total, 4),
        "top3_accuracy": round(top3 / total, 4),
        "mrr": round(reciprocal_rank / total, 4),
    }


def _add_confidence_evolution_edges(
    nodes: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
    hypotheses: list[ScientificHypothesisMemory],
) -> None:
    by_signature: dict[str, list[ScientificHypothesisMemory]] = defaultdict(list)
    for hypothesis in hypotheses:
        signature = _normalize(" ".join([hypothesis.title, *map(str, hypothesis.entity_ids_json or [])]))[:240]
        by_signature[signature].append(hypothesis)
    for related in by_signature.values():
        ordered = sorted(related, key=lambda item: item.created_at)
        for previous, current in zip(ordered, ordered[1:]):
            if previous.id in nodes and current.id in nodes:
                edges.append(
                    {
                        "source": previous.id,
                        "target": current.id,
                        "relation": "confidence_evolved_to",
                        "properties": {
                            "previous_confidence": previous.confidence,
                            "current_confidence": current.confidence,
                            "delta": (
                                round(float(current.confidence - previous.confidence), 4)
                                if current.confidence is not None and previous.confidence is not None
                                else None
                            ),
                        },
                    }
                )


def _tokens_for_context(context: dict[str, Any], state_name: str) -> list[str]:
    text = json.dumps(context, default=str).lower() + " " + state_name.lower()
    tokens = set(TOKEN_RE.findall(text))
    outcome = context.get("scientific_outcome") if isinstance(context.get("scientific_outcome"), dict) else {}
    for key in (
        "biotruth_verdict",
        "abstention_decision",
        "abstention_required",
        "contradiction_search_attempted",
    ):
        value = outcome.get(key)
        if value is not None:
            tokens.add(f"outcome_{key}_{str(value).lower()}")
    for gap in outcome.get("adaptive_gaps", []) if isinstance(outcome.get("adaptive_gaps"), list) else []:
        tokens.add(f"adaptive_gap_{str(gap).lower()}")
    high_tier_count = outcome.get("high_tier_evidence_count")
    if isinstance(high_tier_count, (int, float)):
        tokens.add("high_tier_present" if high_tier_count > 0 else "high_tier_absent")
    return sorted(tokens)[:256]


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


def _run_reward(run: Run, state: Any | None = None) -> float:
    state_confidence = None
    if state is not None:
        state_confidence = getattr(state, "report", {}).get("confidence")
    confidence = float(state_confidence if state_confidence is not None else (run.final_confidence or 0.0))
    status = "completed" if state is not None and getattr(state, "report", None) else run.status
    status_bonus = 0.5 if status == "completed" else -0.5
    return max(-1.0, min(1.0, status_bonus + confidence))

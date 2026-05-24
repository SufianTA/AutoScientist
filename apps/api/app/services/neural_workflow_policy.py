from __future__ import annotations

import json
import math
import random
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import ToolBenchmark, WorkflowPolicyExample, WorkflowPolicyModel


TOKEN_RE = re.compile(r"[A-Za-z0-9_+.-]{2,}")
MODEL_TYPE = "neural_scientific_workflow_policy"
SCHEMA = "autosci.neural_workflow_policy.v1"


def train_neural_workflow_policy_model(
    db: Session,
    *,
    name: str = "neural_scientific_workflow_policy",
    artifact_dir: str | Path = "outputs/models",
    epochs: int = 80,
    hidden_dim: int = 128,
    lr: float = 0.002,
    batch_size: int = 64,
    vocab_size: int = 2048,
    seed: int = 13,
) -> WorkflowPolicyModel:
    torch = _require_torch()
    _seed_everything(torch, seed)
    examples = (
        db.query(WorkflowPolicyExample)
        .order_by(WorkflowPolicyExample.created_at.asc(), WorkflowPolicyExample.run_id.asc(), WorkflowPolicyExample.step_index.asc())
        .all()
    )
    if len(examples) < 8:
        raise RuntimeError("Need at least 8 workflow policy examples to train a neural policy model.")

    train_examples, holdout_examples = _split_by_run(examples)
    if not train_examples:
        train_examples = examples
        holdout_examples = []
    action_index = _action_index(examples)
    vocab = _build_vocab(train_examples, max_size=vocab_size)
    x_train, y_train, w_train = _tensorize(torch, train_examples, vocab, action_index)
    x_holdout, y_holdout, _ = _tensorize(torch, holdout_examples, vocab, action_index) if holdout_examples else (None, None, None)

    model = _WorkflowPolicyNet(input_dim=len(vocab), hidden_dim=hidden_dim, output_dim=len(action_index))
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    batch_size = max(1, min(batch_size, len(train_examples)))
    losses: list[float] = []
    for _ in range(max(1, epochs)):
        model.train()
        order = torch.randperm(x_train.shape[0])
        epoch_loss = 0.0
        for start in range(0, x_train.shape[0], batch_size):
            idx = order[start : start + batch_size]
            logits = model(x_train[idx])
            loss_by_example = torch.nn.functional.cross_entropy(logits, y_train[idx], reduction="none")
            loss = (loss_by_example * w_train[idx]).mean()
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            epoch_loss += float(loss.detach().cpu())
        losses.append(round(epoch_loss / max(1, math.ceil(x_train.shape[0] / batch_size)), 6))

    model.eval()
    train_metrics = _evaluate(torch, model, x_train, y_train)
    holdout_metrics = _evaluate(torch, model, x_holdout, y_holdout) if x_holdout is not None else _empty_metrics()
    majority_metrics = _majority_baseline_metrics(train_examples, holdout_examples, action_index)
    action_counts = Counter(_action(example) for example in examples)
    action_rewards = _action_rewards(examples)
    tool_reliability = _tool_reliability_summary(db.query(ToolBenchmark).all())
    version = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    model_dir = Path(artifact_dir) / f"{name}_{version}"
    model_dir.mkdir(parents=True, exist_ok=True)
    weights_path = model_dir / "model.pt"
    torch.save(model.state_dict(), weights_path)
    manifest = {
        "schema": SCHEMA,
        "name": name,
        "version": version,
        "model_type": MODEL_TYPE,
        "created_at": datetime.utcnow().isoformat(),
        "framework": {"name": "pytorch", "version": torch.__version__},
        "architecture": {
            "input": "bag_of_context_tokens",
            "hidden_dim": hidden_dim,
            "output": "workflow_action_softmax",
            "vocab_size": len(vocab),
            "num_actions": len(action_index),
        },
        "files": {"weights": "model.pt"},
        "vocab": vocab,
        "action_index": action_index,
        "action_counts": dict(action_counts),
        "action_rewards": action_rewards,
        "tool_reliability": tool_reliability,
        "training": {
            "num_examples": len(examples),
            "training_examples": len(train_examples),
            "holdout_examples": len(holdout_examples),
            "epochs": epochs,
            "batch_size": batch_size,
            "learning_rate": lr,
            "seed": seed,
            "loss_curve": losses,
        },
        "metrics": {
            "num_examples": len(examples),
            "training_examples": len(train_examples),
            "holdout_examples": len(holdout_examples),
            "top1_training_accuracy": train_metrics["top1_accuracy"],
            "top3_training_accuracy": train_metrics["top3_accuracy"],
            "mrr_training": train_metrics["mrr"],
            "top1_holdout_accuracy": holdout_metrics["top1_accuracy"],
            "top3_holdout_accuracy": holdout_metrics["top3_accuracy"],
            "mrr_holdout": holdout_metrics["mrr"],
            "majority_top1_holdout_accuracy": majority_metrics["top1_accuracy"],
            "majority_top3_holdout_accuracy": majority_metrics["top3_accuracy"],
            "majority_mrr_holdout": majority_metrics["mrr"],
        },
        "sample_predictions": _sample_predictions(torch, model, examples, vocab, action_index, action_counts, action_rewards),
    }
    manifest_path = model_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    (model_dir / "MODEL_CARD.md").write_text(_render_model_card(manifest), encoding="utf-8")
    (model_dir / "README.md").write_text(_render_readme(manifest), encoding="utf-8")

    row = WorkflowPolicyModel(
        name=name,
        version=version,
        model_type=MODEL_TYPE,
        artifact_path=str(manifest_path),
        training_summary_json={
            "num_examples": len(examples),
            "training_examples": len(train_examples),
            "holdout_examples": len(holdout_examples),
            "num_actions": len(action_index),
            "top_actions": action_counts.most_common(10),
            "framework": "pytorch",
            "architecture": manifest["architecture"],
        },
        metrics_json=manifest["metrics"],
    )
    db.add(row)
    return row


def predict_neural_workflow_policy(
    context: dict[str, Any],
    *,
    model_path: str | Path,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    torch = _require_torch()
    manifest_path = Path(model_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    model = _load_model(torch, manifest, manifest_path.parent)
    vocab = {str(key): int(value) for key, value in manifest["vocab"].items()}
    action_index = {str(key): int(value) for key, value in manifest["action_index"].items()}
    index_action = {index: action for action, index in action_index.items()}
    features = _encode_context(torch, context, vocab).unsqueeze(0)
    with torch.no_grad():
        probabilities = torch.softmax(model(features), dim=1)[0]
    k = max(1, min(top_k, len(index_action)))
    values, indices = torch.topk(probabilities, k=k)
    action_counts = manifest.get("action_counts", {})
    action_rewards = manifest.get("action_rewards", {})
    predictions = []
    for value, index in zip(values.tolist(), indices.tolist()):
        action = index_action[int(index)]
        predictions.append(
            {
                "action": action,
                "score": round(float(value), 6),
                "probability": round(float(value), 6),
                "mean_reward": round(float(action_rewards.get(action, 0.0)), 4),
                "support": int(action_counts.get(action, 0)),
            }
        )
    return predictions


def is_neural_policy_artifact(model_path: str | Path) -> bool:
    try:
        data = json.loads(Path(model_path).read_text(encoding="utf-8"))
    except Exception:
        return False
    return data.get("schema") == SCHEMA


def _require_torch() -> Any:
    try:
        import torch
    except Exception as exc:  # pragma: no cover - depends on optional install.
        raise RuntimeError(
            "PyTorch is required for the neural workflow policy. Install with "
            "`python -m pip install -e .[neural]` or use the RunPod PyTorch image."
        ) from exc
    return torch


def _seed_everything(torch: Any, seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)
    if hasattr(torch, "cuda") and torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


class _WorkflowPolicyNet:
    def __new__(cls, input_dim: int, hidden_dim: int, output_dim: int) -> Any:
        torch = _require_torch()

        class Net(torch.nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.layers = torch.nn.Sequential(
                    torch.nn.Linear(input_dim, hidden_dim),
                    torch.nn.LayerNorm(hidden_dim),
                    torch.nn.GELU(),
                    torch.nn.Dropout(0.1),
                    torch.nn.Linear(hidden_dim, output_dim),
                )

            def forward(self, x: Any) -> Any:
                return self.layers(x)

        return Net()


def _load_model(torch: Any, manifest: dict[str, Any], model_dir: Path) -> Any:
    arch = manifest["architecture"]
    model = _WorkflowPolicyNet(
        input_dim=int(arch["vocab_size"]),
        hidden_dim=int(arch["hidden_dim"]),
        output_dim=int(arch["num_actions"]),
    )
    weights = model_dir / manifest.get("files", {}).get("weights", "model.pt")
    try:
        state_dict = torch.load(weights, map_location="cpu", weights_only=True)
    except TypeError:
        state_dict = torch.load(weights, map_location="cpu")
    model.load_state_dict(state_dict)
    model.eval()
    return model


def _split_by_run(
    examples: list[WorkflowPolicyExample],
) -> tuple[list[WorkflowPolicyExample], list[WorkflowPolicyExample]]:
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
    holdout_count = max(1, round(len(ordered_runs) * 0.2))
    holdout_runs = set(ordered_runs[-holdout_count:])
    train = [example for example in examples if example.run_id not in holdout_runs]
    holdout = [example for example in examples if example.run_id in holdout_runs]
    return train, holdout


def _action(example: WorkflowPolicyExample) -> str:
    return f"{example.action_type}:{example.action_name}"


def _action_index(examples: list[WorkflowPolicyExample]) -> dict[str, int]:
    actions = sorted({_action(example) for example in examples})
    return {action: index for index, action in enumerate(actions)}


def _build_vocab(examples: list[WorkflowPolicyExample], *, max_size: int) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for example in examples:
        counts.update(_tokens_for_example(example))
    tokens = [token for token, _ in counts.most_common(max(1, max_size))]
    if not tokens:
        tokens = ["__empty_context__"]
    return {token: index for index, token in enumerate(tokens)}


def _tokens_for_example(example: WorkflowPolicyExample) -> list[str]:
    return _tokens_for_context({**example.context_json, "state_name": example.state_name})


def _tokens_for_context(context: dict[str, Any]) -> list[str]:
    raw = json.dumps(context, sort_keys=True, default=str).lower()
    tokens = set(TOKEN_RE.findall(raw))
    state = context.get("state_name")
    if state:
        tokens.add(f"state={str(state).lower()}")
    previous = context.get("previous_state")
    if previous:
        tokens.add(f"previous={str(previous).lower()}")
    tool_source = context.get("tool_source")
    if tool_source:
        tokens.add(f"tool_source={str(tool_source).lower()}")
    outcome = context.get("scientific_outcome") if isinstance(context.get("scientific_outcome"), dict) else {}
    for key in (
        "biotruth_verdict",
        "abstention_decision",
        "abstention_required",
        "contradiction_search_attempted",
    ):
        value = outcome.get(key)
        if value is not None:
            tokens.add(f"outcome_{key}={str(value).lower()}")
    for gap in outcome.get("adaptive_gaps", []) if isinstance(outcome.get("adaptive_gaps"), list) else []:
        tokens.add(f"adaptive_gap={str(gap).lower()}")
    high_tier_count = outcome.get("high_tier_evidence_count")
    if isinstance(high_tier_count, (int, float)):
        tokens.add("high_tier_present" if high_tier_count > 0 else "high_tier_absent")
    run_config = context.get("run_config") if isinstance(context.get("run_config"), dict) else {}
    provider = run_config.get("llm_provider")
    if provider:
        tokens.add(f"provider={str(provider).lower()}")
    return sorted(tokens)


def _tensorize(
    torch: Any,
    examples: list[WorkflowPolicyExample],
    vocab: dict[str, int],
    action_index: dict[str, int],
) -> tuple[Any, Any, Any]:
    x = torch.stack([_encode_context(torch, {**example.context_json, "state_name": example.state_name}, vocab) for example in examples])
    y = torch.tensor([action_index[_action(example)] for example in examples], dtype=torch.long)
    weights = torch.tensor([_sample_weight(example) for example in examples], dtype=torch.float32)
    return x, y, weights


def _encode_context(torch: Any, context: dict[str, Any], vocab: dict[str, int]) -> Any:
    vector = torch.zeros(len(vocab), dtype=torch.float32)
    for token in _tokens_for_context(context):
        index = vocab.get(token)
        if index is not None:
            vector[index] += 1.0
    if vector.sum() > 0:
        vector = vector / torch.clamp(vector.norm(p=2), min=1.0)
    return vector


def _sample_weight(example: WorkflowPolicyExample) -> float:
    reward = float(example.reward or 0.0)
    return max(0.25, 1.0 + reward)


def _evaluate(torch: Any, model: Any, x: Any, y: Any) -> dict[str, float | None]:
    if x is None or y is None or len(y) == 0:
        return _empty_metrics()
    with torch.no_grad():
        logits = model(x)
        topk = torch.topk(logits, k=min(3, logits.shape[1]), dim=1).indices
    top1 = (topk[:, 0] == y).float().mean().item()
    top3 = (topk == y.unsqueeze(1)).any(dim=1).float().mean().item()
    reciprocal = 0.0
    full_rank = torch.argsort(logits, dim=1, descending=True)
    for expected, ranked in zip(y.tolist(), full_rank.tolist()):
        reciprocal += 1.0 / (ranked.index(expected) + 1)
    return {
        "top1_accuracy": round(float(top1), 4),
        "top3_accuracy": round(float(top3), 4),
        "mrr": round(reciprocal / len(y), 4),
    }


def _empty_metrics() -> dict[str, None]:
    return {"top1_accuracy": None, "top3_accuracy": None, "mrr": None}


def _majority_baseline_metrics(
    train_examples: list[WorkflowPolicyExample],
    holdout_examples: list[WorkflowPolicyExample],
    action_index: dict[str, int],
) -> dict[str, float | None]:
    if not holdout_examples:
        return _empty_metrics()
    counts = Counter(_action(example) for example in train_examples)
    ranked_actions = [action for action, _ in counts.most_common()] or list(action_index)
    top1 = 0
    top3 = 0
    rr = 0.0
    for example in holdout_examples:
        expected = _action(example)
        if ranked_actions[:1] == [expected]:
            top1 += 1
        if expected in ranked_actions[:3]:
            top3 += 1
        if expected in ranked_actions:
            rr += 1.0 / (ranked_actions.index(expected) + 1)
    total = len(holdout_examples)
    return {
        "top1_accuracy": round(top1 / total, 4),
        "top3_accuracy": round(top3 / total, 4),
        "mrr": round(rr / total, 4),
    }


def _action_rewards(examples: list[WorkflowPolicyExample]) -> dict[str, float]:
    rewards: dict[str, list[float]] = defaultdict(list)
    for example in examples:
        rewards[_action(example)].append(float(example.reward or 0.0))
    return {action: sum(values) / len(values) for action, values in rewards.items() if values}


def _tool_reliability_summary(benchmarks: list[ToolBenchmark]) -> dict[str, Any]:
    summary = {}
    for benchmark in benchmarks:
        summary[benchmark.tool_name] = {
            "tool_source": benchmark.tool_source,
            "call_count": benchmark.call_count,
            "success_rate": benchmark.success_count / benchmark.call_count if benchmark.call_count else None,
            "avg_latency_ms": benchmark.avg_latency_ms,
            "avg_usefulness": benchmark.avg_usefulness,
        }
    return summary


def _sample_predictions(
    torch: Any,
    model: Any,
    examples: list[WorkflowPolicyExample],
    vocab: dict[str, int],
    action_index: dict[str, int],
    action_counts: Counter[str],
    action_rewards: dict[str, float],
) -> list[dict[str, Any]]:
    predictions = []
    seen: set[str] = set()
    for example in examples:
        key = example.state_name
        if key in seen:
            continue
        seen.add(key)
        context = {**example.context_json, "state_name": example.state_name}
        x = _encode_context(torch, context, vocab).unsqueeze(0)
        with torch.no_grad():
            probabilities = torch.softmax(model(x), dim=1)[0]
        index_action = {index: action for action, index in action_index.items()}
        values, indices = torch.topk(probabilities, k=min(3, len(index_action)))
        predictions.append(
            {
                "context": {
                    "state_name": example.state_name,
                    "objective_preview": str(example.context_json.get("objective", ""))[:160],
                },
                "expected_action": _action(example),
                "predictions": [
                    {
                        "action": index_action[int(index)],
                        "probability": round(float(value), 6),
                        "support": int(action_counts.get(index_action[int(index)], 0)),
                        "mean_reward": round(float(action_rewards.get(index_action[int(index)], 0.0)), 4),
                    }
                    for value, index in zip(values.tolist(), indices.tolist())
                ],
            }
        )
        if len(predictions) >= 8:
            break
    return predictions


def _render_model_card(manifest: dict[str, Any]) -> str:
    metrics = manifest["metrics"]
    training = manifest["training"]
    architecture = manifest["architecture"]
    return "\n".join(
        [
            "# AutoScientist Neural Scientific Workflow Policy",
            "",
            "## Intended Use",
            "",
            "This PyTorch model ranks the next AutoScientist workflow action from scientific run context. "
            "It is an orchestration model, not a biomedical fact model or clinical model.",
            "",
            "## Open-Source Stack",
            "",
            f"- Framework: `PyTorch {manifest['framework']['version']}`",
            "- Inputs: bag-of-token representation of objective, state, run config, and tool context.",
            "- Output: softmax distribution over workflow actions.",
            "",
            "## Architecture",
            "",
            f"- Vocabulary size: `{architecture['vocab_size']}`",
            f"- Hidden dimension: `{architecture['hidden_dim']}`",
            f"- Actions: `{architecture['num_actions']}`",
            "",
            "## Training Data",
            "",
            f"- Examples: `{training['num_examples']}`",
            f"- Training examples: `{training['training_examples']}`",
            f"- Holdout examples: `{training['holdout_examples']}`",
            "- Source: AutoScientist workflow traces, tool calls, rewards, replay bundles, and memory graph.",
            "",
            "## Metrics",
            "",
            f"- Top-1 training accuracy: `{metrics['top1_training_accuracy']}`",
            f"- Top-3 training accuracy: `{metrics['top3_training_accuracy']}`",
            f"- Training MRR: `{metrics['mrr_training']}`",
            f"- Top-1 holdout accuracy: `{metrics['top1_holdout_accuracy']}`",
            f"- Top-3 holdout accuracy: `{metrics['top3_holdout_accuracy']}`",
            f"- Holdout MRR: `{metrics['mrr_holdout']}`",
            f"- Majority baseline top-3 holdout accuracy: `{metrics['majority_top3_holdout_accuracy']}`",
            "",
            "## Limitations",
            "",
            "- Current dataset is still small; the model should be retrained after larger real biomedical benchmark runs.",
            "- It predicts workflow actions, not scientific truth.",
            "- Use replay/state-graph audits before making claims about discovery value.",
        ]
    )


def _render_readme(manifest: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Neural Workflow Policy Artifact",
            "",
            "Files:",
            "",
            "- `manifest.json`: schema, vocab, action index, metrics, and sample predictions.",
            "- `model.pt`: PyTorch state dict.",
            "- `MODEL_CARD.md`: intended use, metrics, and limitations.",
            "",
            "Predict from AutoScientist:",
            "",
            "```bash",
            "curl -X POST http://127.0.0.1:8000/memory/policy/predict \\",
            "  -H 'Content-Type: application/json' \\",
            "  -d '{\"model_id\":\"MODEL_ID\",\"context\":{\"objective\":\"RA target prioritization\",\"state_name\":\"TOOL_SELECTION\"},\"top_k\":5}'",
            "```",
            "",
            f"Model version: `{manifest['version']}`",
        ]
    )

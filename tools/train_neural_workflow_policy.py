from __future__ import annotations

import argparse
import json
import sys

from app.db.session import SessionLocal
from app.services.neural_workflow_policy import train_neural_workflow_policy_model


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the PyTorch neural AutoScientist workflow policy.")
    parser.add_argument("--name", default="neural_scientific_workflow_policy")
    parser.add_argument("--artifact-dir", default="outputs/models")
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--hidden-dim", type=int, default=128)
    parser.add_argument("--learning-rate", type=float, default=0.002)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--vocab-size", type=int, default=2048)
    parser.add_argument("--seed", type=int, default=13)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    db = SessionLocal()
    try:
        model = train_neural_workflow_policy_model(
            db,
            name=args.name,
            artifact_dir=args.artifact_dir,
            epochs=args.epochs,
            hidden_dim=args.hidden_dim,
            lr=args.learning_rate,
            batch_size=args.batch_size,
            vocab_size=args.vocab_size,
            seed=args.seed,
        )
        db.commit()
        db.refresh(model)
        print(
            json.dumps(
                {
                    "id": model.id,
                    "name": model.name,
                    "version": model.version,
                    "model_type": model.model_type,
                    "artifact_path": model.artifact_path,
                    "training_summary": model.training_summary_json,
                    "metrics": model.metrics_json,
                },
                indent=2,
            )
        )
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json

from app.db.models import Objective
from app.db.session import SessionLocal, init_db
from app.services.run_executor import create_run_record, execute_run, normalize_run_config


def run_question(question: str, config: dict | None = None) -> dict:
    init_db()
    db = SessionLocal()
    try:
        objective = Objective(
            title=question[:120],
            objective_text=question,
            constraints_json={"local_runner": True, "require_critic": True},
        )
        db.add(objective)
        db.commit()
        db.refresh(objective)
        run_config = normalize_run_config({"execution_mode": "inline", **(config or {})})
        run = create_run_record(db, objective, run_config)
        run.payment_status = "not_required"
        db.commit()
        run = execute_run(db, run, objective)
        return {
            "run_id": run.id,
            "status": run.status,
            "final_confidence": run.final_confidence,
            "report_url": f"/reports/{run.id}",
            "trace_url": f"/runs/{run.id}/trace",
        }
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a local BioAutoScientist question.")
    parser.add_argument("question", help="Scientific question or objective")
    parser.add_argument("--agents", type=int, default=6)
    parser.add_argument("--runtime", type=int, default=30)
    parser.add_argument("--strictness", choices=["exploratory", "balanced", "strict"], default="balanced")
    parser.add_argument("--llm-provider", default="mock")
    parser.add_argument("--llm-model", default="mock-scientist")
    parser.add_argument("--model-tool", action="append", default=[], help="Registered custom model tool name")
    args = parser.parse_args()
    result = run_question(
        args.question,
        {
            "agent_count": args.agents,
            "max_runtime_minutes": args.runtime,
            "evidence_strictness": args.strictness,
            "llm_provider": args.llm_provider,
            "llm_model": args.llm_model,
            "model_tool_names": args.model_tool,
        },
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

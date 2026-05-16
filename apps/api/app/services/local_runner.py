from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.db.models import AgentStep, Objective, ToolCall
from app.db.session import SessionLocal, init_db
from app.routes.reports import build_report, render_markdown_report
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
        report = build_report(run.id, db)
        step_count = db.query(AgentStep).filter(AgentStep.run_id == run.id).count()
        tool_call_count = db.query(ToolCall).filter(ToolCall.run_id == run.id).count()
        return {
            "run_id": run.id,
            "status": run.status,
            "final_confidence": run.final_confidence,
            "report_url": f"/reports/{run.id}",
            "trace_url": f"/runs/{run.id}/trace",
            "trace_summary": {
                "agent_steps": step_count,
                "tool_calls": tool_call_count,
            },
            "report": report,
        }
    finally:
        db.close()


def format_result(result: dict, output_format: str) -> str:
    if output_format == "json":
        return json.dumps(result, indent=2)
    if output_format == "markdown":
        return render_markdown_report(result["report"])
    report = result["report"]
    hypothesis = report["hypothesis"]
    lines = [
        f"Run: {result['run_id']}",
        f"Status: {result['status']}",
        f"Final confidence: {result['final_confidence']}",
        f"Agent steps: {result['trace_summary']['agent_steps']}",
        f"Tool calls: {result['trace_summary']['tool_calls']}",
        "",
        f"Hypothesis: {hypothesis['title']}",
        hypothesis["text"],
        "",
        "Evidence:",
    ]
    for item in report["evidence"]:
        lines.append(f"- {item['source']}: {item['support_label']} ({item['support_score']})")
    lines.extend(["", "Guardrails:"])
    for guardrail in report["guardrails"]:
        lines.append(f"- {guardrail}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a local BioAutoScientist question.")
    parser.add_argument("question", help="Scientific question or objective")
    parser.add_argument("--agents", type=int, default=6)
    parser.add_argument("--runtime", type=int, default=30)
    parser.add_argument("--strictness", choices=["exploratory", "balanced", "strict"], default="balanced")
    parser.add_argument("--llm-provider", default="mock")
    parser.add_argument("--llm-model", default="mock-scientist")
    parser.add_argument("--model-tool", action="append", default=[], help="Registered custom model tool name")
    parser.add_argument(
        "--output-format",
        choices=["summary", "json", "markdown"],
        default="summary",
        help="Command-line output format",
    )
    parser.add_argument("--output-file", help="Optional path to write the formatted output")
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
    formatted = format_result(result, args.output_format)
    if args.output_file:
        Path(args.output_file).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output_file).write_text(formatted, encoding="utf-8")
        print(json.dumps({"run_id": result["run_id"], "status": result["status"], "output_file": args.output_file}, indent=2))
    else:
        print(formatted)


if __name__ == "__main__":
    main()

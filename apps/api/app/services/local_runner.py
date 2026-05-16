from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.db.models import AgentStep, Objective, ToolCall
from app.db.session import SessionLocal, init_db
from app.routes.reports import build_report, render_markdown_report
from app.services.run_executor import create_run_record, execute_run, normalize_run_config


ANSI = {
    "reset": "\033[0m",
    "dim": "\033[2m",
    "bold": "\033[1m",
    "cyan": "\033[36m",
    "blue": "\033[34m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "magenta": "\033[35m",
    "red": "\033[31m",
    "white": "\033[37m",
}


STATE_COLORS = {
    "INITIALIZE_FRAMEWORK": "cyan",
    "PLAN_RESEARCH": "blue",
    "FIND_TOOLS": "magenta",
    "EXECUTE_EVIDENCE_COLLECTION": "green",
    "SCORE_EVIDENCE": "yellow",
    "GENERATE_HYPOTHESES": "blue",
    "CRITIQUE_AND_REFINE": "red",
    "PROPOSE_EXPERIMENTS": "magenta",
    "GENERATE_REPORT": "cyan",
}


def paint(text: str, color: str, enabled: bool = True) -> str:
    if not enabled:
        return text
    return f"{ANSI.get(color, '')}{text}{ANSI['reset']}"


def run_question(
    question: str,
    config: dict | None = None,
    progress_callback: Any | None = None,
) -> dict:
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
        run = execute_run(db, run, objective, progress_callback=progress_callback)
        report = build_report(run.id, db)
        steps = db.query(AgentStep).filter(AgentStep.run_id == run.id).order_by(AgentStep.started_at.asc()).all()
        tool_calls = db.query(ToolCall).filter(ToolCall.run_id == run.id).order_by(ToolCall.created_at.asc()).all()
        return {
            "run_id": run.id,
            "status": run.status,
            "final_confidence": run.final_confidence,
            "report_url": f"/reports/{run.id}",
            "trace_url": f"/runs/{run.id}/trace",
            "trace_summary": {
                "agent_steps": len(steps),
                "tool_calls": len(tool_calls),
            },
            "provenance": {
                "agent_steps": [
                    {
                        "agent_name": step.agent_name,
                        "state_name": step.state_name,
                        "input": step.input_json,
                        "output": step.output_json,
                        "started_at": step.started_at.isoformat(),
                        "completed_at": step.completed_at.isoformat() if step.completed_at else None,
                        "error": step.error,
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
                        "created_at": call.created_at.isoformat(),
                    }
                    for call in tool_calls
                ],
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
    ]
    errors = [
        step.get("error")
        for step in result.get("provenance", {}).get("agent_steps", [])
        if step.get("error")
    ]
    if errors:
        lines.extend(["", "Errors:"])
        lines.extend(f"- {error}" for error in errors)
    lines.extend(["", f"Hypothesis: {hypothesis['title']}", hypothesis["text"], "", "Evidence:"])
    for item in report["evidence"]:
        lines.append(f"- {item['source']}: {item['support_label']} ({item['support_score']})")
    lines.extend(["", "Guardrails:"])
    for guardrail in report["guardrails"]:
        lines.append(f"- {guardrail}")
    return "\n".join(lines)


def optimized_agent_count(question: str) -> int:
    text = question.lower()
    score = 4
    complexity_terms = [
        "compound",
        "molecule",
        "omics",
        "pathway",
        "literature",
        "safety",
        "clinical",
        "experiment",
        "drug",
        "therapeutic",
    ]
    score += min(4, sum(1 for term in complexity_terms if term in text) // 2)
    if len(question) > 300:
        score += 1
    return max(3, min(score, 8))


def render_progress_event(event: dict[str, Any], color: bool = True) -> str:
    state_name = event["state_name"]
    agent_name = event["agent_name"]
    output = event.get("output", {})
    state_color = STATE_COLORS.get(state_name, "white")
    lines = [paint(f"[{state_name}]", state_color, color) + f" {paint(agent_name, 'bold', color)}"]
    if "framework" in output:
        lines.append(f"  runtime: {output['framework']} ({output.get('mode')})")
        roster = output.get("agent_roster", [])
        if roster:
            lines.append(paint("  agents initialized:", "cyan", color))
            for agent in roster:
                lines.append(
                    f"    {agent.get('slot')}. {paint(agent.get('agent_name', ''), 'bold', color)}"
                    f" - {agent.get('responsibility')}"
                )
    if "plan" in output:
        lines.append(f"  plan steps: {len(output['plan'])}")
        for index, step in enumerate(output["plan"][:6], start=1):
            lines.append(f"    {index}. {step}")
    if "biomedical_context" in output:
        context = output["biomedical_context"]
        if context.get("primary_genes"):
            lines.append(f"  targets: {', '.join(context['primary_genes'])}")
        if context.get("diseases"):
            lines.append(f"  diseases: {', '.join(context['diseases'])}")
        if context.get("candidate_interventions"):
            lines.append(f"  candidates: {', '.join(context['candidate_interventions'][:6])}")
        if context.get("pubmed_queries"):
            lines.append(f"  literature queries: {len(context['pubmed_queries'])}")
    if "selected_tools" in output:
        lines.append(f"  queued tools: {', '.join(output['selected_tools'])}")
    if "tool_output_count" in output:
        lines.append(
            f"  tool calls completed: {output['tool_output_count']} "
            f"(custom models: {output.get('custom_model_tool_count', 0)}, "
            f"live public: {output.get('live_public_tool_count', 0)}, "
            f"tooluniverse: {output.get('tooluniverse_tool_count', 0)})"
        )
    if "agent_tool_assignments" in output:
        for assignment in output["agent_tool_assignments"][:10]:
            status_color = "green" if assignment["status"] == "success" else "yellow"
            lines.append(
                f"  {assignment['agent_name']} -> {assignment['tool_name']}: "
                f"{paint(assignment['status'], status_color, color)}"
            )
    if "scored_evidence" in output:
        labels = [item.get("score", {}).get("label", "unscored") for item in output["scored_evidence"]]
        lines.append(f"  evidence scored: {', '.join(labels)}")
    if "llm_calls" in output and output["llm_calls"]:
        latest = output["llm_calls"][-1]
        lines.append(
            f"  {paint('llm', 'magenta', color)}: {latest.get('agent_name')} {latest.get('task')} "
            f"via {latest.get('provider')}/{latest.get('model')} ({latest.get('latency_ms')} ms)"
        )
    if "hypothesis_card" in output:
        card = output["hypothesis_card"]
        lines.append(f"  hypothesis: {card.get('title')}")
        lines.append(f"  confidence: {card.get('confidence')}")
    if "critique" in output:
        lines.append(f"  critique: {output['critique']}")
    if "experiments" in output:
        lines.append(f"  experiments proposed: {len(output['experiments'])}")
    if "report" in output:
        lines.append(f"  report confidence: {output['report'].get('confidence')}")
    return "\n".join(lines)


def prompt_multiline_objective() -> str:
    print("Paste your scientific problem. Press Enter on a blank line to run.")
    lines = []
    while True:
        line = input("> ")
        if not line.strip():
            break
        lines.append(line)
    objective = "\n".join(lines).strip()
    if objective:
        return objective
    return "Generate a therapeutic hypothesis for ACVR1-driven Fibrodysplasia Ossificans Progressiva and propose validation experiments."


def prompt_agent_count(question: str) -> int:
    recommended = optimized_agent_count(question)
    raw = input(f"Agents to use [optimized={recommended}, or enter 1-12]: ").strip().lower()
    if raw in {"", "optimized", "opt", "o"}:
        return recommended
    try:
        return max(1, min(int(raw), 12))
    except ValueError:
        print(f"Using optimized agent count: {recommended}")
        return recommended


def run_interactive() -> None:
    print("BioAutoScientist interactive local run")
    question = prompt_multiline_objective()
    agents = prompt_agent_count(question)
    strictness = input("Evidence strictness [balanced/exploratory/strict, default balanced]: ").strip().lower()
    if strictness not in {"balanced", "exploratory", "strict"}:
        strictness = "balanced"
    live_raw = input("Use live public biomedical data? [Y/n]: ").strip().lower()
    real_data_enabled = live_raw not in {"n", "no", "mock"}
    provider = input("LLM provider [openai/anthropic/gemini/openai_compatible/local_http, default openai]: ").strip().lower()
    provider = provider or "openai"
    model_default = {
        "openai": "gpt-4.1",
        "anthropic": "claude-sonnet-4-6",
        "gemini": "gemini-1.5-pro",
        "openai_compatible": "local-model",
        "local_http": "local-http-model",
    }.get(provider, "gpt-4.1")
    model = input(f"LLM model [default {model_default}]: ").strip() or model_default
    api_key_env = input("API key env var [provider default]: ").strip()
    base_url = ""
    if provider in {"openai_compatible", "local_http"}:
        base_url = input("LLM base URL: ").strip()
    output_file = input("Markdown output file [outputs/interactive_report.md]: ").strip() or "outputs/interactive_report.md"
    provenance_file = (
        input("Provenance JSON file [outputs/interactive_provenance.json]: ").strip()
        or "outputs/interactive_provenance.json"
    )
    print("")
    print(f"Queued {agents} agents with {strictness} evidence strictness.")
    print(f"Live public biomedical data: {'enabled' if real_data_enabled else 'disabled'}")
    print(f"Real LLM: {provider}/{model}")
    print("Running local scientist loop...\n")

    def progress(event: dict[str, Any]) -> None:
        print(render_progress_event(event))
        print("")

    result = run_question(
        question,
        {
            "agent_count": agents,
            "max_runtime_minutes": 30,
            "evidence_strictness": strictness,
            "llm_provider": provider,
            "llm_model": model,
            "llm_api_key_env_var": api_key_env,
            "llm_base_url": base_url,
            "require_real_llm": True,
            "real_data_enabled": real_data_enabled,
        },
        progress_callback=progress,
    )
    report_text = format_result(result, "markdown")
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    Path(output_file).write_text(report_text, encoding="utf-8")
    Path(provenance_file).parent.mkdir(parents=True, exist_ok=True)
    Path(provenance_file).write_text(
        json.dumps(
            {
                "run_id": result["run_id"],
                "status": result["status"],
                "trace_summary": result["trace_summary"],
                "provenance": result["provenance"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("Final answer")
    print(format_result(result, "summary"))
    print("")
    print(f"Markdown report: {output_file}")
    print(f"Provenance JSON: {provenance_file}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a local BioAutoScientist question.")
    parser.add_argument("question", nargs="?", help="Scientific question or objective")
    parser.add_argument("--interactive", action="store_true", help="Prompt for agents and scientific problem")
    parser.add_argument("--agents", type=int, default=6)
    parser.add_argument("--runtime", type=int, default=30)
    parser.add_argument("--strictness", choices=["exploratory", "balanced", "strict"], default="balanced")
    parser.add_argument("--llm-provider", default="mock")
    parser.add_argument("--llm-model", default="mock-scientist")
    parser.add_argument("--llm-api-key-env-var", default="")
    parser.add_argument("--llm-base-url", default="")
    parser.add_argument("--require-real-llm", action="store_true")
    parser.add_argument("--model-tool", action="append", default=[], help="Registered custom model tool name")
    parser.add_argument("--real-data", action="store_true", help="Use live public biomedical APIs during the run")
    parser.add_argument(
        "--output-format",
        choices=["summary", "json", "markdown"],
        default="summary",
        help="Command-line output format",
    )
    parser.add_argument("--output-file", help="Optional path to write the formatted output")
    parser.add_argument("--provenance-file", help="Optional path to write full JSON trace and tool provenance")
    parser.add_argument("--stream-progress", action="store_true", help="Stream agent, LLM, and tool activity as it runs")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI colors in streamed progress")
    args = parser.parse_args()
    if args.interactive:
        run_interactive()
        return
    if not args.question:
        parser.error("question is required unless --interactive is set")
    def progress(event: dict[str, Any]) -> None:
        print(render_progress_event(event, color=not args.no_color), flush=True)
        print("", flush=True)

    if args.stream_progress:
        print(
            paint("BioAutoScientist strict local run", "bold", not args.no_color),
            flush=True,
        )
        print(f"Question: {args.question}", flush=True)
        print(f"Agents: {args.agents} | Strictness: {args.strictness} | Provider: {args.llm_provider}/{args.llm_model}", flush=True)
        print("", flush=True)

    result = run_question(
        args.question,
        {
            "agent_count": args.agents,
            "max_runtime_minutes": args.runtime,
            "evidence_strictness": args.strictness,
            "llm_provider": args.llm_provider,
            "llm_model": args.llm_model,
            "llm_api_key_env_var": args.llm_api_key_env_var,
            "llm_base_url": args.llm_base_url,
            "require_real_llm": args.require_real_llm,
            "model_tool_names": args.model_tool,
            "real_data_enabled": args.real_data,
        },
        progress_callback=progress if args.stream_progress else None,
    )
    formatted = format_result(result, args.output_format)
    if args.provenance_file:
        Path(args.provenance_file).parent.mkdir(parents=True, exist_ok=True)
        Path(args.provenance_file).write_text(
            json.dumps(
                {
                    "run_id": result["run_id"],
                    "status": result["status"],
                    "trace_summary": result["trace_summary"],
                    "provenance": result["provenance"],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    if args.output_file:
        Path(args.output_file).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output_file).write_text(formatted, encoding="utf-8")
        print(
            json.dumps(
                {
                    "run_id": result["run_id"],
                    "status": result["status"],
                    "output_file": args.output_file,
                    "provenance_file": args.provenance_file,
                },
                indent=2,
            )
        )
    else:
        print(formatted)
    if args.require_real_llm and result["status"] != "completed":
        raise SystemExit(2)


if __name__ == "__main__":
    main()

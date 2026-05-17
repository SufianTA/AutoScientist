from datetime import datetime
import re
from typing import Any

from agents.app.state import AgentStateName, ResearchRunState
from tools.custom_tools.registry import build_custom_tools


class AgentOrchestrator:
    def __init__(self) -> None:
        self.tools = build_custom_tools()

    def _context_from_objective(self, objective: str) -> dict[str, str]:
        stop = {"AND", "THE", "USE", "NOT", "FOR", "WITH", "DNA", "RNA", "LLM"}
        genes = [
            match
            for match in re.findall(r"\b[A-Z][A-Z0-9]{2,9}\b", objective)
            if match not in stop
        ]
        disease = "the specified disease context"
        for pattern in [
            r"for ([A-Za-z][A-Za-z0-9 /'-]+?)(?:\.|,|;| and | with | by |$)",
            r"driven ([A-Za-z][A-Za-z0-9 /'-]+?)(?:\.|,|;| and | with | by |$)",
            r"in ([A-Za-z][A-Za-z0-9 /'-]+?)(?:\.|,|;| and | with | by |$)",
        ]:
            match = re.search(pattern, objective)
            if match:
                disease = re.sub(r"^[A-Z0-9]+-driven\s+", "", match.group(1), flags=re.I).strip()
                break
        target = genes[0] if genes else "disease-relevant target"
        return {"target": target, "disease": disease}

    def run_demo(
        self,
        run_id: str,
        objective_id: str,
        objective: str,
        run_config: dict[str, Any] | None = None,
    ) -> tuple[ResearchRunState, list[dict[str, Any]]]:
        state = ResearchRunState(run_id=run_id, objective_id=objective_id, objective=objective)
        config = run_config or {}
        context = self._context_from_objective(objective)
        target = context["target"]
        disease = context["disease"]
        trace: list[dict[str, Any]] = []

        def record(agent: str, state_name: AgentStateName, output: dict[str, Any]) -> None:
            trace.append(
                {
                    "agent_name": agent,
                    "state_name": state_name.value,
                    "input": {"objective": state.objective, "run_config": config},
                    "output": output,
                    "completed_at": datetime.utcnow().isoformat(),
                }
            )

        state.current_state = AgentStateName.PLAN_RESEARCH
        state.plan = [
            "Ground disease and target identity.",
            "Collect available mechanism, literature, target, and intervention evidence.",
            "Generate candidate therapeutic hypothesis.",
            "Score evidence and apply skeptical critique.",
            "Publish board post and final report with guardrails.",
        ]
        record(
            "pi_agent",
            state.current_state,
            {
                "plan": state.plan,
                "agent_count": config.get("agent_count", 6),
                "evidence_strictness": config.get("evidence_strictness", "balanced"),
                "max_runtime_minutes": config.get("max_runtime_minutes", 30),
            },
        )

        state.current_state = AgentStateName.FIND_TOOLS
        state.selected_tools = [
            "evidence_quality_scorer_tool",
            "hypothesis_card_generator_tool",
            "experiment_recommendation_tool",
        ]
        record("finder_agent", state.current_state, {"selected_tools": state.selected_tools})

        state.current_state = AgentStateName.EXECUTE_EVIDENCE_COLLECTION
        state.evidence = [
            {
                "source": "local_objective_context",
                "text": (
                    f"The user objective asks whether {target}-linked biology is relevant to "
                    f"{disease}. This is planning context, not external evidence."
                ),
                "structured": {"target": target, "disease": disease, "objective": objective},
            },
            {
                "source": "local_guardrail_context",
                "text": (
                    "No live biomedical databases or real LLM were used in this fallback path; "
                    "claims must remain provisional until live evidence is retrieved."
                ),
                "structured": {"requires_live_validation": True},
            },
        ]
        record("mechanism_agent", state.current_state, {"evidence": state.evidence})

        state.current_state = AgentStateName.SCORE_EVIDENCE
        scored = []
        for item in state.evidence:
            score = self.tools["evidence_quality_scorer_tool"].run(
                {
                    "hypothesis": f"Modulating {target}-linked mechanisms may be relevant to {disease}.",
                    "evidence_text": item["text"],
                    "evidence_source": item["source"],
                }
            ).model_dump()
            scored.append({**item, "score": score["output"]})
        state.evidence = scored
        record("critic_agent", state.current_state, {"scored_evidence": scored})

        state.current_state = AgentStateName.GENERATE_HYPOTHESES
        card = self.tools["hypothesis_card_generator_tool"].run(
            {"target": target, "disease": disease, "evidence": scored}
        ).model_dump()
        state.hypothesis_card = card["output"]
        record("mechanism_agent", state.current_state, {"hypothesis_card": state.hypothesis_card})

        state.current_state = AgentStateName.CRITIQUE_AND_REFINE
        state.critique = {
            "critique_type": "translation_gap",
            "severity": "medium",
            "critique": (
                "This fallback run used only local objective context. It is not sufficient to rank "
                "clinical candidates or claim efficacy."
            ),
            "recommended_fix": (
                "Run strict real mode with a real LLM, live public APIs, ToolUniverse target-disease "
                "tools, intervention evidence, and safety review before escalation."
            ),
        }
        record("critic_agent", state.current_state, state.critique)

        state.current_state = AgentStateName.PROPOSE_EXPERIMENTS
        experiments = self.tools["experiment_recommendation_tool"].run({"hypothesis_card": state.hypothesis_card}).model_dump()
        state.experiments = experiments["output"]["experiments"]
        record("experiment_designer_agent", state.current_state, {"experiments": state.experiments})

        state.current_state = AgentStateName.GENERATE_REPORT
        state.report = {
            "title": f"{target} / {disease} Candidate Therapeutic Hypothesis Report",
            "summary": state.hypothesis_card.get("hypothesis"),
            "confidence": state.hypothesis_card.get("confidence", 0.0),
            "guardrails": [
                "No clinical efficacy claim is made.",
                "No safety claim is made.",
                "This is a computationally prioritized candidate hypothesis requiring validation.",
            ],
            "next_experiments": state.experiments,
            "run_config": config,
        }
        record("publisher_agent", state.current_state, {"report": state.report})
        return state, trace

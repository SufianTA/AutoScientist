from datetime import datetime
from typing import Any

from agents.app.state import AgentStateName, ResearchRunState
from tools.custom_tools.registry import build_custom_tools


class AgentOrchestrator:
    def __init__(self) -> None:
        self.tools = build_custom_tools()

    def run_demo(self, run_id: str, objective_id: str, objective: str) -> tuple[ResearchRunState, list[dict[str, Any]]]:
        state = ResearchRunState(run_id=run_id, objective_id=objective_id, objective=objective)
        trace: list[dict[str, Any]] = []

        def record(agent: str, state_name: AgentStateName, output: dict[str, Any]) -> None:
            trace.append(
                {
                    "agent_name": agent,
                    "state_name": state_name.value,
                    "input": {"objective": state.objective},
                    "output": output,
                    "completed_at": datetime.utcnow().isoformat(),
                }
            )

        state.current_state = AgentStateName.PLAN_RESEARCH
        state.plan = [
            "Ground disease and target identity.",
            "Collect ACVR1/FOP mechanism evidence.",
            "Generate candidate therapeutic hypothesis.",
            "Score evidence and apply skeptical critique.",
            "Publish board post and final report with guardrails.",
        ]
        record("pi_agent", state.current_state, {"plan": state.plan})

        state.current_state = AgentStateName.FIND_TOOLS
        state.selected_tools = [
            "acvr1_target_profile_tool",
            "fop_disease_profile_tool",
            "evidence_quality_scorer_tool",
            "hypothesis_card_generator_tool",
            "experiment_recommendation_tool",
        ]
        record("finder_agent", state.current_state, {"selected_tools": state.selected_tools})

        state.current_state = AgentStateName.EXECUTE_EVIDENCE_COLLECTION
        acvr1 = self.tools["acvr1_target_profile_tool"].run({"gene_symbol": "ACVR1"}).model_dump()
        fop = self.tools["fop_disease_profile_tool"].run({"disease_name": "Fibrodysplasia Ossificans Progressiva"}).model_dump()
        state.tool_outputs.extend([{"tool_name": "acvr1_target_profile_tool", "result": acvr1}, {"tool_name": "fop_disease_profile_tool", "result": fop}])
        state.evidence = [
            {
                "source": "acvr1_target_profile_tool",
                "text": "ACVR1 activating variants are linked to FOP and BMP/osteogenic signaling.",
                "structured": acvr1["output"],
            },
            {
                "source": "fop_disease_profile_tool",
                "text": "FOP is a rare disorder with progressive heterotopic ossification and strong ACVR1 causal link.",
                "structured": fop["output"],
            },
        ]
        record("mechanism_agent", state.current_state, {"evidence": state.evidence})

        state.current_state = AgentStateName.SCORE_EVIDENCE
        scored = []
        for item in state.evidence:
            score = self.tools["evidence_quality_scorer_tool"].run(
                {
                    "hypothesis": "Modulating ACVR1-linked BMP signaling may reduce FOP-relevant osteogenic signaling.",
                    "evidence_text": item["text"],
                    "evidence_source": item["source"],
                }
            ).model_dump()
            scored.append({**item, "score": score["output"]})
        state.evidence = scored
        record("critic_agent", state.current_state, {"scored_evidence": scored})

        state.current_state = AgentStateName.GENERATE_HYPOTHESES
        card = self.tools["hypothesis_card_generator_tool"].run(
            {"target": "ACVR1", "disease": "FOP", "evidence": scored}
        ).model_dump()
        state.hypothesis_card = card["output"]
        record("mechanism_agent", state.current_state, {"hypothesis_card": state.hypothesis_card})

        state.current_state = AgentStateName.CRITIQUE_AND_REFINE
        state.critique = {
            "critique_type": "translation_gap",
            "severity": "medium",
            "critique": "The mechanism is plausible, but mock evidence is not sufficient to rank clinical candidates or claim efficacy.",
            "recommended_fix": "Replace mock profiles with ToolUniverse target-disease, literature, ChEMBL, and safety calls before escalation.",
        }
        record("critic_agent", state.current_state, state.critique)

        state.current_state = AgentStateName.PROPOSE_EXPERIMENTS
        experiments = self.tools["experiment_recommendation_tool"].run({"hypothesis_card": state.hypothesis_card}).model_dump()
        state.experiments = experiments["output"]["experiments"]
        record("experiment_designer_agent", state.current_state, {"experiments": state.experiments})

        state.current_state = AgentStateName.GENERATE_REPORT
        state.report = {
            "title": "ACVR1/FOP Candidate Therapeutic Hypothesis Report",
            "summary": state.hypothesis_card.get("hypothesis"),
            "confidence": state.hypothesis_card.get("confidence", 0.0),
            "guardrails": [
                "No clinical efficacy claim is made.",
                "No safety claim is made.",
                "This is a computationally prioritized candidate hypothesis requiring validation.",
            ],
            "next_experiments": state.experiments,
        }
        record("publisher_agent", state.current_state, {"report": state.report})
        return state, trace


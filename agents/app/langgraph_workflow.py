from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from agents.app.graph import AgentOrchestrator
from agents.app.state import AgentStateName, ResearchRunState


class LangGraphScientificWorkflow(AgentOrchestrator):
    """Node-by-node scientific workflow with LangGraph when available.

    The node functions are plain Python and deterministic. When LangGraph is
    installed, they are wired into a StateGraph. When it is unavailable, the
    same nodes run sequentially so local development and CI remain reliable.
    """

    def __init__(self, fallback: AgentOrchestrator | None = None) -> None:
        super().__init__()
        self.fallback = fallback or AgentOrchestrator()
        self.langgraph_available = self._check_langgraph()

    def _check_langgraph(self) -> bool:
        try:
            import langgraph  # noqa: F401
        except Exception:
            return False
        return True

    def run_demo(
        self,
        run_id: str,
        objective_id: str,
        objective: str,
        run_config: dict[str, Any] | None = None,
    ) -> tuple[ResearchRunState, list[dict[str, Any]]]:
        config = {**(run_config or {}), "agent_framework": "langgraph"}
        state = ResearchRunState(run_id=run_id, objective_id=objective_id, objective=objective)
        trace: list[dict[str, Any]] = []
        self._record(
            trace,
            "framework_runtime",
            "INITIALIZE_FRAMEWORK",
            {"objective": objective, "run_config": config},
            {
                "framework": "langgraph",
                "available": self.langgraph_available,
                "mode": "state_graph" if self.langgraph_available else "sequential_node_fallback",
                "node_count": len(self._node_sequence()),
            },
        )

        if self.langgraph_available:
            state = self._run_langgraph(state, trace, config)
        else:
            state = self._run_sequential(state, trace, config)
        return state, trace

    def _run_langgraph(
        self,
        initial_state: ResearchRunState,
        trace: list[dict[str, Any]],
        config: dict[str, Any],
    ) -> ResearchRunState:
        try:
            from langgraph.graph import END, StateGraph
        except Exception:
            return self._run_sequential(initial_state, trace, config)

        graph = StateGraph(ResearchRunState)
        nodes = self._node_sequence()
        for node_name, node_func in nodes:
            graph.add_node(node_name, self._graph_node(node_func, trace, config))
        graph.set_entry_point(nodes[0][0])
        for index, (node_name, _) in enumerate(nodes):
            if index == len(nodes) - 1:
                graph.add_edge(node_name, END)
            else:
                graph.add_edge(node_name, nodes[index + 1][0])
        compiled = graph.compile()
        result = compiled.invoke(initial_state)
        if isinstance(result, ResearchRunState):
            return result
        return ResearchRunState.model_validate(result)

    def _run_sequential(
        self,
        state: ResearchRunState,
        trace: list[dict[str, Any]],
        config: dict[str, Any],
    ) -> ResearchRunState:
        for _, node_func in self._node_sequence():
            state = node_func(state, trace, config)
        return state

    def _graph_node(
        self,
        node_func: Callable[[ResearchRunState, list[dict[str, Any]], dict[str, Any]], ResearchRunState],
        trace: list[dict[str, Any]],
        config: dict[str, Any],
    ) -> Callable[[ResearchRunState | dict[str, Any]], ResearchRunState]:
        def wrapped(state: ResearchRunState | dict[str, Any]) -> ResearchRunState:
            parsed = state if isinstance(state, ResearchRunState) else ResearchRunState.model_validate(state)
            return node_func(parsed, trace, config)

        return wrapped

    def _node_sequence(
        self,
    ) -> list[tuple[str, Callable[[ResearchRunState, list[dict[str, Any]], dict[str, Any]], ResearchRunState]]]:
        return [
            ("plan_research", self._plan_research),
            ("find_tools", self._find_tools),
            ("execute_evidence_collection", self._execute_evidence_collection),
            ("score_evidence", self._score_evidence),
            ("generate_hypotheses", self._generate_hypotheses),
            ("critique_and_refine", self._critique_and_refine),
            ("propose_experiments", self._propose_experiments),
            ("generate_report", self._generate_report),
        ]

    def _record(
        self,
        trace: list[dict[str, Any]],
        agent: str,
        state_name: str,
        input_payload: dict[str, Any],
        output: dict[str, Any],
    ) -> None:
        trace.append(
            {
                "agent_name": agent,
                "state_name": state_name,
                "input": input_payload,
                "output": output,
                "completed_at": datetime.utcnow().isoformat(),
            }
        )

    def _plan_research(
        self,
        state: ResearchRunState,
        trace: list[dict[str, Any]],
        config: dict[str, Any],
    ) -> ResearchRunState:
        state.current_state = AgentStateName.PLAN_RESEARCH
        state.plan = [
            "Ground disease and target identity.",
            "Collect disease-target-mechanism evidence through ToolUniverse-style tools.",
            "Generate a candidate hypothesis with explicit uncertainty.",
            "Score evidence and separate support from translation gaps.",
            "Critique claims before publishing to the research board.",
            "Propose computational and experimental validation steps.",
        ]
        self._record(
            trace,
            "pi_agent",
            state.current_state.value,
            {"objective": state.objective, "run_config": config},
            {
                "plan": state.plan,
                "agent_count": config.get("agent_count", 6),
                "evidence_strictness": config.get("evidence_strictness", "balanced"),
                "llm_provider": config.get("llm_provider", "mock"),
                "llm_model": config.get("llm_model", "mock-scientist"),
            },
        )
        return state

    def _find_tools(
        self,
        state: ResearchRunState,
        trace: list[dict[str, Any]],
        config: dict[str, Any],
    ) -> ResearchRunState:
        state.current_state = AgentStateName.FIND_TOOLS
        state.selected_tools = [
            "acvr1_target_profile_tool",
            "fop_disease_profile_tool",
            "evidence_quality_scorer_tool",
            "hypothesis_card_generator_tool",
            "experiment_recommendation_tool",
            *config.get("model_tool_names", []),
        ]
        self._record(
            trace,
            "finder_agent",
            state.current_state.value,
            {"objective": state.objective, "available_custom_tools": sorted(self.tools.keys())},
            {"selected_tools": state.selected_tools, "selection_policy": "mock ACVR1/FOP demo plus configured model tools"},
        )
        return state

    def _execute_evidence_collection(
        self,
        state: ResearchRunState,
        trace: list[dict[str, Any]],
        config: dict[str, Any],
    ) -> ResearchRunState:
        state.current_state = AgentStateName.EXECUTE_EVIDENCE_COLLECTION
        acvr1 = self.tools["acvr1_target_profile_tool"].run({"gene_symbol": "ACVR1"}).model_dump()
        fop = self.tools["fop_disease_profile_tool"].run(
            {"disease_name": "Fibrodysplasia Ossificans Progressiva"}
        ).model_dump()
        state.tool_outputs.extend(
            [
                {"tool_name": "acvr1_target_profile_tool", "result": acvr1},
                {"tool_name": "fop_disease_profile_tool", "result": fop},
            ]
        )
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
        self._record(
            trace,
            "mechanism_agent",
            state.current_state.value,
            {"selected_tools": state.selected_tools},
            {"evidence": state.evidence, "tool_output_count": len(state.tool_outputs)},
        )
        return state

    def _score_evidence(
        self,
        state: ResearchRunState,
        trace: list[dict[str, Any]],
        config: dict[str, Any],
    ) -> ResearchRunState:
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
        self._record(
            trace,
            "critic_agent",
            state.current_state.value,
            {"evidence_count": len(scored), "strictness": config.get("evidence_strictness", "balanced")},
            {"scored_evidence": scored},
        )
        return state

    def _generate_hypotheses(
        self,
        state: ResearchRunState,
        trace: list[dict[str, Any]],
        config: dict[str, Any],
    ) -> ResearchRunState:
        state.current_state = AgentStateName.GENERATE_HYPOTHESES
        card = self.tools["hypothesis_card_generator_tool"].run(
            {"target": "ACVR1", "disease": "FOP", "evidence": state.evidence}
        ).model_dump()
        state.hypothesis_card = card["output"]
        self._record(
            trace,
            "mechanism_agent",
            state.current_state.value,
            {"scored_evidence": state.evidence},
            {"hypothesis_card": state.hypothesis_card},
        )
        return state

    def _critique_and_refine(
        self,
        state: ResearchRunState,
        trace: list[dict[str, Any]],
        config: dict[str, Any],
    ) -> ResearchRunState:
        state.current_state = AgentStateName.CRITIQUE_AND_REFINE
        state.critique = {
            "critique_type": "translation_gap",
            "severity": "medium",
            "critique": "The mechanism is plausible, but mock evidence is not sufficient to rank clinical candidates or claim efficacy.",
            "recommended_fix": "Replace mock profiles with ToolUniverse target-disease, literature, ChEMBL, and safety calls before escalation.",
            "abstention_required": False,
        }
        self._record(
            trace,
            "critic_agent",
            state.current_state.value,
            {"hypothesis_card": state.hypothesis_card},
            state.critique,
        )
        return state

    def _propose_experiments(
        self,
        state: ResearchRunState,
        trace: list[dict[str, Any]],
        config: dict[str, Any],
    ) -> ResearchRunState:
        state.current_state = AgentStateName.PROPOSE_EXPERIMENTS
        experiments = self.tools["experiment_recommendation_tool"].run(
            {"hypothesis_card": state.hypothesis_card}
        ).model_dump()
        state.experiments = experiments["output"]["experiments"]
        self._record(
            trace,
            "experiment_designer_agent",
            state.current_state.value,
            {"hypothesis_card": state.hypothesis_card, "critique": state.critique},
            {"experiments": state.experiments},
        )
        return state

    def _generate_report(
        self,
        state: ResearchRunState,
        trace: list[dict[str, Any]],
        config: dict[str, Any],
    ) -> ResearchRunState:
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
            "run_config": config,
            "agent_framework": "langgraph",
        }
        self._record(
            trace,
            "publisher_agent",
            state.current_state.value,
            {
                "hypothesis_card": state.hypothesis_card,
                "critique": state.critique,
                "experiments": state.experiments,
            },
            {"report": state.report},
        )
        return state

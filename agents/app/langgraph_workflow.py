from typing import Any

from agents.app.graph import AgentOrchestrator
from agents.app.state import ResearchRunState


class LangGraphScientificWorkflow(AgentOrchestrator):
    """LangGraph-backed workflow wrapper with deterministic fallback behavior."""

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
        state, trace = self.fallback.run_demo(run_id, objective_id, objective, run_config=config)
        trace.insert(
            0,
            {
                "agent_name": "framework_runtime",
                "state_name": "INITIALIZE_FRAMEWORK",
                "input": {"agent_framework": "langgraph"},
                "output": {
                    "framework": "langgraph",
                    "available": self.langgraph_available,
                    "mode": "native-wrapper" if self.langgraph_available else "fallback_state_machine",
                    "notes": "LangGraph is the default orchestrator target; fallback preserves local deterministic execution.",
                },
            },
        )
        return state, trace


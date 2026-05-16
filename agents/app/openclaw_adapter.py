from typing import Any

from agents.app.graph import AgentOrchestrator
from agents.app.state import ResearchRunState


class OpenClawAdapter(AgentOrchestrator):
    """Optional OpenClaw adapter placeholder.

    OpenClaw is not the default core runtime. This adapter keeps the integration
    point explicit while routing current scientific runs through the audited
    local state machine until a constrained OpenClaw integration is added.
    """

    def __init__(self, fallback: AgentOrchestrator | None = None) -> None:
        super().__init__()
        self.fallback = fallback or AgentOrchestrator()

    def run_demo(
        self,
        run_id: str,
        objective_id: str,
        objective: str,
        run_config: dict[str, Any] | None = None,
    ) -> tuple[ResearchRunState, list[dict[str, Any]]]:
        config = {**(run_config or {}), "agent_framework": "openclaw"}
        state, trace = self.fallback.run_demo(run_id, objective_id, objective, run_config=config)
        trace.insert(
            0,
            {
                "agent_name": "framework_runtime",
                "state_name": "INITIALIZE_FRAMEWORK",
                "input": {"agent_framework": "openclaw"},
                "output": {
                    "framework": "openclaw",
                    "available": False,
                    "mode": "optional_adapter_placeholder",
                    "notes": "OpenClaw can be integrated later for optional workflows; scientific execution remains constrained and auditable.",
                },
            },
        )
        return state, trace


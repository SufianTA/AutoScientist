from typing import Any

from agents.app.graph import AgentOrchestrator
from agents.app.langgraph_workflow import LangGraphScientificWorkflow
from agents.app.openclaw_adapter import OpenClawAdapter


def build_agent_runtime(run_config: dict[str, Any]) -> AgentOrchestrator:
    framework = run_config.get("agent_framework", "langgraph")
    if framework == "openclaw":
        return OpenClawAdapter(fallback=AgentOrchestrator())
    if framework == "langgraph":
        return LangGraphScientificWorkflow(fallback=AgentOrchestrator())
    return AgentOrchestrator()


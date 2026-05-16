from typing import Any

from tools.custom_tools.registry import build_custom_tools


class ToolUniverseAdapter:
    """Adapter boundary for ToolUniverse plus custom prototype tools."""

    def __init__(self, mode: str = "mock") -> None:
        self.mode = mode
        self.custom_tools = build_custom_tools()

    def list_tools(self) -> list[dict[str, Any]]:
        tools = [tool.spec().model_dump() for tool in self.custom_tools.values()]
        tools.append(
            {
                "name": "tooluniverse_placeholder",
                "description": "Placeholder for installed ToolUniverse inventory discovery.",
                "input_schema": {"type": "object"},
                "output_schema": {"type": "object"},
                "example_input": {},
                "source": "tooluniverse",
                "status": "needs_install_or_configuration",
                "notes": "Wire to ToolUniverse package/CLI in Milestone 1 hardening.",
            }
        )
        return tools

    def inspect_schema(self, tool_name: str) -> dict[str, Any]:
        if tool_name not in self.custom_tools:
            raise KeyError(f"Unknown tool: {tool_name}")
        return self.custom_tools[tool_name].spec().model_dump()

    def execute(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        if tool_name not in self.custom_tools:
            raise KeyError(f"Unknown or unavailable tool: {tool_name}")
        return self.custom_tools[tool_name].run(payload).model_dump()


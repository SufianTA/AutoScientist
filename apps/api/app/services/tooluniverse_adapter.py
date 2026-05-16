import time
from typing import Any

from tools.custom_tools.registry import build_custom_tools


class ToolUniverseAdapter:
    """Adapter boundary for ToolUniverse plus custom prototype tools."""

    def __init__(self, mode: str = "mock", scan_all: bool = False) -> None:
        self.mode = mode
        self.scan_all = scan_all
        self.custom_tools = build_custom_tools()
        self._tooluniverse: Any | None = None
        self._tooluniverse_error: str | None = None

    def list_tools(self) -> list[dict[str, Any]]:
        tools = [tool.spec().model_dump() for tool in self.custom_tools.values()]
        tools.extend(self._list_tooluniverse_tools())
        return tools

    def tooluniverse_health(self) -> dict[str, Any]:
        instance = self._get_tooluniverse()
        if instance is None:
            return {
                "available": False,
                "status": "needs_install_or_dependency_fix",
                "error": self._tooluniverse_error,
            }
        return {"available": True, "status": "ready", "error": None}

    def inspect_schema(self, tool_name: str) -> dict[str, Any]:
        if tool_name not in self.custom_tools:
            for tool in self._list_tooluniverse_tools():
                if tool["name"] == tool_name:
                    return tool
            raise KeyError(f"Unknown tool: {tool_name}")
        return self.custom_tools[tool_name].spec().model_dump()

    def execute(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        if tool_name not in self.custom_tools:
            return self._execute_tooluniverse_tool(tool_name, payload)
        return self.custom_tools[tool_name].run(payload).model_dump()

    def _get_tooluniverse(self) -> Any | None:
        if self._tooluniverse is not None:
            return self._tooluniverse
        if self._tooluniverse_error is not None:
            return None
        try:
            from tooluniverse import ToolUniverse

            self._tooluniverse = ToolUniverse()
        except Exception as exc:  # ToolUniverse imports optional ML deps at module import time.
            self._tooluniverse_error = str(exc)
            return None
        return self._tooluniverse

    def _list_tooluniverse_tools(self) -> list[dict[str, Any]]:
        tooluniverse = self._get_tooluniverse()
        if tooluniverse is None:
            return [
                {
                    "name": "tooluniverse_unavailable",
                    "description": "ToolUniverse package could not be imported in the current environment.",
                    "input_schema": {"type": "object"},
                    "output_schema": {"type": "object"},
                    "example_input": {},
                    "source": "tooluniverse",
                    "status": "needs_install_or_dependency_fix",
                    "notes": self._tooluniverse_error or "Unknown ToolUniverse import failure.",
                }
            ]
        try:
            specs = tooluniverse.list_built_in_tools(mode="list_spec", scan_all=self.scan_all)
        except Exception as exc:
            return [
                {
                    "name": "tooluniverse_inventory_error",
                    "description": "ToolUniverse imported but inventory discovery failed.",
                    "input_schema": {"type": "object"},
                    "output_schema": {"type": "object"},
                    "example_input": {},
                    "source": "tooluniverse",
                    "status": "inventory_error",
                    "notes": str(exc),
                }
            ]
        normalized = []
        for spec in specs:
            try:
                normalized.append(self._normalize_tooluniverse_spec(spec))
            except Exception as exc:
                normalized.append(
                    {
                        "name": spec.get("name", "unnamed_tooluniverse_tool"),
                        "description": spec.get("description", ""),
                        "input_schema": {"type": "object"},
                        "output_schema": {"type": "object"},
                        "example_input": {},
                        "source": "tooluniverse",
                        "status": "schema_normalization_error",
                        "notes": str(exc),
                    }
                )
        return normalized

    def _normalize_tooluniverse_spec(self, spec: dict[str, Any]) -> dict[str, Any]:
        input_schema = spec.get("parameter") or spec.get("input_schema") or {"type": "object"}
        if not isinstance(input_schema, dict):
            input_schema = {"type": "object", "raw_schema": input_schema}
        return {
            "name": spec.get("name", "unnamed_tooluniverse_tool"),
            "description": spec.get("description", ""),
            "input_schema": input_schema,
            "output_schema": spec.get("output_schema") or {"type": "object"},
            "example_input": self._example_from_schema(input_schema),
            "source": "tooluniverse",
            "status": "available",
            "notes": self._format_tooluniverse_notes(spec),
        }

    def _format_tooluniverse_notes(self, spec: dict[str, Any]) -> str:
        labels = spec.get("label") or []
        tool_type = spec.get("type")
        parts = []
        if tool_type:
            parts.append(f"type={tool_type}")
        if labels:
            parts.append(f"labels={', '.join(labels)}")
        return "; ".join(parts)

    def _example_from_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
        properties = schema.get("properties") if isinstance(schema, dict) else {}
        if not isinstance(properties, dict):
            properties = {}
        example: dict[str, Any] = {}
        for key, value in properties.items():
            if not isinstance(value, dict):
                example[key] = ""
                continue
            if "default" in value:
                example[key] = value["default"]
            elif "example" in value:
                example[key] = value["example"]
            elif value.get("type") == "integer":
                example[key] = 0
            elif value.get("type") == "number":
                example[key] = 0.0
            elif value.get("type") == "array":
                example[key] = []
            elif value.get("type") == "boolean":
                example[key] = False
            else:
                example[key] = ""
        return example

    def _execute_tooluniverse_tool(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        tooluniverse = self._get_tooluniverse()
        if tooluniverse is None:
            raise KeyError(f"ToolUniverse unavailable: {self._tooluniverse_error}")
        try:
            tooluniverse.load_tools(include_tools=[tool_name])
            raw_output = tooluniverse.run({"name": tool_name, "arguments": payload}, verbose=False)
            status = "success"
            warnings: list[str] = []
        except Exception as exc:
            raw_output = {"error": str(exc)}
            status = "failure"
            warnings = [str(exc)]
        return {
            "status": status,
            "input": payload,
            "output": {"raw": raw_output},
            "sources": [{"name": "ToolUniverse", "tool_name": tool_name}],
            "confidence": 0.0,
            "warnings": warnings,
            "runtime_ms": int((time.perf_counter() - started) * 1000),
            "tool_version": "tooluniverse",
        }

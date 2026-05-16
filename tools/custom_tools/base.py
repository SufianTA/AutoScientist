from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    status: str
    input: dict[str, Any]
    output: dict[str, Any]
    sources: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.0
    warnings: list[str] = Field(default_factory=list)
    runtime_ms: int = 0
    tool_version: str = "0.1.0"


class ToolSpec(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    example_input: dict[str, Any]
    source: str = "custom"
    status: str = "working"
    notes: str = ""


class ScientificTool(ABC):
    name: str
    description: str
    example_input: dict[str, Any]
    tool_version = "0.1.0"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {"type": "object"}

    @property
    def output_schema(self) -> dict[str, Any]:
        return {"type": "object"}

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description=self.description,
            input_schema=self.input_schema,
            output_schema=self.output_schema,
            example_input=self.example_input,
        )

    def run(self, payload: dict[str, Any]) -> ToolResult:
        started = time.perf_counter()
        try:
            result = self._run(payload)
            result.runtime_ms = int((time.perf_counter() - started) * 1000)
            result.tool_version = self.tool_version
            return result
        except Exception as exc:  # pragma: no cover - defensive normalization
            return ToolResult(
                status="failure",
                input=payload,
                output={},
                confidence=0.0,
                warnings=[str(exc)],
                runtime_ms=int((time.perf_counter() - started) * 1000),
                tool_version=self.tool_version,
            )

    @abstractmethod
    def _run(self, payload: dict[str, Any]) -> ToolResult:
        raise NotImplementedError


from __future__ import annotations

import json
import os
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def execute_model_tool(tool_config: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Execute an onboarded custom model tool with normalized provenance output."""
    started = time.perf_counter()
    provider = tool_config.get("provider", "mock")
    name = tool_config.get("name", "custom_model_tool")
    try:
        if provider == "mock":
            output = _mock_model_response(name, payload)
        elif provider == "local_http":
            output = _local_http_response(tool_config, payload)
        else:
            output = {
                "label": "not_executed",
                "score": 0.0,
                "rationale": f"Provider '{provider}' is registered but not executed by the local runner yet.",
                "warnings": ["Use local_http for executable local model tools in this prototype."],
            }
        status = "success" if output.get("label") != "not_executed" else "partial"
        warnings = output.pop("warnings", [])
    except Exception as exc:  # pragma: no cover - defensive normalization
        status = "failure"
        output = {}
        warnings = [str(exc)]
    return {
        "status": status,
        "input": payload,
        "output": output,
        "sources": [{"name": name, "provider": provider, "type": "custom_model_tool"}],
        "confidence": float(output.get("score", 0.0)) if output else 0.0,
        "warnings": warnings,
        "runtime_ms": int((time.perf_counter() - started) * 1000),
        "tool_version": tool_config.get("tool_version", "0.1.0"),
    }


def _mock_model_response(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    hypothesis = str(payload.get("hypothesis", "")).lower()
    evidence = str(payload.get("evidence_text", payload.get("prompt", ""))).lower()
    overlaps = sum(1 for token in {"acvr1", "fop", "bmp", "ossification"} if token in hypothesis and token in evidence)
    score = min(0.95, 0.45 + overlaps * 0.12)
    label = "weak_support" if score < 0.7 else "strong_support"
    return {
        "label": label,
        "score": round(score, 2),
        "evidence_type": "custom_model",
        "rationale": f"{name} mock scorer found {overlaps} disease-mechanism token overlaps.",
        "warnings": ["Mock custom model output; replace with local_http endpoint for real inference."],
    }


def _local_http_response(tool_config: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    endpoint = tool_config.get("endpoint_url")
    if not endpoint:
        raise ValueError("local_http model tool requires endpoint_url")
    headers = {"Content-Type": "application/json"}
    env_var = tool_config.get("api_key_env_var")
    if env_var and os.getenv(env_var):
        headers["Authorization"] = f"Bearer {os.getenv(env_var)}"
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            decoded = response.read().decode("utf-8")
    except HTTPError as exc:
        raise RuntimeError(f"local_http model returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"local_http model endpoint unavailable: {exc.reason}") from exc
    result = json.loads(decoded)
    if not isinstance(result, dict):
        raise ValueError("local_http model response must be a JSON object")
    return result

from __future__ import annotations

import importlib
import os
import time
from typing import Any

from app.services.scientific_planning import fallback_evaluation_criteria


class OpenScientistCapabilityRegistry:
    """Thin adapter registry for the real Open AI Scientist capabilities.

    These adapters intentionally do not make external research packages hard
    dependencies of the core app; when packages are installed in an isolated
    runtime, the same adapter boundary can call them and preserve provenance.
    """

    def health(self) -> dict[str, Any]:
        return {
            "qworld": self._module_health("qworld"),
            "txagent": self._module_health("txagent"),
            "tooluniverse": self._module_health("tooluniverse"),
            "clawinstitute_board": {
                "available": True,
                "status": "local_board_ready",
                "mode": "local_research_board",
            },
        }

    def generate_qworld_criteria(
        self,
        objective: str,
        classification: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        config = config or {}
        if not config.get("qworld_enabled", True):
            return self._criteria_result(
                objective,
                classification,
                started,
                status="skipped",
                mode="disabled",
                warnings=["Qworld criteria generation is disabled in run_config."],
            )
        try:
            qworld = importlib.import_module("qworld")
            generator_cls = getattr(qworld, "CriteriaGenerator")
            model = config.get("qworld_model") or config.get("llm_model") or "gpt-4.1"
            base_url = config.get("qworld_base_url") or config.get("llm_base_url") or None
            api_key = self._api_key_from_env(config.get("qworld_api_key_env_var") or config.get("llm_api_key_env_var"))
            generator = generator_cls(model=model, base_url=base_url, api_key=api_key)
            raw = generator.generate({"id": "autosci_objective", "question": objective})
            criteria = raw.get("final_criteria") or raw.get("reviewed_criteria") or []
            if not criteria:
                raise RuntimeError("Qworld returned no final criteria.")
            return {
                "status": "success",
                "mode": "qworld",
                "criteria": criteria,
                "raw": raw,
                "warnings": [],
                "runtime_ms": int((time.perf_counter() - started) * 1000),
            }
        except Exception as exc:
            return self._criteria_result(
                objective,
                classification,
                started,
                status="partial",
                mode="fallback",
                warnings=[f"Qworld unavailable or failed: {str(exc)[:300]}"],
            )

    def txagent_health(self) -> dict[str, Any]:
        health = self._module_health("txagent")
        health["recommended_mode"] = "external_gpu_service_or_isolated_subprocess"
        return health

    def execute_txagent(self, question: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
        started = time.perf_counter()
        config = config or {}
        try:
            txagent_module = importlib.import_module("txagent")
            agent_cls = getattr(txagent_module, "TxAgent")
            model_name = config.get("txagent_model_name") or "mims-harvard/TxAgent-T1-Llama-3.1-8B"
            rag_model_name = config.get("txagent_rag_model_name") or "mims-harvard/ToolRAG-T1-GTE-Qwen2-1.5B"
            agent = agent_cls(model_name, rag_model_name, enable_summary=False)
            agent.init_model()
            output = agent.run_multistep_agent(
                question,
                temperature=float(config.get("txagent_temperature", 0.3)),
                max_new_tokens=int(config.get("txagent_max_new_tokens", 1024)),
                max_token=int(config.get("txagent_max_token", 90240)),
                call_agent=bool(config.get("txagent_multiagent", False)),
                max_round=int(config.get("txagent_max_round", 20)),
            )
            return {
                "status": "success",
                "input": {"question": question},
                "output": {"answer": output},
                "warnings": [],
                "runtime_ms": int((time.perf_counter() - started) * 1000),
                "capability": "txagent",
            }
        except Exception as exc:
            return {
                "status": "failure",
                "input": {"question": question},
                "output": {},
                "warnings": [f"TxAgent execution unavailable or failed: {str(exc)[:500]}"],
                "runtime_ms": int((time.perf_counter() - started) * 1000),
                "capability": "txagent",
            }

    def local_board_post_metadata(self, post_type: str, content: dict[str, Any]) -> dict[str, Any]:
        return {
            "clawinstitute_integration": {
                "mode": "local_research_board",
                "remote_sync": "not_configured",
                "post_type": post_type,
                "track_record_fields": {
                    "claim_count": len(content.get("claim_graph", {}).get("claims", [])),
                    "evaluation_score": content.get("report_evaluation", {}).get("score"),
                    "abstention_required": content.get("abstention", {}).get("abstention_required"),
                },
            }
        }

    def _criteria_result(
        self,
        objective: str,
        classification: dict[str, Any],
        started: float,
        *,
        status: str,
        mode: str,
        warnings: list[str],
    ) -> dict[str, Any]:
        return {
            "status": status,
            "mode": mode,
            "criteria": fallback_evaluation_criteria(objective, classification),
            "raw": None,
            "warnings": warnings,
            "runtime_ms": int((time.perf_counter() - started) * 1000),
        }

    def _module_health(self, module_name: str) -> dict[str, Any]:
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            return {"available": False, "status": "not_installed_or_import_failed", "error": str(exc)[:300]}
        return {
            "available": True,
            "status": "importable",
            "version": getattr(module, "__version__", None),
            "error": None,
        }

    def _api_key_from_env(self, env_var: str | None) -> str | None:
        if not env_var:
            return None
        return os.getenv(env_var)

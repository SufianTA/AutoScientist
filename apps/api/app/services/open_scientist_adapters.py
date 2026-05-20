from __future__ import annotations

import importlib
import json
import os
import subprocess
import time
from typing import Any

from app.services.scientific_planning import fallback_evaluation_criteria


class OpenScientistCapabilityRegistry:
    """Thin adapter registry for the real Open AI Scientist capabilities.

    These adapters intentionally do not make TxAgent or Medea hard dependencies
    of the core app; when the packages are installed in an isolated runtime, the
    same adapter boundary can call them and preserve provenance.
    """

    def health(self) -> dict[str, Any]:
        return {
            "qworld": self._module_health("qworld"),
            "txagent": self._module_health("txagent"),
            "medea": self.medea_health(),
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

    def medea_health(self) -> dict[str, Any]:
        external_python = os.getenv("MEDEA_PYTHON")
        if external_python:
            health = self._external_medea_health(external_python)
        else:
            health = self._module_health("medea")
        health["recommended_mode"] = "external_service_or_isolated_subprocess"
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

    def execute_medea(self, objective: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
        started = time.perf_counter()
        config = config or {}
        external_python = config.get("medea_python") or os.getenv("MEDEA_PYTHON")
        if external_python:
            return self._execute_medea_subprocess(objective, config, str(external_python), started)
        try:
            medea_module = importlib.import_module("medea")
            medea_func = getattr(medea_module, "medea")
            output = medea_func(
                user_instruction=objective,
                experiment_instruction=config.get("medea_experiment_instruction") or None,
                research_planning_module=config.get("medea_research_planning_module"),
                analysis_module=config.get("medea_analysis_module"),
                literature_module=config.get("medea_literature_module"),
                debate_rounds=int(config.get("medea_debate_rounds", 1)),
                panelist_llms=config.get("medea_panelist_llms"),
                timeout=int(config.get("medea_timeout_seconds", 1200)),
            )
            return {
                "status": "success",
                "input": {"objective": objective},
                "output": output,
                "warnings": [],
                "runtime_ms": int((time.perf_counter() - started) * 1000),
                "capability": "medea",
            }
        except Exception as exc:
            return {
                "status": "failure",
                "input": {"objective": objective},
                "output": {},
                "warnings": [f"Medea execution unavailable or failed: {str(exc)[:500]}"],
                "runtime_ms": int((time.perf_counter() - started) * 1000),
                "capability": "medea",
            }

    def _external_medea_health(self, python_executable: str) -> dict[str, Any]:
        code = """
import json
try:
    import medea
    print(json.dumps({
        "available": True,
        "status": "importable_external_python",
        "version": getattr(medea, "__version__", None),
        "python": __import__("sys").executable,
        "error": None,
    }))
except Exception as exc:
    print(json.dumps({
        "available": False,
        "status": "external_import_failed",
        "version": None,
        "python": __import__("sys").executable,
        "error": str(exc)[:500],
    }))
"""
        try:
            completed = subprocess.run(
                [python_executable, "-c", code],
                check=False,
                capture_output=True,
                text=True,
                timeout=90,
            )
        except Exception as exc:
            return {
                "available": False,
                "status": "external_python_failed",
                "version": None,
                "python": python_executable,
                "error": str(exc)[:500],
            }
        return self._json_from_subprocess(completed.stdout) or {
            "available": False,
            "status": "external_import_failed",
            "version": None,
            "python": python_executable,
            "error": (completed.stderr or completed.stdout or "No subprocess output.")[:500],
        }

    def _execute_medea_subprocess(
        self,
        objective: str,
        config: dict[str, Any],
        python_executable: str,
        started: float,
    ) -> dict[str, Any]:
        payload = {
            "objective": objective,
            "experiment_instruction": config.get("medea_experiment_instruction") or None,
            "debate_rounds": int(config.get("medea_debate_rounds", 0)),
            "panelist_llms": config.get("medea_panelist_llms"),
            "timeout": int(config.get("medea_timeout_seconds", 1200)),
            "smoke_only": bool(config.get("medea_smoke_only", False)),
        }
        code = """
import inspect
import json
import sys
import traceback

payload = json.load(sys.stdin)
try:
    import medea
    medea_func = getattr(medea, "medea")
    if payload.get("smoke_only"):
        result = {
            "mode": "smoke_only",
            "medea_version": getattr(medea, "__version__", None),
            "medea_signature": str(inspect.signature(medea_func)),
        }
    else:
        result = medea_func(
            user_instruction=payload["objective"],
            experiment_instruction=payload.get("experiment_instruction"),
            research_planning_module=None,
            analysis_module=None,
            literature_module=None,
            debate_rounds=int(payload.get("debate_rounds") or 0),
            panelist_llms=payload.get("panelist_llms"),
            timeout=int(payload.get("timeout") or 1200),
        )
    print(json.dumps({
        "ok": True,
        "medea_version": getattr(medea, "__version__", None),
        "output": result,
    }, default=str))
except Exception as exc:
    print(json.dumps({
        "ok": False,
        "error": str(exc)[:1000],
        "traceback": traceback.format_exc(limit=8),
    }))
"""
        try:
            completed = subprocess.run(
                [python_executable, "-c", code],
                input=json.dumps(payload),
                check=False,
                capture_output=True,
                text=True,
                timeout=int(config.get("medea_subprocess_timeout_seconds", 180)),
            )
        except Exception as exc:
            return {
                "status": "failure",
                "input": {"objective": objective},
                "output": {},
                "warnings": [f"Medea subprocess failed: {str(exc)[:500]}"],
                "runtime_ms": int((time.perf_counter() - started) * 1000),
                "capability": "medea",
            }

        parsed = self._json_from_subprocess(completed.stdout)
        if parsed and parsed.get("ok"):
            return {
                "status": "success",
                "input": {"objective": objective, "python": python_executable},
                "output": parsed.get("output", {}),
                "warnings": self._subprocess_warnings(completed),
                "runtime_ms": int((time.perf_counter() - started) * 1000),
                "capability": "medea",
            }
        warning = parsed.get("error") if parsed else (completed.stderr or completed.stdout or "No subprocess output.")
        return {
            "status": "failure",
            "input": {"objective": objective, "python": python_executable},
            "output": parsed or {},
            "warnings": [f"Medea execution unavailable or failed: {warning[:500]}"],
            "runtime_ms": int((time.perf_counter() - started) * 1000),
            "capability": "medea",
        }

    def _json_from_subprocess(self, stdout: str) -> dict[str, Any] | None:
        for line in reversed((stdout or "").splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        return None

    def _subprocess_warnings(self, completed: subprocess.CompletedProcess[str]) -> list[str]:
        warnings = []
        if completed.returncode != 0:
            warnings.append(f"Subprocess exited with code {completed.returncode}.")
        if completed.stderr:
            warnings.append(completed.stderr[:500])
        return warnings

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

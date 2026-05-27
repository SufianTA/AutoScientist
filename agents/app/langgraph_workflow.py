from __future__ import annotations

import json
import os
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Callable

from app.services.llm_provider import call_llm, parse_json_object, require_real_provider
from app.services.biotruth_critic import evaluate_hypothesis
from app.services.abstention_policy import evaluate_abstention_policy
from app.services.adaptive_tool_planner import plan_adaptive_tools
from app.services.actionability_assessor import assess_actionability
from app.services.contradiction_detector import detect_contradictions
from app.services.evidence_hierarchy import summarize_evidence_hierarchy
from app.services.open_scientist_adapters import OpenScientistCapabilityRegistry
from app.services.scientific_planning import (
    build_abstention_assessment,
    build_capability_plan,
    build_claim_graph,
    build_evidence_coverage_matrix,
    classify_objective,
    compile_case_profile,
    evaluate_report_against_criteria,
    score_experiment_gates,
    type_evidence_items,
)
from app.services.scientific_strategy import (
    build_scientific_strategy,
    calibrate_scientific_strategy_with_review,
    rank_experiments_by_strategy,
)
from app.services.tooluniverse_adapter import ToolUniverseAdapter
from agents.app.graph import AgentOrchestrator
from agents.app.model_tool_runner import execute_model_tool
from agents.app.state import AgentStateName, ResearchRunState
from tools.custom_tools.clinical_status import disease_aliases, target_aliases, title_claim_type


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
        self._active_trace: list[dict[str, Any]] = []
        self._progress_lock = threading.Lock()
        self.open_scientist = OpenScientistCapabilityRegistry()

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
        raw_config = run_config or {}
        self._progress_callback = raw_config.get("_progress_callback")
        config = {key: value for key, value in raw_config.items() if not key.startswith("_")}
        config = {**config, "agent_framework": "langgraph"}
        if config.get("require_real_llm"):
            require_real_provider(config)
        state = ResearchRunState(run_id=run_id, objective_id=objective_id, objective=objective)
        state.context["agent_roster"] = self._agent_roster(config.get("agent_count", 6))
        state.context["real_mode"] = bool(config.get("real_data_enabled") and config.get("require_real_llm"))
        trace: list[dict[str, Any]] = []
        self._active_trace = trace
        try:
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
                    "agent_roster": state.context["agent_roster"],
                    "real_mode": state.context["real_mode"],
                },
            )

            if self.langgraph_available:
                state = self._run_langgraph(state, trace, config)
            else:
                state = self._run_sequential(state, trace, config)
            return state, trace
        finally:
            self._progress_callback = None

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
            ("classify_objective", self._classify_objective),
            ("plan_research", self._plan_research),
            ("find_tools", self._find_tools),
            ("execute_evidence_collection", self._execute_evidence_collection),
            ("score_evidence", self._score_evidence),
            ("generate_hypotheses", self._generate_hypotheses),
            ("debate_and_revise", self._debate_and_revise),
            ("critique_and_refine", self._critique_and_refine),
            ("propose_experiments", self._propose_experiments),
            ("generate_report", self._generate_report),
        ]

    def _emit_checkpoint(self, state: "ResearchRunState", stage: str, config: dict[str, Any]) -> None:
        """Write a partial state snapshot to the checkpoint directory for crash recovery."""
        checkpoint_dir = config.get("checkpoint_dir") or ""
        if not checkpoint_dir:
            import tempfile
            checkpoint_dir = os.path.join(tempfile.gettempdir(), "autoscientist_checkpoints")
        try:
            os.makedirs(checkpoint_dir, exist_ok=True)
            run_id = state.run_id or "unknown"
            ts = int(time.time())
            path = os.path.join(checkpoint_dir, f"checkpoint_{run_id}_{stage}_{ts}.json")
            snapshot = {
                "run_id": run_id,
                "stage": stage,
                "timestamp_utc": datetime.utcnow().isoformat(),
                "evidence_count": len(state.evidence),
                "tool_output_count": len(state.tool_outputs),
                "hypothesis_card": state.hypothesis_card,
                "experiments": state.experiments,
                "evidence_sources": [item.get("source") for item in state.evidence],
                "current_state": state.current_state.value if state.current_state else None,
            }
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(snapshot, fh, indent=2, default=str)
        except Exception:
            pass

    def _record(
        self,
        trace: list[dict[str, Any]],
        agent: str,
        state_name: str,
        input_payload: dict[str, Any],
        output: dict[str, Any],
    ) -> None:
        trace_item = {
            "agent_name": agent,
            "state_name": state_name,
            "input": input_payload,
            "output": output,
            "completed_at": datetime.utcnow().isoformat(),
        }
        with self._progress_lock:
            trace.append(trace_item)
        self._emit_callback(trace_item)

    def _emit_callback(self, trace_item: dict[str, Any]) -> None:
        callback = getattr(self, "_progress_callback", None)
        if callable(callback):
            callback(trace_item)

    def _runtime_event(
        self,
        agent: str,
        state_name: str,
        output: dict[str, Any],
        input_payload: dict[str, Any] | None = None,
    ) -> None:
        trace_item = {
            "agent_name": agent,
            "state_name": state_name,
            "input": input_payload or {},
            "output": output,
            "completed_at": datetime.utcnow().isoformat(),
            "event": True,
        }
        with self._progress_lock:
            self._active_trace.append(trace_item)
        self._emit_callback(trace_item)

    def _agent_roster(self, count: int) -> list[dict[str, Any]]:
        roles = [
            ("pi_agent", "principal investigator planning and synthesis"),
            ("finder_agent", "tool discovery and schema mapping"),
            ("tooluniverse_agent", "ToolUniverse/OpenTargets execution"),
            ("literature_agent", "PubMed evidence retrieval"),
            ("knowledge_agent", "gene, disease, and mechanism grounding"),
            ("molecule_agent", "candidate intervention and chemistry lookup"),
            ("critic_agent", "skeptical evidence scoring and claim limits"),
            ("experiment_designer_agent", "validation experiment design"),
            ("publisher_agent", "board post and final report synthesis"),
            ("safety_agent", "safety and translation gap review"),
            ("omics_agent", "pathway and omics mechanism review"),
            ("provenance_agent", "trace and reproducibility checks"),
        ]
        return [
            {"slot": index + 1, "agent_name": name, "responsibility": responsibility}
            for index, (name, responsibility) in enumerate(roles[: max(1, min(int(count), len(roles)))])
        ]

    def _llm_enabled(self, config: dict[str, Any]) -> bool:
        return config.get("llm_provider") not in {None, "", "mock"}

    def _call_llm_with_retries(self, **kwargs: Any) -> dict[str, Any]:
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                return call_llm(**kwargs)
            except Exception as exc:
                last_exc = exc
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
        raise last_exc or RuntimeError("LLM provider request failed.")

    def _llm_json(
        self,
        state: ResearchRunState,
        config: dict[str, Any],
        *,
        agent_name: str,
        task: str,
        system_prompt: str,
        prompt: str,
        max_tokens: int = 1200,
    ) -> dict[str, Any]:
        max_tokens = min(max_tokens, int(config.get("llm_max_tokens", max_tokens) or max_tokens))
        self._runtime_event(
            agent_name,
            "LLM_CALL_STARTED",
            {"task": task, "provider": config["llm_provider"], "model": config["llm_model"]},
        )
        try:
            result = self._call_llm_with_retries(
                provider=config["llm_provider"],
                model=config["llm_model"],
                api_key_env_var=config.get("llm_api_key_env_var") or None,
                base_url=config.get("llm_base_url") or None,
                system_prompt=system_prompt,
                prompt=prompt,
                temperature=0.2,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            self._runtime_event(
                agent_name,
                "LLM_CALL_FAILED",
                {"task": task, "provider": config["llm_provider"], "model": config["llm_model"], "error": str(exc)[:500]},
            )
            error_text = f"{type(exc).__name__}: {str(exc)[:1000]}"
            state.context.setdefault("warnings", []).append(
                f"LLM task {task} failed after retries; bounded fallback used: {error_text[:300]}"
            )
            state.context.setdefault("llm_calls", []).append(
                {
                    "agent_name": agent_name,
                    "task": task,
                    "provider": config["llm_provider"],
                    "model": config["llm_model"],
                    "status": "fallback_after_error",
                    "latency_ms": 0,
                    "response_excerpt": error_text[:600],
                }
            )
            return self._fallback_llm_json(task, error_text)
        try:
            result["json"] = parse_json_object(result["text"])
        except RuntimeError:
            compact_prompt = (
                f"{prompt}\n\nYour previous response was not parseable JSON. "
                "Return one compact JSON object only, with no markdown and no commentary. "
                "Keep every array to at most 5 short strings."
            )
            try:
                result = self._call_llm_with_retries(
                    provider=config["llm_provider"],
                    model=config["llm_model"],
                    api_key_env_var=config.get("llm_api_key_env_var") or None,
                    base_url=config.get("llm_base_url") or None,
                    system_prompt=system_prompt,
                    prompt=compact_prompt,
                    temperature=0.0,
                    max_tokens=min(max_tokens, 900),
                )
            except Exception as exc:
                error_text = f"{type(exc).__name__}: {str(exc)[:1000]}"
                state.context.setdefault("warnings", []).append(
                    f"LLM JSON repair for {task} failed after retries; bounded fallback used: {error_text[:300]}"
                )
                result["json"] = self._fallback_llm_json(task, error_text)
            else:
                try:
                    result["json"] = parse_json_object(result["text"])
                except RuntimeError:
                    result["json"] = self._fallback_llm_json(task, result["text"])
        self._runtime_event(
            agent_name,
            "LLM_CALL_COMPLETED",
            {
                "task": task,
                "provider": result["provider"],
                "model": result["model"],
                "latency_ms": result["latency_ms"],
                "response_excerpt": result["text"][:220],
            },
        )
        call_summary = {
            "agent_name": agent_name,
            "task": task,
            "provider": result["provider"],
            "model": result["model"],
            "status": result["status"],
            "latency_ms": result["latency_ms"],
            "response_excerpt": result["text"][:600],
        }
        state.context.setdefault("llm_calls", []).append(call_summary)
        return result["json"]

    def _llm_json_detached(
        self,
        config: dict[str, Any],
        *,
        agent_name: str,
        task: str,
        system_prompt: str,
        prompt: str,
        max_tokens: int = 1200,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        max_tokens = min(max_tokens, int(config.get("llm_max_tokens", max_tokens) or max_tokens))
        self._runtime_event(
            agent_name,
            "LLM_CALL_STARTED",
            {"task": task, "provider": config["llm_provider"], "model": config["llm_model"]},
        )
        try:
            result = self._call_llm_with_retries(
                provider=config["llm_provider"],
                model=config["llm_model"],
                api_key_env_var=config.get("llm_api_key_env_var") or None,
                base_url=config.get("llm_base_url") or None,
                system_prompt=system_prompt,
                prompt=prompt,
                temperature=0.2,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            self._runtime_event(
                agent_name,
                "LLM_CALL_FAILED",
                {"task": task, "provider": config["llm_provider"], "model": config["llm_model"], "error": str(exc)[:500]},
            )
            error_text = f"{type(exc).__name__}: {str(exc)[:1000]}"
            return self._fallback_llm_json(task, error_text), {
                "agent_name": agent_name,
                "task": task,
                "provider": config["llm_provider"],
                "model": config["llm_model"],
                "status": "fallback_after_error",
                "latency_ms": 0,
                "response_excerpt": error_text[:600],
            }
        try:
            parsed = parse_json_object(result["text"])
        except RuntimeError:
            compact_prompt = (
                f"{prompt}\n\nYour previous response was not parseable JSON. "
                "Return one compact JSON object only, with no markdown and no commentary. "
                "Keep every array to at most 5 short strings."
            )
            try:
                result = self._call_llm_with_retries(
                    provider=config["llm_provider"],
                    model=config["llm_model"],
                    api_key_env_var=config.get("llm_api_key_env_var") or None,
                    base_url=config.get("llm_base_url") or None,
                    system_prompt=system_prompt,
                    prompt=compact_prompt,
                    temperature=0.0,
                    max_tokens=min(max_tokens, 900),
                )
            except Exception as exc:
                parsed = self._fallback_llm_json(task, f"{type(exc).__name__}: {str(exc)[:1000]}")
            else:
                try:
                    parsed = parse_json_object(result["text"])
                except RuntimeError:
                    parsed = self._fallback_llm_json(task, result["text"])
        self._runtime_event(
            agent_name,
            "LLM_CALL_COMPLETED",
            {
                "task": task,
                "provider": result["provider"],
                "model": result["model"],
                "latency_ms": result["latency_ms"],
                "response_excerpt": result["text"][:220],
            },
        )
        summary = {
            "agent_name": agent_name,
            "task": task,
            "provider": result["provider"],
            "model": result["model"],
            "status": result["status"],
            "latency_ms": result["latency_ms"],
            "response_excerpt": result["text"][:600],
        }
        return parsed, summary

    def _fallback_llm_json(self, task: str, text: str) -> dict[str, Any]:
        excerpt = text.strip()[:1200]
        if task == "biomedical_context_extraction":
            context = self._heuristic_context(excerpt)
            context["llm_raw_text"] = excerpt
            context["_parse_fallback"] = True
            return context
        if task == "research_plan_generation":
            return {
                "plan_steps": [
                    "Ground disease, target, pathway, and intervention entities.",
                    "Collect live public and ToolUniverse evidence.",
                    "Score support, contradictions, and safety concerns.",
                    "Generate a bounded candidate hypothesis.",
                    "Critique claims and propose validation experiments.",
                ],
                "llm_raw_text": excerpt,
                "_parse_fallback": True,
            }
        if task == "evidence_quality_scoring":
            return {
                "label": "mechanistic_relevance",
                "score": 0.5,
                "evidence_type": "llm_unstructured_review",
                "rationale": excerpt or "LLM returned unstructured evidence review.",
                "warnings": ["LLM response was not parseable JSON; score was conservatively bounded."],
                "_parse_fallback": True,
            }
        if task == "hypothesis_synthesis":
            return {
                "title": "Candidate therapeutic hypothesis requiring validation",
                "hypothesis": "The LLM produced an unstructured hypothesis synthesis; raw text is preserved in provenance.",
                "scientific_assessment": [],
                "limitations": ["LLM response was not parseable JSON; use provenance for raw response review."],
                "llm_raw_text": excerpt,
                "_parse_fallback": True,
            }
        if task == "skeptical_critique":
            return {
                "critique_type": "unstructured_llm_critique",
                "severity": "medium",
                "critique": excerpt or "The LLM produced an unstructured critique.",
                "recommended_fix": "Review raw LLM response in provenance and rerun with a stricter model/prompt if needed.",
                "abstention_required": False,
                "claim_boundary": "candidate hypothesis; no clinical efficacy or safety claim",
                "_parse_fallback": True,
            }
        if task == "scientist_panel_position":
            return {
                "position": excerpt or "Agent returned an unstructured position.",
                "key_claims": [],
                "supporting_evidence_sources": [],
                "concerns": ["Unstructured LLM response; raw text preserved in provenance."],
                "requested_followups": [],
                "confidence_delta": 0,
                "vote": "revise",
                "_parse_fallback": True,
            }
        if task == "cross_agent_debate":
            return {
                "agreements": [],
                "disagreements": [],
                "overclaims": ["Unstructured debate response; use raw text in provenance."],
                "required_revisions": [excerpt] if excerpt else [],
                "consensus": "revise",
                "_parse_fallback": True,
            }
        if task == "pi_debate_adjudication":
            return {
                "accepted_claims": [],
                "softened_or_rejected_claims": [],
                "revised_hypothesis": "",
                "confidence_adjustment": -0.05,
                "final_confidence": None,
                "rationale": excerpt or "Unstructured PI adjudication response.",
                "_parse_fallback": True,
            }
        if task == "final_report_synthesis":
            return {
                "title": "Candidate biomedical hypothesis report",
                "summary": excerpt or "The LLM produced an unstructured final synthesis.",
                "_parse_fallback": True,
            }
        return {"llm_raw_text": excerpt, "_parse_fallback": True}

    def _extract_context(self, state: ResearchRunState, config: dict[str, Any]) -> dict[str, Any]:
        if self._llm_enabled(config):
            prompt = (
                "Extract the biomedical entities needed for autonomous evidence gathering. "
                "Return only JSON with keys: primary_genes, diseases, candidate_interventions, "
                "pathways, pubmed_queries, analysis_goal. Use empty arrays when absent. "
                "Hard limits: primary_genes <= 4, diseases <= 3, candidate_interventions <= 6, "
                "pathways <= 4, pubmed_queries <= 4. Do not add loosely related diseases or broad pathway catalogs.\n\n"
                f"Scientific problem:\n{state.objective}"
            )
            context = self._llm_json(
                state,
                config,
                agent_name="pi_agent",
                task="biomedical_context_extraction",
                system_prompt=(
                    "You are a biomedical research planner. Extract grounded entities for tool calls. "
                    "Do not invent entities that are not implied by the question."
                ),
                prompt=prompt,
                max_tokens=900,
            )
        else:
            context = self._heuristic_context(state.objective)
        normalized = self._normalize_context(context, state.objective)
        return self._merge_configured_benchmark_context(normalized, config)

    def _heuristic_context(self, objective: str) -> dict[str, Any]:
        stop = {
            "AND",
            "THE",
            "USE",
            "DO",
            "NOT",
            "DNA",
            "RNA",
            "AI",
            "LLM",
        }
        stop.update(self._DISEASE_ALIAS_EXPANSIONS.keys())
        stop.update(alias.upper() for alias in self._DISEASE_ALIAS_EXPANSIONS)
        genes = [
            match
            for match in re.findall(r"\b[A-Z][A-Z0-9]{2,9}\b", objective)
            if match not in stop and not match.startswith("HTTP")
        ]
        diseases: list[str] = []
        for pattern in [
            r"\bfor\s+[A-Z0-9-]{2,12}\s+in\s+([^.;,]+)",
            r"\bhypothesis\s+in\s+([^.;,]+)",
            r"\bfor\s+([^.;,]+)",
            r"\bin\s+([^.;,]+)",
            r"\bdriven\s+([^.;,]+)",
        ]:
            match = re.search(pattern, objective, flags=re.I)
            if not match:
                continue
            disease = self._clean_disease_phrase(match.group(1))
            if disease:
                diseases.append(disease)
        candidate_terms = re.findall(
            r"\b[A-Za-z][A-Za-z0-9-]{3,}(?:mab|nib|tinib|limus|siran|statin|caftor)\b",
            objective,
            re.I,
        )
        intervention_classes = re.findall(
            r"\b(?:inhibitor|antibody|siRNA|ASO|antisense|CRISPR|base editing|prime editing|gene therapy|small molecule)\b",
            objective,
            re.I,
        )
        candidates = [*candidate_terms, *intervention_classes]
        if not diseases:
            diseases.extend(self._vocabulary_scan_diseases(objective))
        queries: list[str] = []
        if genes and diseases:
            queries.append(f"{genes[0]} {diseases[0]} mechanism")
            queries.append(f"{genes[0]} {diseases[0]} safety therapeutic")
            if len(genes) > 1:
                queries.append(f"{genes[1]} {diseases[0]} mechanism")
        elif genes:
            queries.append(f"{genes[0]} mechanism")
            queries.append(f"{genes[0]} therapeutic target")
        elif diseases:
            queries.append(f"{diseases[0]} target therapy mechanism")
            queries.append(f"{diseases[0]} novel therapeutic")
        else:
            short = objective[:60].strip()
            if short:
                queries.append(short)
        return {
            "primary_genes": list(dict.fromkeys(genes))[:4],
            "diseases": list(dict.fromkeys(diseases))[:3],
            "candidate_interventions": list(dict.fromkeys(candidates))[:6],
            "pathways": [],
            "pubmed_queries": queries[:4],
            "analysis_goal": objective,
            "extraction_method": "heuristic",
        }

    def _clean_disease_phrase(self, value: str) -> str:
        cleaned = re.split(
            r"\b(?:using|use|include|including|require|with|by|from|and\s+produce|produce|propose|ranked|strategy|rather\s+than)\b",
            value,
            maxsplit=1,
            flags=re.I,
        )[0].strip(" .;:,")
        cleaned = re.sub(r"^(?:analyze|assess|evaluate|generate|build|design)\s+", "", cleaned, flags=re.I)
        cleaned = re.sub(r"\b(?:acquired|complex|candidate|therapeutic)\s+(?=resistance|hypothesis|strategy)", "", cleaned, flags=re.I)
        gene_then_disease = re.match(r"^([A-Z0-9-]{2,12})\s+in\s+(.+)$", cleaned, flags=re.I)
        if gene_then_disease:
            cleaned = gene_then_disease.group(2).strip(" .;:,")
        cell_context = re.search(r"\s+in\s+(.+)$", cleaned, flags=re.I)
        if cell_context and re.search(r"\b(cell|cells|fibroblast|synovial|tissue|organoid)\b", cell_context.group(1), flags=re.I):
            cleaned = cleaned[: cell_context.start()].strip(" .;:,")
        cleaned = re.sub(r"^(the|a|an)\s+", "", cleaned, flags=re.I)
        if not cleaned or len(cleaned.split()) > 8:
            return ""
        if re.fullmatch(r"[A-Z0-9-]{2,12}", cleaned):
            return ""
        return cleaned

    def _normalize_context(self, context: dict[str, Any], objective: str) -> dict[str, Any]:
        genes = self._string_list(context.get("primary_genes"))
        diseases = []
        for disease in self._string_list(context.get("diseases")):
            cleaned = self._clean_disease_phrase(
                re.sub(r"^[A-Z0-9]+-driven\s+", "", disease, flags=re.I).strip()
            )
            if cleaned:
                diseases.append(cleaned)
        explicit_diseases = self._heuristic_context(objective).get("diseases", [])
        diseases = list(
            dict.fromkeys(
                [
                    *explicit_diseases,
                    *[
                        disease
                        for disease in diseases
                        if "heterotopic ossification" not in disease.lower()
                    ],
                ]
            )
        )
        explicit_genes = self._explicit_gene_symbols(objective)
        genes = self._clean_primary_genes([*explicit_genes, *genes], diseases, objective)[:4]
        pubmed_queries = self._clean_pubmed_queries(self._string_list(context.get("pubmed_queries"))[:4])
        normalized = {
            "primary_genes": genes,
            "diseases": self._prioritize_diseases(diseases, objective)[:2],
            "candidate_interventions": self._string_list(context.get("candidate_interventions"))[:6],
            "pathways": self._string_list(context.get("pathways"))[:4],
            "pubmed_queries": pubmed_queries,
            "analysis_goal": str(context.get("analysis_goal") or objective),
            "extraction_method": context.get("extraction_method", "llm"),
        }
        if not normalized["pubmed_queries"]:
            normalized["pubmed_queries"] = self._default_pubmed_queries(normalized, objective)
        else:
            normalized["pubmed_queries"] = [
                re.sub(r"([A-Z0-9]+)\s+\1-driven\s+", r"\1 ", query, flags=re.I)
                for query in normalized["pubmed_queries"]
            ]
        return normalized

    def _prioritize_diseases(self, diseases: list[str], objective: str) -> list[str]:
        vocab = [self._expand_disease_alias(v) for v in self._vocabulary_scan_diseases(objective)]
        clean = []
        for disease in diseases:
            disease = self._expand_disease_alias(self._clean_disease_phrase(disease))
            if not disease or self._looks_like_task_instruction(disease):
                continue
            clean.append(disease)
        lower_to_original = {d.lower(): d for d in clean}
        ordered = [lower_to_original[v.lower()] for v in vocab if v.lower() in lower_to_original]
        ordered.extend([d for d in clean if d not in ordered])
        return list(dict.fromkeys(ordered))

    _DISEASE_ALIAS_EXPANSIONS: dict[str, str] = {
        "nsclc": "non-small cell lung cancer",
        "sclc": "small cell lung cancer",
        "hcc": "hepatocellular carcinoma",
        "rcc": "renal cell carcinoma",
        "copd": "chronic obstructive pulmonary disease",
        "nash": "non-alcoholic steatohepatitis",
    }

    def _expand_disease_alias(self, disease: str) -> str:
        return self._DISEASE_ALIAS_EXPANSIONS.get(str(disease).lower(), disease)

    def _clean_primary_genes(self, genes: list[str], diseases: list[str], objective: str) -> list[str]:
        disease_aliases = {alias.upper() for alias in self._DISEASE_ALIAS_EXPANSIONS}
        disease_terms = {d.lower() for d in diseases}
        objective_lower = objective.lower()
        cleaned = []
        for gene in self._string_list(genes):
            upper = gene.upper()
            alias_disease = self._DISEASE_ALIAS_EXPANSIONS.get(gene.lower())
            if upper in disease_aliases and (
                gene.lower() in objective_lower
                or (alias_disease and alias_disease.lower() in disease_terms)
            ):
                continue
            cleaned.append(gene)
        return list(dict.fromkeys(cleaned))

    def _merge_configured_benchmark_context(
        self,
        context: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        benchmark_task = config.get("benchmark_task")
        if not isinstance(benchmark_task, dict):
            return context
        gene = str(benchmark_task.get("gene_symbol") or "").strip()
        disease = str(benchmark_task.get("disease_name") or "").strip()
        if gene:
            context["primary_genes"] = list(dict.fromkeys([gene, *context.get("primary_genes", [])]))[:4]
        if disease:
            context["diseases"] = list(dict.fromkeys([disease, *context.get("diseases", [])]))[:3]
        if gene and disease:
            required_queries = [
                f"{gene} {disease} mechanism",
                f"{gene} {disease} target validation",
                f"{gene} {disease} clinical precedence response",
                f"{gene} {disease} safety adverse effect",
                f"{gene} {disease} failed trial not associated",
            ]
            existing = list(context.get("pubmed_queries", []))
            context["pubmed_queries"] = list(dict.fromkeys([*required_queries, *existing]))[:7]
        context["benchmark_task"] = {
            key: benchmark_task.get(key)
            for key in (
                "id",
                "case_id",
                "template_id",
                "domain",
                "gene_symbol",
                "disease_name",
                "target_ensembl_id",
                "disease_efo_id",
                "expected_capabilities",
                "public_labels",
                "public_context",
            )
            if benchmark_task.get(key) not in (None, "", [])
        }
        return context

    def _benchmark_public_evidence_items(
        self,
        config: dict[str, Any],
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        benchmark_task = config.get("benchmark_task")
        if not isinstance(benchmark_task, dict):
            benchmark_task = context.get("benchmark_task")
        if not isinstance(benchmark_task, dict):
            return []
        labels = benchmark_task.get("public_labels") if isinstance(benchmark_task.get("public_labels"), dict) else {}
        public_context = (
            benchmark_task.get("public_context")
            if isinstance(benchmark_task.get("public_context"), dict)
            else {}
        )
        gene = str(benchmark_task.get("gene_symbol") or self._primary_target_from_context(context)).strip()
        disease = str(benchmark_task.get("disease_name") or self._primary_disease_from_context(context)).strip()
        evidence: list[dict[str, Any]] = []
        if labels:
            association_status = labels.get("open_targets_association_status")
            association_score = labels.get("open_targets_association_score")
            rank = labels.get("open_targets_association_rank")
            matched_disease = labels.get("open_targets_matched_disease_name") or disease
            pubmed_count = labels.get("pubmed_gene_disease_count")
            availability = labels.get("evidence_availability")
            evidence.append(
                {
                    "source": "Benchmark public context: Open Targets target-disease association",
                    "text": (
                        f"Public Open Targets context for {gene} and {disease}: association status "
                        f"{association_status}, association score {association_score}, rank {rank}, matched disease "
                        f"{matched_disease}, PubMed gene-disease count {pubmed_count}, evidence availability "
                        f"{availability}. Open Targets scores are ranking heuristics and PubMed counts are "
                        "availability signals, so this supports target-disease grounding but not efficacy or safety."
                    ),
                    "structured": {
                        "evidence_type": "target_disease_association",
                        "public_labels": labels,
                        "source_policy": "live_public_benchmark_context",
                    },
                }
            )
        target = {}
        target_context = public_context.get("open_targets_target") or public_context.get("open_targets")
        if isinstance(target_context, dict):
            target = target_context.get("target") if isinstance(target_context.get("target"), dict) else {}
        tractability = target.get("tractability") if isinstance(target, dict) else []
        positive_tractability = [
            item
            for item in tractability or []
            if isinstance(item, dict)
            and item.get("value") is True
            and str(item.get("label") or "").lower()
            in {"approved drug", "advanced clinical", "phase 1 clinical", "clinical precedence"}
        ]
        if positive_tractability:
            labels_text = "; ".join(
                f"{item.get('label')} ({item.get('modality')})" for item in positive_tractability[:6]
            )
            evidence.append(
                {
                    "source": "Benchmark public context: Open Targets target tractability",
                    "text": (
                        f"Open Targets target metadata for {gene} reports clinical or tractability precedence: "
                        f"{labels_text}. This is target-level precedence and must be separated from "
                        f"disease-specific efficacy claims for {disease}."
                    ),
                    "structured": {
                        "evidence_type": "clinical_precedence",
                        "target": target,
                        "positive_tractability": positive_tractability,
                        "source_policy": "live_public_benchmark_context",
                    },
                }
            )
        return evidence

    def _primary_target_from_context(self, context: dict[str, Any]) -> str:
        genes = context.get("primary_genes", [])
        return str(genes[0]) if genes else "target"

    def _primary_disease_from_context(self, context: dict[str, Any]) -> str:
        diseases = context.get("diseases", [])
        return str(diseases[0]) if diseases else "disease"

    def _string_list(self, value: Any) -> list[str]:
        if not value:
            return []
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    def _clean_pubmed_queries(self, queries: list[str]) -> list[str]:
        cleaned: list[str] = []
        for query in queries:
            normalized = re.sub(r"\s+", " ", str(query)).strip()
            if not normalized:
                continue
            if self._looks_like_serialized_context(normalized):
                continue
            if len(normalized) < 3 or len(normalized) > 180:
                continue
            if self._looks_like_task_instruction(normalized):
                continue
            cleaned.append(normalized)
        return list(dict.fromkeys(cleaned))[:4]

    _TASK_INSTRUCTION_PREFIXES = (
        "use single-cell",
        "use autoscientist",
        "use rnaseq",
        "use omics",
        "use single",
        "assess the",
        "generate a target",
        "generate a hypothesis",
        "identify the best",
        "evaluate the",
        "prioritize the",
        "use public biomedical",
    )

    _DISEASE_SUFFIXES: tuple[str, ...] = (
        "cancer", "carcinoma", "adenocarcinoma", "lymphoma", "leukemia",
        "leukaemia", "melanoma", "sarcoma", "glioma", "glioblastoma",
        "myeloma", "neoplasm", "tumor", "tumour", "blastoma", "mesothelioma",
        "cholangiocarcinoma", "malignancy",
    )

    _DISEASE_VOCAB: tuple[str, ...] = (
        "nsclc", "sclc", "dlbcl", "aml", "cll", "cml", "hcc", "rcc",
        "multiple myeloma", "hodgkin lymphoma", "glioblastoma multiforme",
        "neuroblastoma", "retinoblastoma", "hepatocellular carcinoma",
        "non-small cell lung cancer", "small cell lung cancer",
        "colorectal cancer", "pancreatic cancer", "breast cancer",
        "ovarian cancer", "prostate cancer", "thyroid cancer",
        "renal cell carcinoma", "urothelial carcinoma", "bladder cancer",
        "gastric cancer", "esophageal cancer", "cervical cancer",
        "endometrial cancer", "head and neck cancer",
        "rheumatoid arthritis", "systemic lupus erythematosus", "lupus",
        "psoriasis", "atopic dermatitis", "crohn's disease", "crohn disease",
        "ulcerative colitis", "multiple sclerosis", "systemic sclerosis",
        "sjogren syndrome", "ankylosing spondylitis",
        "heart failure", "myocardial infarction", "atrial fibrillation",
        "type 2 diabetes", "type 1 diabetes", "hypercholesterolemia",
        "non-alcoholic steatohepatitis", "nash", "nafld",
        "pulmonary fibrosis", "idiopathic pulmonary fibrosis", "asthma",
        "chronic obstructive pulmonary disease", "copd", "cystic fibrosis",
        "sickle cell disease", "thalassemia", "hemophilia",
        "gaucher disease", "fabry disease",
        "alzheimer's disease", "alzheimer disease", "parkinson's disease",
        "parkinson disease", "huntington disease", "huntington's disease",
        "amyotrophic lateral sclerosis", "als", "spinal muscular atrophy",
        "epilepsy", "schizophrenia", "major depressive disorder",
    )

    def _looks_like_task_instruction(self, value: str) -> bool:
        if len(value) <= 60:
            return False
        lowered = value.lower()
        return any(lowered.startswith(p) for p in self._TASK_INSTRUCTION_PREFIXES)

    def _looks_like_serialized_context(self, value: str) -> bool:
        stripped = value.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            return True
        lowered = stripped.lower()
        context_keys = (
            '"primary_genes"',
            '"diseases"',
            '"candidate_interventions"',
            '"pathways"',
            '"pubmed_queries"',
            "'primary_genes'",
            "'diseases'",
        )
        if any(key in lowered for key in context_keys):
            return True
        return stripped.count("{") + stripped.count("}") + stripped.count("[") + stripped.count("]") >= 2

    def _vocabulary_scan_diseases(self, objective: str) -> list[str]:
        """Return recognizable disease/condition terms found in the objective text."""
        lowered = objective.lower()
        found: list[str] = []
        for term in self._DISEASE_VOCAB:
            if term in lowered:
                found.append(term)
        for suffix in self._DISEASE_SUFFIXES:
            pattern = rf"\b(?:[a-z]{{2,}}(?:[- ][a-z]{{2,}}){{0,3}} )?{re.escape(suffix)}\b"
            for m in re.finditer(pattern, lowered):
                phrase = m.group(0).strip()
                if phrase and phrase not in found and 2 <= len(phrase.split()) <= 5:
                    found.append(phrase)
        return list(dict.fromkeys(found))[:3]

    def _sanitize_pubmed_query(self, query: str, genes: list[str], diseases: list[str]) -> str:
        """Validate a PubMed query before dispatch; replace task-instruction leaks with focused terms."""
        q = re.sub(r"\s+", " ", str(query)).strip()
        if not q or len(q) < 3:
            return ""
        if self._looks_like_serialized_context(q):
            return ""
        if self._looks_like_task_instruction(q):
            if genes and diseases:
                return f"{genes[0]} {diseases[0]} mechanism"
            if genes:
                return f"{genes[0]} mechanism"
            if diseases:
                return f"{diseases[0]} target therapy"
            return ""
        return q

    def _default_pubmed_queries(self, context: dict[str, Any], objective: str) -> list[str]:
        genes = context.get("primary_genes", [])
        diseases = context.get("diseases", [])
        pathways = context.get("pathways", [])
        pieces = [*genes, *diseases] or [*genes, *pathways]
        base_query = " ".join(str(piece) for piece in pieces if str(piece).strip()).strip()
        if not base_query:
            vocab = self._vocabulary_scan_diseases(objective)
            if genes and vocab:
                base_query = f"{genes[0]} {vocab[0]}"
            elif genes:
                base_query = genes[0]
            elif vocab:
                base_query = vocab[0]
            else:
                base_query = objective[:60].strip()
        return [
            f"{base_query} mechanism",
            f"{base_query} therapeutic safety",
            f"{base_query} candidate intervention",
        ]

    def _evidence_digest(
        self,
        state: ResearchRunState,
        limit: int = 12,
        text_chars: int = 900,
    ) -> list[dict[str, Any]]:
        def rank(item: dict[str, Any]) -> tuple[float, int]:
            score = item.get("score", {}).get("score")
            try:
                numeric_score = float(score)
            except (TypeError, ValueError):
                numeric_score = 0.0
            source = str(item.get("source", ""))
            source_bonus = 0
            if source.startswith("Benchmark public context"):
                source_bonus += 5
            if "ToolUniverse" in source or "OpenTargets" in source:
                source_bonus += 2
            if source.startswith("PubMed"):
                source_bonus += 1
            if source == "NCBI Gene":
                source_bonus += 1
            return (numeric_score + source_bonus / 10, source_bonus)

        digest = []
        for item in sorted(state.evidence, key=rank, reverse=True)[:limit]:
            structured = item.get("structured", {})
            citations = []
            for article in structured.get("articles", [])[:3] if isinstance(structured, dict) else []:
                citations.append(
                    {
                        "pmid": article.get("pmid"),
                        "title": article.get("title"),
                        "url": article.get("url"),
                    }
                )
            digest.append(
                {
                    "source": item.get("source"),
                    "label": item.get("score", {}).get("label"),
                    "score": item.get("score", {}).get("score"),
                    "text": str(item.get("text", ""))[:text_chars],
                    "citations": citations,
                }
            )
        return digest

    def _target_aliases(self, target: str) -> set[str]:
        return target_aliases(target)

    def _disease_aliases(self, disease: str) -> set[str]:
        return disease_aliases(disease)

    def _pubmed_title_relevance(self, item: dict[str, Any], state: ResearchRunState | None) -> dict[str, Any]:
        structured = item.get("structured", {}) if isinstance(item.get("structured"), dict) else {}
        articles = structured.get("articles") or []
        if not articles:
            return {
                "relevant": False,
                "target_hits": 0,
                "disease_hits": 0,
                "clinical_hits": 0,
                "mechanism_hits": 0,
                "safety_hits": 0,
            }
        target = self._primary_target(state) if state is not None else ""
        disease = self._primary_disease(state) if state is not None else ""
        target_aliases = self._target_aliases(target)
        disease_aliases = self._disease_aliases(disease)
        target_hits = 0
        disease_hits = 0
        clinical_hits = 0
        mechanism_hits = 0
        safety_hits = 0
        for article in articles:
            text = " ".join(
                str(article.get(key) or "")
                for key in ("title", "abstract", "journal")
            ).lower()
            if any(alias in text for alias in target_aliases):
                target_hits += 1
            if any(alias in text for alias in disease_aliases):
                disease_hits += 1
            claim_type = title_claim_type(text)
            if claim_type == "clinical_precedence":
                clinical_hits += 1
            if claim_type == "mechanistic":
                mechanism_hits += 1
            if claim_type == "safety":
                safety_hits += 1
        return {
            "relevant": target_hits > 0 and disease_hits > 0,
            "target_hits": target_hits,
            "disease_hits": disease_hits,
            "clinical_hits": clinical_hits,
            "mechanism_hits": mechanism_hits,
            "safety_hits": safety_hits,
        }

    def _deterministic_score_evidence_item(
        self,
        item: dict[str, Any],
        hypothesis_seed: str,
        state: ResearchRunState | None = None,
    ) -> dict[str, Any]:
        if item.get("source", "").startswith("PubMed:") and item.get("structured", {}).get("count") == 0:
            return {
                "label": "irrelevant",
                "score": 0.1,
                "evidence_type": "literature_search",
                "rationale": "The live PubMed query returned zero records, so it cannot support the hypothesis.",
                "warnings": ["Absence of retrieved records is not evidence against the hypothesis."],
            }
        source = str(item.get("source", ""))
        if source.startswith("Benchmark public context"):
            structured = item.get("structured", {}) if isinstance(item.get("structured"), dict) else {}
            evidence_type = str(structured.get("evidence_type") or "public_context")
            labels = structured.get("public_labels", {}) if isinstance(structured.get("public_labels"), dict) else {}
            association_score = labels.get("open_targets_association_score")
            try:
                numeric_score = float(association_score)
            except (TypeError, ValueError):
                numeric_score = 0.0
            if evidence_type == "target_disease_association" and labels.get("open_targets_association_status") == "matched":
                return {
                    "label": "strong_support" if numeric_score >= 0.35 else "weak_support",
                    "score": max(0.65, min(0.9, numeric_score + 0.25)),
                    "evidence_type": "target_disease_association",
                    "rationale": "Public Open Targets target-disease association was explicitly retrieved for the benchmark case.",
                    "warnings": ["Association scores rank evidence and are not clinical efficacy claims."],
                }
            if evidence_type == "clinical_precedence":
                return {
                    "label": "mechanistic_relevance",
                    "score": 0.68,
                    "evidence_type": "clinical_precedence",
                    "rationale": "Open Targets target metadata indicates target-level clinical or tractability precedence.",
                    "warnings": ["Target-level precedence must be separated from disease-specific efficacy claims."],
                }
        if source.startswith("PubMed:"):
            relevance = self._pubmed_title_relevance(item, state)
            if not relevance["relevant"]:
                return {
                    "label": "irrelevant",
                    "score": 0.2,
                    "evidence_type": "literature_search",
                    "rationale": (
                        "PubMed returned records, but retrieved titles did not jointly mention the target and "
                        "disease context; this cannot be treated as target-disease support."
                    ),
                    "warnings": [f"target_hits={relevance['target_hits']}; disease_hits={relevance['disease_hits']}"],
                }
            if relevance["clinical_hits"]:
                return {
                    "label": "strong_support",
                    "score": 0.78,
                    "evidence_type": "clinical_precedence_literature",
                    "rationale": "Retrieved PubMed titles jointly match the target/disease context and include clinical or treatment language.",
                    "warnings": ["Article titles still require manual inspection before efficacy claims."],
                }
            if relevance["safety_hits"]:
                return {
                    "label": "safety_concern",
                    "score": 0.7,
                    "evidence_type": "safety_literature",
                    "rationale": "Retrieved PubMed titles jointly match the target/disease context and include safety or adverse-event language.",
                    "warnings": ["Safety evidence requires manual review before translation claims."],
                }
            if relevance["mechanism_hits"]:
                return {
                    "label": "mechanistic_relevance",
                    "score": 0.62,
                    "evidence_type": "mechanistic_literature",
                    "rationale": "Retrieved PubMed titles jointly match the target/disease context and include mechanism/pathway language.",
                    "warnings": ["Mechanistic literature supports plausibility, not efficacy."],
                }
        score = self.tools["evidence_quality_scorer_tool"].run(
            {
                "hypothesis": hypothesis_seed,
                "evidence_text": item["text"],
                "evidence_source": item["source"],
            }
        ).model_dump()
        if state is not None:
            state.tool_outputs.append(
                {
                    "tool_name": "evidence_quality_scorer_tool",
                    "tool_source": "custom",
                    "result": score,
                }
            )
        self._runtime_event(
            "critic_agent",
            "TOOL_CALL_COMPLETED",
            {
                "tool_name": "evidence_quality_scorer_tool",
                "tool_source": "custom",
                "status": score.get("status"),
                "latency_ms": score.get("runtime_ms"),
            },
            score.get("input", {}),
        )
        return score["output"]

    def _score_evidence_with_llm_batch(
        self,
        state: ResearchRunState,
        config: dict[str, Any],
        hypothesis_seed: str,
    ) -> list[dict[str, Any]]:
        compact_items = [
            {
                "index": index,
                "source": item.get("source"),
                "text": str(item.get("text", ""))[:650],
            }
            for index, item in enumerate(state.evidence)
        ]
        try:
            scoring_json = self._llm_json(
                state,
                config,
                agent_name="critic_agent",
                task="evidence_quality_scoring",
                system_prompt=(
                    "You are a skeptical biomedical evidence evaluator. Score each evidence item for how it "
                    "supports a candidate hypothesis. Be conservative and do not overclaim."
                ),
                prompt=(
                    "Return only JSON with key scores. scores must be an array with one object per evidence item. "
                    "Each object needs index, label, score, evidence_type, rationale, warnings. "
                    "Allowed labels: strong_support, weak_support, mechanistic_relevance, irrelevant, "
                    "contradicts, safety_concern. Scores must be 0-1. Keep rationales short.\n"
                    f"Hypothesis: {hypothesis_seed}\n"
                    f"Evidence items: {json.dumps(compact_items, default=str)[:9000]}"
                ),
                max_tokens=1400,
            )
        except Exception as exc:
            state.context.setdefault("warnings", []).append(
                f"LLM evidence batch scoring failed; deterministic fallback used: {str(exc)[:300]}"
            )
            scoring_json = {"scores": []}
        scores_by_index: dict[int, dict[str, Any]] = {}
        for score in scoring_json.get("scores", []) if isinstance(scoring_json.get("scores"), list) else []:
            try:
                index = int(score.get("index"))
                score["score"] = float(score.get("score", 0.0))
            except (TypeError, ValueError):
                continue
            scores_by_index[index] = {
                "label": score.get("label", "mechanistic_relevance"),
                "score": max(0.0, min(1.0, score["score"])),
                "evidence_type": score.get("evidence_type", "biomedical_evidence"),
                "rationale": score.get("rationale", "Batch LLM scorer produced a bounded evidence assessment."),
                "warnings": score.get("warnings", []),
            }
        scored = []
        for index, item in enumerate(state.evidence):
            score_output = scores_by_index.get(index)
            if score_output is None:
                score_output = self._deterministic_score_evidence_item(item, hypothesis_seed, state)
            scored.append({**item, "score": score_output})
        return scored

    def _explicit_gene_symbols(self, objective: str) -> list[str]:
        stop = {"AND", "THE", "USE", "NOT", "DNA", "RNA", "LLM"}
        stop.update(alias.upper() for alias in self._DISEASE_ALIAS_EXPANSIONS)
        genes = [
            value
            for value in re.findall(r"\b[A-Z][A-Z0-9]{2,9}\b", objective)
            if value not in stop and not value.startswith("HTTP")
        ]
        return list(dict.fromkeys(genes))[:4]

    def _primary_target(self, state: ResearchRunState) -> str:
        genes = state.context.get("biomedical_context", {}).get("primary_genes", [])
        return genes[0] if genes else "disease-relevant target/pathway"

    def _primary_disease(self, state: ResearchRunState) -> str:
        diseases = state.context.get("biomedical_context", {}).get("diseases", [])
        if diseases:
            # Prefer entries that look like actual disease names over mechanism descriptions.
            # Skip strings that sound like mechanisms/pathways/interventions rather than diseases.
            _MECHANISM_TERMS = (
                "pathway", "inhibition", "signaling", "modulation", "targeting",
                "activation", "mutation", "knockout", "overexpression", "deficiency",
                "therapy", "treatment", "strategy", "approach",
            )
            disease_candidates = [
                d for d in diseases
                if not any(t in d.lower() for t in _MECHANISM_TERMS)
            ]
            # Also prefer entries that match vocabulary scan
            vocab = self._vocabulary_scan_diseases(state.objective)
            vocab_set = {v.lower() for v in vocab}
            vocab_matches = [d for d in disease_candidates if d.lower() in vocab_set]
            if vocab_matches:
                return vocab_matches[0]
            if disease_candidates:
                return disease_candidates[0]
            # Fall back to the raw first entry if all entries look like mechanisms
            return diseases[0]
        vocab = self._vocabulary_scan_diseases(state.objective)
        return vocab[0] if vocab else "the disease context"

    def _classify_objective(
        self,
        state: ResearchRunState,
        trace: list[dict[str, Any]],
        config: dict[str, Any],
    ) -> ResearchRunState:
        state.current_state = AgentStateName.CLASSIFY_OBJECTIVE
        biomedical_context = self._extract_context(state, config)
        state.context["biomedical_context"] = biomedical_context
        if isinstance(biomedical_context.get("benchmark_task"), dict):
            state.context["benchmark_task"] = biomedical_context["benchmark_task"]
        classification = classify_objective(state.objective, biomedical_context).model_dump()
        case_profile = compile_case_profile(state.objective, classification, biomedical_context)
        capability_plan = build_capability_plan(classification, case_profile)
        criteria_result = self.open_scientist.generate_evaluation_criteria(state.objective, classification, config)
        state.context["objective_classification"] = classification
        state.context["case_profile"] = case_profile
        state.context["capability_plan"] = capability_plan
        state.context["evaluation_criteria"] = criteria_result["criteria"]
        state.context["open_scientist_health"] = self.open_scientist.health()
        self._record(
            trace,
            "pi_agent",
            state.current_state.value,
            {"objective": state.objective, "run_config": config},
            {
                "biomedical_context": biomedical_context,
                "objective_classification": classification,
                "case_profile": case_profile,
                "capability_plan": capability_plan,
                "evaluation_criteria": criteria_result["criteria"],
                "open_scientist_health": state.context["open_scientist_health"],
            },
        )
        return state

    def _plan_research(
        self,
        state: ResearchRunState,
        trace: list[dict[str, Any]],
        config: dict[str, Any],
    ) -> ResearchRunState:
        state.current_state = AgentStateName.PLAN_RESEARCH
        biomedical_context = state.context.get("biomedical_context") or self._extract_context(state, config)
        state.context["biomedical_context"] = biomedical_context
        if self._llm_enabled(config):
            plan_json = self._llm_json(
                state,
                config,
                agent_name="pi_agent",
                task="research_plan_generation",
                system_prompt=(
                    "You are a skeptical biomedical principal investigator. Create a tool-grounded "
                    "plan for evidence gathering, hypothesis generation, critique, and validation. "
                    "Avoid clinical claims unless direct evidence is available."
                ),
                prompt=(
                    "Return only JSON with key plan_steps as an array of 5-8 concise steps. "
                    f"Scientific problem: {state.objective}\n"
                    f"Extracted context: {json.dumps(biomedical_context, indent=2)}"
                ),
                max_tokens=900,
            )
            state.plan = self._string_list(plan_json.get("plan_steps"))
        if not state.plan:
            state.plan = [
                "Extract disease, target, pathway, and intervention entities from the objective.",
                "Collect live gene, disease, literature, compound, and ToolUniverse/OpenTargets evidence.",
                "Generate a candidate therapeutic or mechanistic hypothesis with explicit uncertainty.",
                "Score evidence and separate support from safety, translation, and contradiction gaps.",
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
                "biomedical_context": biomedical_context,
                "agent_roster": state.context.get("agent_roster", []),
                "agent_count": config.get("agent_count", 6),
                "evidence_strictness": config.get("evidence_strictness", "balanced"),
                "llm_provider": config.get("llm_provider", "mock"),
                "llm_model": config.get("llm_model", "mock-scientist"),
                "objective_classification": state.context.get("objective_classification", {}),
                "capability_plan": state.context.get("capability_plan", {}),
                "evaluation_criteria_count": len(state.context.get("evaluation_criteria", [])),
                "llm_calls": state.context.get("llm_calls", []),
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
        if config.get("real_data_enabled"):
            state.selected_tools = [
                "ncbi_gene_profile_tool",
                "pubmed_literature_search_tool",
                "pubchem_candidate_lookup_tool",
                "clinical_trials_search_tool",
                "reactome_pathway_search_tool",
                "openfda_adverse_event_tool",
                "OpenTargets_get_disease_id_description_by_name",
                "OpenTargets_get_drug_chembId_by_generic_name",
                "evidence_quality_scorer_tool",
                "hypothesis_card_generator_tool",
                "experiment_recommendation_tool",
                *[tool["name"] for tool in config.get("model_tool_configs", [])],
            ]
        else:
            state.selected_tools = [
                "evidence_quality_scorer_tool",
                "hypothesis_card_generator_tool",
                "experiment_recommendation_tool",
                *[tool["name"] for tool in config.get("model_tool_configs", [])],
            ]
        routed_capabilities = state.context.get("objective_classification", {}).get("required_capabilities", [])
        capability_tools = []
        if "txagent" in routed_capabilities:
            capability_tools.append("txagent_agent")
        if "clawinstitute_board" in routed_capabilities:
            capability_tools.append("clawinstitute_board_publisher")
        state.selected_tools = list(dict.fromkeys([*state.selected_tools, *capability_tools]))
        policy_advice = self._sciflow_policy_advice(state, config)
        promoted_tools = self._promoted_policy_tools(policy_advice, state.selected_tools, config)
        if promoted_tools:
            state.selected_tools = list(dict.fromkeys([*state.selected_tools, *promoted_tools]))
        execution_policy = self._build_sciflow_execution_policy(policy_advice, state, config)
        state.context["sciflow_execution_policy"] = execution_policy
        self._record(
            trace,
            "finder_agent",
            state.current_state.value,
            {
                "objective": state.objective,
                "biomedical_context": state.context.get("biomedical_context", {}),
                "objective_classification": state.context.get("objective_classification", {}),
                "available_custom_tools": sorted(self.tools.keys()),
                "available_open_scientist_capabilities": self.open_scientist.health(),
            },
            {
                "selected_tools": state.selected_tools,
                "sciflow_policy": policy_advice,
                "policy_promoted_tools": promoted_tools,
                "sciflow_execution_policy": execution_policy,
                "capability_plan": state.context.get("capability_plan", {}),
                "selection_policy": (
                    "live public APIs plus ToolUniverse/OpenTargets, SciFlow policy advice, and configured model tools"
                    if config.get("real_data_enabled")
                    else "local deterministic planning, SciFlow policy advice, scoring tools, and configured model tools"
                ),
            },
        )
        return state

    def _sciflow_policy_advice(self, state: ResearchRunState, config: dict[str, Any]) -> dict[str, Any]:
        if not config.get("sciflow_policy_enabled"):
            return {"enabled": False, "status": "disabled", "predictions": []}
        context = {
            "objective": state.objective,
            "state_name": "TOOL_SELECTION",
            "previous_state": AgentStateName.FIND_TOOLS.value,
            "biomedical_context": state.context.get("biomedical_context", {}),
            "objective_classification": state.context.get("objective_classification", {}),
            "run_config": {
                "real_data_enabled": config.get("real_data_enabled"),
                "llm_provider": config.get("llm_provider"),
                "agent_count": config.get("agent_count"),
            },
        }
        try:
            model = self._load_sciflow_policy_model(config)
            if model is None:
                return {"enabled": True, "status": "no_model_available", "predictions": []}
            predictions = self._predict_sciflow_actions(model, context)
            advice = {
                "enabled": True,
                "status": "success",
                "model_id": model.get("id"),
                "model_type": model.get("model_type"),
                "model_path": model.get("artifact_path"),
                "predictions": predictions,
            }
            state.context["sciflow_policy"] = advice
            return advice
        except Exception as exc:
            advice = {"enabled": True, "status": "failed", "error": str(exc)[:500], "predictions": []}
            state.context["sciflow_policy"] = advice
            return advice

    def _load_sciflow_policy_model(self, config: dict[str, Any]) -> dict[str, Any] | None:
        if config.get("sciflow_policy_model_path"):
            return {
                "id": config.get("sciflow_policy_model_id") or "external_sciflow_policy",
                "model_type": config.get("sciflow_policy_model_type") or "",
                "artifact_path": config["sciflow_policy_model_path"],
            }
        from app.db.models import WorkflowPolicyModel
        from app.db.session import SessionLocal

        db = SessionLocal()
        try:
            model_id = config.get("sciflow_policy_model_id")
            model = db.get(WorkflowPolicyModel, model_id) if model_id else None
            if model is None:
                model = db.query(WorkflowPolicyModel).order_by(WorkflowPolicyModel.created_at.desc()).first()
            if model is None:
                return None
            return {
                "id": model.id,
                "model_type": model.model_type,
                "artifact_path": model.artifact_path,
            }
        finally:
            db.close()

    def _predict_sciflow_actions(
        self,
        model: dict[str, Any],
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        from app.services.neural_workflow_policy import MODEL_TYPE as NEURAL_POLICY_TYPE
        from app.services.neural_workflow_policy import predict_neural_workflow_policy
        from app.services.scientific_memory import predict_next_actions

        if model.get("model_type") == NEURAL_POLICY_TYPE:
            return predict_neural_workflow_policy(context, model_path=model["artifact_path"], top_k=5)
        return predict_next_actions(context, model_path=model["artifact_path"], top_k=5)

    def _promoted_policy_tools(
        self,
        policy_advice: dict[str, Any],
        selected_tools: list[str],
        config: dict[str, Any],
    ) -> list[str]:
        if policy_advice.get("status") != "success":
            return []
        min_score = float(config.get("sciflow_policy_min_score", 0.15) or 0.15)
        known_tools = {
            "ncbi_gene_profile_tool",
            "pubmed_literature_search_tool",
            "pubchem_candidate_lookup_tool",
            "clinical_trials_search_tool",
            "reactome_pathway_search_tool",
            "openfda_adverse_event_tool",
            "OpenTargets_get_disease_id_description_by_name",
            "OpenTargets_get_drug_chembId_by_generic_name",
            "OpenTargets_get_associated_targets_by_disease_efoId",
            "evidence_quality_scorer_tool",
            "hypothesis_card_generator_tool",
            "experiment_recommendation_tool",
            "txagent_agent",
            "clawinstitute_board_publisher",
            *[tool["name"] for tool in config.get("model_tool_configs", [])],
        }
        promoted = []
        selected = set(selected_tools)
        for prediction in policy_advice.get("predictions", []):
            action = str(prediction.get("action", ""))
            score = float(prediction.get("score") or prediction.get("probability") or 0.0)
            if not action.startswith("tool_call:") or score < min_score:
                continue
            tool_name = action.split(":", 1)[1]
            if tool_name in known_tools and tool_name not in selected:
                promoted.append(tool_name)
        return promoted

    def _build_sciflow_execution_policy(
        self,
        policy_advice: dict[str, Any],
        state: ResearchRunState,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        if policy_advice.get("status") != "success":
            return {
                "enabled": bool(policy_advice.get("enabled")),
                "status": policy_advice.get("status", "disabled"),
                "applied": False,
                "selected_actions": [],
                "effects": [],
            }
        predictions = policy_advice.get("predictions", [])
        selected_actions = [
            {
                "action": str(prediction.get("action") or ""),
                "score": float(prediction.get("score") or prediction.get("probability") or 0.0),
            }
            for prediction in predictions
            if prediction.get("action")
        ]
        actions = {item["action"] for item in selected_actions}
        routed = set(state.context.get("objective_classification", {}).get("required_capabilities", []))
        tool_actions = [action for action in actions if action.startswith("tool_call:")]
        wants_live_execution = any(
            action in actions
            for action in (
                "state_transition:EXECUTE_EVIDENCE_COLLECTION",
                "state_transition:TOOL_CALL_STARTED",
                "state_transition:TOOL_CALL_COMPLETED",
            )
        )
        wants_tooluniverse = (
            "tooluniverse" in routed
            or any("OpenTargets" in action or "tooluniverse" in action.lower() for action in tool_actions)
        )
        applied = bool(config.get("real_data_enabled") and (wants_live_execution or tool_actions or wants_tooluniverse))
        effects: list[str] = []
        if applied:
            effects.append("prioritize_live_evidence_execution")
            effects.append("add_policy_followup_pubmed_queries")
            if wants_tooluniverse:
                effects.append("deepen_opentargets_followups")
        return {
            "enabled": True,
            "status": "applied" if applied else "advice_only",
            "applied": applied,
            "selected_actions": selected_actions[:5],
            "effects": effects,
            "extra_pubmed_queries": 2 if applied else 0,
            "pubmed_retmax": 7 if applied else 5,
            "max_tooluniverse_followups": 3 if applied and wants_tooluniverse else 2,
            "rationale": (
                "Policy predicted execution/tool actions, so the runtime expanded live evidence collection."
                if applied
                else "Policy produced advice but did not trigger a live execution change."
            ),
        }

    def _local_context_evidence(self, state: ResearchRunState) -> list[dict[str, Any]]:
        target = self._primary_target(state)
        disease = self._primary_disease(state)
        context = state.context.get("biomedical_context", {})
        queries = context.get("pubmed_queries", [])
        return [
            {
                "source": "local_objective_context",
                "text": (
                    f"The objective asks whether {target}-linked biology is relevant to {disease}. "
                    "This is parsed planning context, not external biomedical evidence."
                ),
                "structured": {
                    "target": target,
                    "disease": disease,
                    "objective": state.objective,
                    "biomedical_context": context,
                },
            },
            {
                "source": "local_retrieval_plan",
                "text": (
                    "Live evidence has not been retrieved in this mode. The run should be treated as a "
                    f"workflow dry run; suggested retrieval queries include: {', '.join(queries[:3]) or state.objective[:160]}."
                ),
                "structured": {"requires_real_data": True, "planned_queries": queries},
            },
        ]

    def _execute_enabled_open_scientist_capabilities(
        self,
        state: ResearchRunState,
        config: dict[str, Any],
    ) -> None:
        capabilities = set(state.context.get("objective_classification", {}).get("required_capabilities", []))
        if config.get("txagent_enabled") and "txagent" in capabilities:
            self._runtime_event(
                "txagent_agent",
                "TOOL_CALL_STARTED",
                {"tool_name": "txagent_agent", "tool_source": "open_scientist"},
                {"objective": state.objective},
            )
            result = self.open_scientist.execute_txagent(state.objective, config)
            self._runtime_event(
                "txagent_agent",
                "TOOL_CALL_COMPLETED",
                {
                    "tool_name": "txagent_agent",
                    "tool_source": "open_scientist",
                    "status": result.get("status"),
                    "latency_ms": result.get("runtime_ms"),
                },
                {"objective": state.objective},
            )
            state.tool_outputs.append({"tool_name": "txagent_agent", "tool_source": "open_scientist", "result": result})
            if result["status"] in {"success", "partial"}:
                state.evidence.append(
                    {
                        "source": "txagent_agent",
                        "text": str(result.get("output", {}).get("answer") or result.get("output", ""))[:4000],
                        "structured": result,
                    }
                )
    def _execute_evidence_collection(
        self,
        state: ResearchRunState,
        trace: list[dict[str, Any]],
        config: dict[str, Any],
    ) -> ResearchRunState:
        state.current_state = AgentStateName.EXECUTE_EVIDENCE_COLLECTION
        if config.get("real_data_enabled"):
            return self._execute_live_evidence_collection(state, trace, config)
        state.evidence = self._local_context_evidence(state)
        model_tool_outputs = []
        target = self._primary_target(state)
        disease = self._primary_disease(state)
        hypothesis_seed = f"Modulating {target}-linked mechanisms may be relevant to {disease}."
        for model_tool in config.get("model_tool_configs", []):
            model_result = execute_model_tool(
                model_tool,
                {
                    "hypothesis": hypothesis_seed,
                    "evidence_text": (
                        "Local planning context was extracted from the objective; live external evidence was not retrieved."
                    ),
                    "entity_context": {
                        "gene": target,
                        "disease": disease,
                        "biomedical_context": state.context.get("biomedical_context", {}),
                    },
                },
            )
            state.tool_outputs.append(
                {
                    "tool_name": model_tool["name"],
                    "tool_source": "custom_model",
                    "result": model_result,
                }
            )
            model_tool_outputs.append({"tool_name": model_tool["name"], "result": model_result})
        for model_output in model_tool_outputs:
            result = model_output["result"]
            if result["status"] in {"success", "partial"}:
                state.evidence.append(
                    {
                        "source": model_output["tool_name"],
                        "text": result["output"].get("rationale", "Custom model produced a structured evidence assessment."),
                        "structured": result["output"],
                    }
                )
        self._execute_enabled_open_scientist_capabilities(state, config)
        state.evidence = type_evidence_items(state.evidence)
        self._record(
            trace,
            "mechanism_agent",
            state.current_state.value,
            {"selected_tools": state.selected_tools},
            {
                "evidence": state.evidence,
                "evidence_types": sorted({item.get("evidence_type", "unknown") for item in state.evidence}),
                "tool_output_count": len(state.tool_outputs),
                "custom_model_tool_count": len(model_tool_outputs),
                "live_public_tool_count": 0,
                "tooluniverse_tool_count": 0,
            },
        )
        return state

    def _execute_live_evidence_collection(
        self,
        state: ResearchRunState,
        trace: list[dict[str, Any]],
        config: dict[str, Any],
    ) -> ResearchRunState:
        context = state.context.get("biomedical_context", {})
        execution_policy = state.context.get("sciflow_execution_policy", {})
        policy_applied = bool(execution_policy.get("applied"))
        genes = context.get("primary_genes", [])[:2]
        diseases = context.get("diseases", [])[:3]
        candidates = context.get("candidate_interventions", [])[:8]
        pubmed_queries = list(context.get("pubmed_queries", []))[:7]
        policy_followups: list[str] = []
        if policy_applied:
            for query in self._policy_followup_pubmed_queries(genes, diseases, context):
                if query not in pubmed_queries:
                    pubmed_queries.append(query)
                    policy_followups.append(query)
                if len(policy_followups) >= int(execution_policy.get("extra_pubmed_queries") or 0):
                    break
        pubmed_retmax = int(execution_policy.get("pubmed_retmax") or 5) if policy_applied else 5
        live_calls: list[tuple[str, str, dict[str, Any]]] = []
        for gene in genes:
            live_calls.append(("knowledge_agent", "ncbi_gene_profile_tool", {"gene_symbol": gene, "organism": "Homo sapiens"}))
        for query in pubmed_queries:
            clean_q = self._sanitize_pubmed_query(query, genes, diseases)
            if clean_q:
                live_calls.append(("literature_agent", "pubmed_literature_search_tool", {"query": clean_q, "retmax": pubmed_retmax}))
        if candidates:
            live_calls.append(("molecule_agent", "pubchem_candidate_lookup_tool", {"names": candidates}))
        for gene in genes:
            live_calls.append(("omics_agent", "reactome_pathway_search_tool", {"query": gene, "page_size": 5}))
        for pathway in context.get("pathways", [])[:2]:
            live_calls.append(("omics_agent", "reactome_pathway_search_tool", {"query": pathway, "page_size": 5}))
        for disease in diseases[:2]:
            if genes:
                live_calls.append(
                    (
                        "clinical_agent",
                        "clinical_trials_search_tool",
                        {"condition": disease, "query": genes[0], "page_size": 5},
                    )
                )
            for candidate in candidates[:2]:
                live_calls.append(
                    (
                        "clinical_agent",
                        "clinical_trials_search_tool",
                        {"condition": disease, "query": candidate, "page_size": 5},
                    )
                )
        for candidate in candidates[:3]:
            live_calls.append(("safety_agent", "openfda_adverse_event_tool", {"drug_name": candidate, "limit": 5}))
        for disease in diseases:
            live_calls.append(
                (
                    "tooluniverse_agent",
                    "OpenTargets_get_disease_id_description_by_name",
                    {"diseaseName": disease},
                )
            )
        for drug in candidates:
            live_calls.append(
                (
                    "tooluniverse_agent",
                    "OpenTargets_get_drug_chembId_by_generic_name",
                    {"drugName": drug},
                )
            )

        def _pubmed_zero_results(result: dict[str, Any]) -> bool:
            if result.get("status") != "success":
                return False
            output = result.get("output", {})
            articles = output.get("articles") or output.get("results") or output.get("items") or []
            return isinstance(articles, list) and len(articles) == 0

        def _simplify_pubmed_query(query: str) -> str:
            words = [w for w in query.split() if len(w) >= 3]
            focused = " ".join(words[:4])
            return focused if focused != query else ""

        def execute_call(agent_name: str, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
            starting_source = "live_public_biomedical" if tool_name in self.tools else "tooluniverse"
            self._runtime_event(
                agent_name,
                "TOOL_CALL_STARTED",
                {"tool_name": tool_name, "tool_source": starting_source},
                payload,
            )
            started = time.perf_counter()
            source = starting_source
            active_payload = payload
            last_exc: Exception | None = None
            for attempt in range(3):
                last_exc = None
                try:
                    if tool_name in self.tools:
                        result = self.tools[tool_name].run(active_payload).model_dump()
                        source = "live_public_biomedical"
                    else:
                        tooluniverse_adapter = ToolUniverseAdapter(scan_all=False)
                        result = tooluniverse_adapter.execute(tool_name, active_payload)
                        source = "tooluniverse"
                    # Retry PubMed zero-result responses with a simplified query
                    if (
                        tool_name == "pubmed_literature_search_tool"
                        and attempt < 2
                        and _pubmed_zero_results(result)
                    ):
                        original_query = active_payload.get("query", "")
                        simplified = _simplify_pubmed_query(original_query)
                        if simplified and simplified != original_query:
                            active_payload = {**active_payload, "query": simplified}
                            time.sleep(0.5 * (attempt + 1))
                            continue
                    break
                except Exception as exc:
                    last_exc = exc
                    if attempt < 2:
                        time.sleep(1.0 * (attempt + 1))
            if last_exc is not None:
                result = {
                    "status": "failure",
                    "input": active_payload,
                    "output": {"error": str(last_exc)[:1000]},
                    "sources": [{"name": source, "tool_name": tool_name}],
                    "confidence": 0.0,
                    "warnings": [str(last_exc)[:1000]],
                    "runtime_ms": int((time.perf_counter() - started) * 1000),
                    "tool_version": source,
                }
            self._runtime_event(
                agent_name,
                "TOOL_CALL_COMPLETED",
                {
                    "tool_name": tool_name,
                    "tool_source": source,
                    "status": result.get("status"),
                    "latency_ms": result.get("runtime_ms"),
                },
                payload,
            )
            return {
                "agent_name": agent_name,
                "tool_name": tool_name,
                "tool_source": source,
                "input": active_payload,
                "result": result,
            }

        live_tool_outputs: list[dict[str, Any]] = []
        serial_calls = [call for call in live_calls if call[1] == "ncbi_gene_profile_tool"]
        parallel_calls = [call for call in live_calls if call[1] != "ncbi_gene_profile_tool"]
        for call in serial_calls:
            live_tool_outputs.append(execute_call(*call))
            time.sleep(0.45)
        if parallel_calls:
            max_workers = max(1, min(int(config.get("agent_count", 6)), len(parallel_calls)))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(execute_call, *call) for call in parallel_calls]
                for future in as_completed(futures):
                    live_tool_outputs.append(future.result())
        for live_output in live_tool_outputs:
            state.tool_outputs.append(
                {
                    "tool_name": live_output["tool_name"],
                    "tool_source": live_output["tool_source"],
                    "result": live_output["result"],
                }
            )
            evidence_item = self._evidence_from_tool_output(live_output)
            if evidence_item:
                state.evidence.append(evidence_item)
        for evidence_item in self._benchmark_public_evidence_items(config, context):
            state.evidence.append(evidence_item)
        follow_up_outputs = self._run_tooluniverse_followups(
            state,
            live_tool_outputs,
            limit=int(execution_policy.get("max_tooluniverse_followups") or 2) if policy_applied else 2,
        )
        for follow_up in follow_up_outputs:
            state.tool_outputs.append(
                {
                    "tool_name": follow_up["tool_name"],
                    "tool_source": "tooluniverse",
                    "result": follow_up["result"],
                }
            )
            evidence_item = self._evidence_from_tool_output(follow_up)
            if evidence_item:
                state.evidence.append(evidence_item)

        state.evidence = type_evidence_items(state.evidence)
        preliminary_strategy = build_scientific_strategy(
            objective=state.objective,
            biomedical_context=context,
            evidence=state.evidence,
            claim_graph=state.context.get("claim_graph", {}),
        )
        state.context["preliminary_scientific_strategy"] = preliminary_strategy
        preliminary_hierarchy = summarize_evidence_hierarchy(state.evidence)
        preliminary_contradictions = detect_contradictions(
            task=context.get("benchmark_task", config.get("benchmark_task", {})),
            evidence=state.evidence,
            tool_calls=state.tool_outputs,
        )
        adaptive_plan = plan_adaptive_tools(
            task=context.get("benchmark_task", config.get("benchmark_task", {})),
            evidence_hierarchy=preliminary_hierarchy,
            contradiction_analysis=preliminary_contradictions,
            max_recommendations=max(2, min(int(config.get("strategy_repair_max_queries", 2)) + 2, 6)),
        )
        state.context["adaptive_tool_plan"] = adaptive_plan
        strategy_repair_outputs: list[dict[str, Any]] = []
        strategy_repair_queries: list[str] = []
        if config.get("strategy_repair_enabled", True):
            max_repair_queries = max(0, min(int(config.get("strategy_repair_max_queries", 2)), 5))
            seen_queries = {str(query).strip().lower() for query in pubmed_queries}
            planned_followups = [
                *[
                    {"query": item.get("query")}
                    for item in adaptive_plan.get("recommendations", [])
                    if item.get("tool_name") == "pubmed_literature_search_tool" and item.get("query")
                ],
                *preliminary_strategy.get("recommended_followups", []),
            ]
            for followup in planned_followups:
                query = str(followup.get("query", "")).strip()
                if not query or query.lower() in seen_queries:
                    continue
                strategy_repair_queries.append(query)
                seen_queries.add(query.lower())
                if len(strategy_repair_queries) >= max_repair_queries:
                    break
            for query in strategy_repair_queries:
                repair_output = execute_call(
                    "strategy_agent",
                    "pubmed_literature_search_tool",
                    {"query": query, "retmax": min(pubmed_retmax, 5)},
                )
                strategy_repair_outputs.append(repair_output)
                state.tool_outputs.append(
                    {
                        "tool_name": repair_output["tool_name"],
                        "tool_source": repair_output["tool_source"],
                        "result": repair_output["result"],
                    }
                )
                evidence_item = self._evidence_from_tool_output(repair_output)
                if evidence_item:
                    state.evidence.append(evidence_item)
            if strategy_repair_outputs:
                state.evidence = type_evidence_items(state.evidence)

        model_tool_outputs = []
        hypothesis_seed = (
            f"Modulating {self._primary_target(state)}-linked mechanisms may be relevant to {self._primary_disease(state)}."
        )
        for model_tool in config.get("model_tool_configs", []):
            model_result = execute_model_tool(
                model_tool,
                {
                    "hypothesis": hypothesis_seed,
                    "evidence_text": "Live evidence collection includes gene, disease, literature, compound, and OpenTargets context.",
                    "entity_context": {
                        "genes": genes,
                        "diseases": diseases,
                        "candidate_interventions": candidates,
                    },
                },
            )
            state.tool_outputs.append(
                {
                    "tool_name": model_tool["name"],
                    "tool_source": "custom_model",
                    "result": model_result,
                }
            )
            model_tool_outputs.append({"tool_name": model_tool["name"], "result": model_result})
            if model_result["status"] in {"success", "partial"}:
                state.evidence.append(
                    {
                        "source": model_tool["name"],
                        "text": model_result["output"].get("rationale", "Custom model produced a structured evidence assessment."),
                        "structured": model_result["output"],
                    }
                )
        self._execute_enabled_open_scientist_capabilities(state, config)
        state.evidence = type_evidence_items(state.evidence)
        state.context["scientific_strategy"] = build_scientific_strategy(
            objective=state.objective,
            biomedical_context=context,
            evidence=state.evidence,
            claim_graph=state.context.get("claim_graph", {}),
        )
        self._record(
            trace,
            "mechanism_agent",
            state.current_state.value,
            {
                "selected_tools": state.selected_tools,
                "agent_roster": state.context.get("agent_roster", []),
                "biomedical_context": context,
            },
            {
                "evidence": state.evidence,
                "evidence_types": sorted({item.get("evidence_type", "unknown") for item in state.evidence}),
                "tool_output_count": len(state.tool_outputs),
                "custom_model_tool_count": len(model_tool_outputs),
                "live_public_tool_count": len(
                    [item for item in live_tool_outputs if item["tool_source"] == "live_public_biomedical"]
                )
                + len(
                    [
                        item
                        for item in strategy_repair_outputs
                        if item["tool_source"] == "live_public_biomedical"
                    ]
                ),
                "tooluniverse_tool_count": len(
                    [item for item in live_tool_outputs if item["tool_source"] == "tooluniverse"]
                )
                + len(follow_up_outputs),
                "scientific_strategy": state.context.get("scientific_strategy", {}),
                "adaptive_tool_plan": state.context.get("adaptive_tool_plan", {}),
                "strategy_repair": {
                    "enabled": bool(config.get("strategy_repair_enabled", True)),
                    "queries": strategy_repair_queries,
                    "executed_count": len(strategy_repair_outputs),
                    "preliminary_readiness": preliminary_strategy.get("readiness", {}),
                },
                "sciflow_policy_application": {
                    "status": execution_policy.get("status", "disabled"),
                    "applied": policy_applied,
                    "effects": execution_policy.get("effects", []),
                    "policy_followup_pubmed_queries": policy_followups,
                    "pubmed_retmax": pubmed_retmax,
                    "max_tooluniverse_followups": int(execution_policy.get("max_tooluniverse_followups") or 2)
                    if policy_applied
                    else 2,
                    "selected_actions": execution_policy.get("selected_actions", []),
                },
                "agent_tool_assignments": [
                    {
                        "agent_name": item["agent_name"],
                        "tool_name": item["tool_name"],
                        "status": item["result"].get("status"),
                    }
                    for item in [*live_tool_outputs, *follow_up_outputs, *strategy_repair_outputs]
                ],
            },
        )
        self._emit_checkpoint(state, "evidence_collected", config)
        return state

    def _policy_followup_pubmed_queries(
        self,
        genes: list[str],
        diseases: list[str],
        context: dict[str, Any],
    ) -> list[str]:
        gene = genes[0] if genes else ""
        disease = diseases[0] if diseases else ""
        pathways = context.get("pathways", [])[:2]
        queries = []
        if gene and disease:
            queries.extend(
                [
                    f"{gene} {disease} genetics association",
                    f"{gene} {disease} clinical trial biomarker",
                    f"{gene} {disease} therapeutic target validation",
                ]
            )
        for pathway in pathways:
            if disease:
                queries.append(f"{pathway} {disease} pathway intervention")
        return queries

    def _run_tooluniverse_followups(
        self,
        state: ResearchRunState,
        live_tool_outputs: list[dict[str, Any]],
        *,
        limit: int = 2,
    ) -> list[dict[str, Any]]:
        efo_ids: list[str] = []
        for item in live_tool_outputs:
            if item["tool_name"] != "OpenTargets_get_disease_id_description_by_name":
                continue
            raw = item["result"].get("output", {}).get("raw")
            for hit in raw.get("data", {}).get("search", {}).get("hits", []) if isinstance(raw, dict) else []:
                efo_id = hit.get("id")
                if efo_id:
                    efo_ids.append(efo_id)
        outputs = []
        if not efo_ids:
            return outputs
        adapter = ToolUniverseAdapter(scan_all=False)
        for efo_id in list(dict.fromkeys(efo_ids))[: max(1, int(limit))]:
            started = time.perf_counter()
            self._runtime_event(
                "tooluniverse_agent",
                "TOOL_CALL_STARTED",
                {"tool_name": "OpenTargets_get_associated_targets_by_disease_efoId", "tool_source": "tooluniverse"},
                {"efoId": efo_id},
            )
            try:
                result = adapter.execute("OpenTargets_get_associated_targets_by_disease_efoId", {"efoId": efo_id})
            except Exception as exc:
                result = {
                    "status": "failure",
                    "input": {"efoId": efo_id},
                    "output": {"error": str(exc)[:1000]},
                    "sources": [{"name": "tooluniverse", "tool_name": "OpenTargets_get_associated_targets_by_disease_efoId"}],
                    "confidence": 0.0,
                    "warnings": [str(exc)[:1000]],
                    "runtime_ms": int((time.perf_counter() - started) * 1000),
                    "tool_version": "tooluniverse",
                }
            self._runtime_event(
                "tooluniverse_agent",
                "TOOL_CALL_COMPLETED",
                {
                    "tool_name": "OpenTargets_get_associated_targets_by_disease_efoId",
                    "tool_source": "tooluniverse",
                    "status": result.get("status"),
                    "latency_ms": result.get("runtime_ms"),
                },
                {"efoId": efo_id},
            )
            outputs.append(
                {
                    "agent_name": "tooluniverse_agent",
                    "tool_name": "OpenTargets_get_associated_targets_by_disease_efoId",
                    "tool_source": "tooluniverse",
                    "input": {"efoId": efo_id},
                    "result": result,
                }
            )
        return outputs

    def _evidence_from_tool_output(self, live_output: dict[str, Any]) -> dict[str, Any] | None:
        result = live_output["result"]
        if result.get("status") == "failure":
            return None
        output = result.get("output", {})
        tool_name = live_output["tool_name"]
        if tool_name == "ncbi_gene_profile_tool":
            text = output.get("summary") or output.get("description") or "NCBI Gene returned a live gene record."
            return {"source": "NCBI Gene", "text": f"NCBI Gene {output.get('gene_symbol', '')}: {text}", "structured": output}
        if tool_name == "pubmed_literature_search_tool":
            articles = output.get("articles", [])
            titles = "; ".join(article.get("title", "") for article in articles[:4] if article.get("title"))
            return {
                "source": f"PubMed: {output.get('query')}",
                "text": titles or f"PubMed returned live literature search results for {output.get('query')}.",
                "structured": output,
            }
        if tool_name == "pubchem_candidate_lookup_tool":
            compounds = output.get("compounds", [])
            if not compounds:
                return {
                    "source": "PubChem candidate lookup",
                    "text": "PubChem returned no candidate compound records for the supplied intervention names.",
                    "structured": output,
                }
            names = ", ".join(compound.get("name", "") for compound in compounds)
            return {
                "source": "PubChem candidate lookup",
                "text": f"PubChem returned candidate/intervention records for: {names}.",
                "structured": output,
            }
        if tool_name == "clinical_trials_search_tool":
            studies = output.get("studies", [])
            if not studies:
                return {
                    "source": f"ClinicalTrials.gov: {output.get('condition')} {output.get('query')}",
                    "text": "ClinicalTrials.gov returned no matching studies for the supplied condition/query.",
                    "structured": output,
                }
            summaries = []
            for study in studies[:4]:
                phase = ", ".join(study.get("phase") or []) or "phase not listed"
                title = study.get("title") or study.get("nct_id") or "study"
                status = study.get("status") or "status not listed"
                summaries.append(f"{title} ({status}, {phase})")
            return {
                "source": f"ClinicalTrials.gov: {output.get('condition')} {output.get('query')}",
                "text": "ClinicalTrials.gov returned translational study records: " + "; ".join(summaries),
                "structured": output,
            }
        if tool_name == "reactome_pathway_search_tool":
            pathways = output.get("pathways", [])
            if not pathways:
                return {
                    "source": f"Reactome: {output.get('query')}",
                    "text": "Reactome returned no pathway records for this query.",
                    "structured": output,
                }
            names = "; ".join(pathway.get("name", "") for pathway in pathways[:4] if pathway.get("name"))
            return {
                "source": f"Reactome: {output.get('query')}",
                "text": f"Reactome returned pathway/mechanism records: {names}.",
                "structured": output,
            }
        if tool_name == "openfda_adverse_event_tool":
            reactions = output.get("common_reactions", [])
            reaction_text = "; ".join(item.get("reaction", "") for item in reactions[:5] if item.get("reaction"))
            return {
                "source": f"openFDA adverse events: {output.get('drug_name')}",
                "text": (
                    f"openFDA returned {output.get('total_matching_reports', 0)} matching adverse-event reports. "
                    f"Common returned reaction terms include: {reaction_text or 'none in returned reports'}. "
                    "These are safety signals, not incidence rates or causal proof."
                ),
                "structured": output,
            }
        raw = output.get("raw", {})
        return {
            "source": f"ToolUniverse: {tool_name}",
            "text": self._summarize_tooluniverse_output(tool_name, raw),
            "structured": {"tool_name": tool_name, "raw": raw},
        }

    def _summarize_tooluniverse_output(self, tool_name: str, raw: Any) -> str:
        try:
            associated = raw.get("data", {}).get("disease", {}).get("associatedTargets", {})
            rows = associated.get("rows", [])
            disease_name = raw.get("data", {}).get("disease", {}).get("name", "disease")
            if rows:
                target_summaries = []
                for row in rows[:4]:
                    target = row.get("target", {})
                    symbol = target.get("approvedSymbol") or target.get("id")
                    score = row.get("score")
                    if symbol:
                        target_summaries.append(
                            f"{symbol} association score {round(float(score), 3) if isinstance(score, (int, float)) else score}"
                        )
                return (
                    f"{tool_name} returned {associated.get('count', len(rows))} associated targets for "
                    f"{disease_name}; top retrieved targets: " + "; ".join(target_summaries)
                )
            hits = raw.get("data", {}).get("search", {}).get("hits", [])
            if hits:
                summaries = []
                for hit in hits[:3]:
                    summaries.append(
                        f"{hit.get('name') or hit.get('id')}: {hit.get('description') or hit.get('id')}"
                    )
                return f"{tool_name} returned OpenTargets search hits: " + "; ".join(summaries)
        except AttributeError:
            pass
        return f"{tool_name} returned ToolUniverse/OpenTargets evidence: {str(raw)[:1000]}"

    def _score_evidence(
        self,
        state: ResearchRunState,
        trace: list[dict[str, Any]],
        config: dict[str, Any],
    ) -> ResearchRunState:
        state.current_state = AgentStateName.SCORE_EVIDENCE
        scored = []
        hypothesis_seed = (
            f"Modulating {self._primary_target(state)}-linked mechanisms may be relevant to {self._primary_disease(state)}."
        )
        if self._llm_enabled(config):
            scored = self._score_evidence_with_llm_batch(state, config, hypothesis_seed)
        else:
            for item in state.evidence:
                score_output = self._deterministic_score_evidence_item(item, hypothesis_seed, state)
                scored.append({**item, "score": score_output})
        state.evidence = scored
        state.context["evidence_hierarchy"] = summarize_evidence_hierarchy(state.evidence)
        if "adaptive_tool_plan" not in state.context:
            state.context["adaptive_tool_plan"] = plan_adaptive_tools(
                task=state.context.get("benchmark_task", {}),
                evidence_hierarchy=state.context["evidence_hierarchy"],
                contradiction_analysis={},
                max_recommendations=max(2, min(int(config.get("strategy_repair_max_queries", 2)) + 2, 6)),
            )
        state.context["scientific_strategy"] = build_scientific_strategy(
            objective=state.objective,
            biomedical_context=state.context.get("biomedical_context", {}),
            evidence=state.evidence,
            claim_graph=state.context.get("claim_graph", {}),
        )
        self._record(
            trace,
            "critic_agent",
            state.current_state.value,
            {"evidence_count": len(scored), "strictness": config.get("evidence_strictness", "balanced")},
            {
                "scored_evidence": scored,
                "evidence_hierarchy": state.context["evidence_hierarchy"],
                "scientific_strategy": state.context["scientific_strategy"],
                "llm_calls": state.context.get("llm_calls", []),
            },
        )
        return state

    def _generate_hypotheses(
        self,
        state: ResearchRunState,
        trace: list[dict[str, Any]],
        config: dict[str, Any],
    ) -> ResearchRunState:
        state.current_state = AgentStateName.GENERATE_HYPOTHESES
        target = self._primary_target(state)
        disease = self._primary_disease(state)
        card = self.tools["hypothesis_card_generator_tool"].run(
            {"target": target, "disease": disease, "evidence": state.evidence}
        ).model_dump()
        state.hypothesis_card = card["output"]
        if self._llm_enabled(config):
            max_tokens = int(config.get("llm_max_tokens", 1200))
            # Richer output when token budget allows
            rich_mode = max_tokens >= 1000
            hypothesis_json = self._llm_json(
                state,
                config,
                agent_name="mechanism_agent",
                task="hypothesis_synthesis",
                system_prompt=(
                    "You are a senior biomedical research scientist with expertise in translational oncology "
                    "and drug target biology. Synthesize a rigorous, specific, evidence-grounded candidate "
                    "hypothesis from retrieved data. Be scientifically precise, distinguish established "
                    "from speculative, and keep all guardrails explicit. Do not assert clinical efficacy "
                    "or safety without direct clinical evidence in the retrieved data."
                ),
                prompt=(
                    "Return only JSON with these keys: title, hypothesis, scientific_assessment, "
                    "candidate_intervention_summary, limitations.\n"
                    "Rules:\n"
                    f"- title: concise scientific title (10-15 words), name the specific target and disease\n"
                    f"- hypothesis: {('200-280' if rich_mode else '80-120')} words. Be specific: name the "
                    "target mutation or variant, the mechanism (pathway activation, resistance bypass, etc.), "
                    "the disease context, clinical precedence status, and the key unresolved questions. "
                    "Distinguish what is established from what requires validation. Do not assert efficacy.\n"
                    f"- scientific_assessment: array of {('5-6' if rich_mode else '3')} strings, each addressing "
                    "a specific aspect: (1) target-disease validity evidence, (2) clinical precedence status, "
                    "(3) resistance or bypass mechanism evidence, (4) safety and translation gaps, "
                    "(5) patient stratification considerations, (6) key unresolved mechanistic question.\n"
                    "- candidate_intervention_summary: specific paragraph naming actual retrieved compounds "
                    "or drug classes, their approval status, and open questions. Do not fabricate drug names "
                    "not present in the evidence.\n"
                    f"- limitations: array of {('4-5' if rich_mode else '3')} strings naming specific "
                    "evidence gaps, not generic disclaimers.\n"
                    "If clinical precedence evidence exists, frame it as established-but-incomplete, "
                    "explicitly separating known activity from unresolved resistance, safety, and patient-"
                    "selection questions. Do not present established targets as new discoveries.\n"
                    f"Objective: {state.objective}\n"
                    f"Evidence digest: {json.dumps(self._evidence_digest(state, 14, 600), default=str)[:7000]}"
                ),
                max_tokens=max_tokens,
            )
            if hypothesis_json.get("_parse_fallback"):
                state.hypothesis_card.setdefault("limitations", []).append(
                    "LLM hypothesis synthesis was unstructured; raw response is preserved in provenance."
                )
            else:
                for key in ("title", "hypothesis", "candidate_intervention_summary"):
                    if hypothesis_json.get(key):
                        state.hypothesis_card[key] = hypothesis_json[key]
                for key in ("scientific_assessment", "limitations"):
                    values = self._string_list(hypothesis_json.get(key))
                    if values:
                        state.hypothesis_card[key] = values
        claim_graph = build_claim_graph(state.hypothesis_card, state.evidence)
        evidence_coverage = build_evidence_coverage_matrix(
            state.context.get("case_profile", {}),
            state.evidence,
            claim_graph,
        )
        state.context["claim_graph"] = claim_graph
        state.context["evidence_coverage_matrix"] = evidence_coverage
        state.context["scientific_strategy"] = build_scientific_strategy(
            objective=state.objective,
            biomedical_context=state.context.get("biomedical_context", {}),
            evidence=state.evidence,
            claim_graph=claim_graph,
        )
        state.hypothesis_card["claim_graph"] = claim_graph
        state.hypothesis_card["case_profile"] = state.context.get("case_profile", {})
        state.hypothesis_card["evidence_coverage_matrix"] = evidence_coverage
        state.hypothesis_card["scientific_strategy"] = state.context["scientific_strategy"]
        self._record(
            trace,
            "mechanism_agent",
            state.current_state.value,
            {"scored_evidence": state.evidence},
            {
                "hypothesis_card": state.hypothesis_card,
                "claim_graph": claim_graph,
                "evidence_coverage_matrix": evidence_coverage,
                "scientific_strategy": state.context["scientific_strategy"],
                "llm_calls": state.context.get("llm_calls", []),
            },
        )
        return state

    def _debate_scientist_roles(self, config: dict[str, Any]) -> list[dict[str, str]]:
        roles = [
            {
                "agent_name": "mechanism_agent",
                "discipline": "disease mechanism and causal pathway biology",
                "stance": "argue from target-disease mechanism, pathway plausibility, and causal evidence",
            },
            {
                "agent_name": "literature_agent",
                "discipline": "biomedical literature and citation grounding",
                "stance": "argue from PubMed records, publication type, and citation strength",
            },
            {
                "agent_name": "tooluniverse_agent",
                "discipline": "ToolUniverse/OpenTargets target and intervention evidence",
                "stance": "argue from ToolUniverse records, target association scores, and drug records",
            },
            {
                "agent_name": "molecule_agent",
                "discipline": "candidate intervention and chemistry review",
                "stance": "argue from compound identity, target relevance, and molecule-level gaps",
            },
            {
                "agent_name": "safety_agent",
                "discipline": "clinical safety and translation risk",
                "stance": "challenge efficacy/safety overclaims and identify translational risks",
            },
            {
                "agent_name": "omics_agent",
                "discipline": "omics, pathway, and perturbation evidence",
                "stance": "check whether pathway and cellular evidence justify the proposed mechanism",
            },
            {
                "agent_name": "critic_agent",
                "discipline": "skeptical scientific review",
                "stance": "find contradictions, weak links, missing controls, and abstention triggers",
            },
        ]
        count = max(2, min(int(config.get("agent_count", 6)), len(roles)))
        return roles[:count]

    def _deterministic_scientist_positions(self, state: ResearchRunState, config: dict[str, Any]) -> list[dict[str, Any]]:
        evidence_sources = [item.get("source", "unknown") for item in state.evidence[:6]]
        target = self._primary_target(state)
        disease = self._primary_disease(state)
        genes = state.context.get("biomedical_context", {}).get("primary_genes", [target])
        # Build context-specific talking points
        lowered = f"{target} {disease} {state.objective}".lower()
        is_oncology = any(t in lowered for t in [
            "cancer", "nsclc", "sclc", "melanoma", "leukemia", "lymphoma", "carcinoma",
            "glioma", "myeloma", "sarcoma", "adenocarcinoma",
        ])
        is_resistance = any(t in lowered for t in ["resistance", "acquired resistance", "bypass"])
        is_kras = "kras" in lowered
        is_egfr = "egfr" in lowered
        is_braf = "braf" in lowered
        is_ret = "ret" in lowered
        is_met = lowered.count("met ") > 0 or "met exon" in lowered
        target_str = genes[0] if genes else target
        disease_str = disease if disease != "the disease context" else "the relevant disease"

        def _context_position(agent: str) -> tuple[str, list[str], list[str], str, float]:
            """Return (position, concerns, followups, vote, confidence_delta)."""
            if agent == "mechanism_agent":
                if is_kras:
                    pos = (
                        f"{target_str} G12C covalent inhibition is a validated strategy with approved clinical agents. "
                        f"The mechanistic rationale for both direct KRAS G12C inhibition and resistance bypass is "
                        f"well-supported by biochemical and clinical evidence, but response durability and co-mutation "
                        f"effects on STK11/KEAP1 pathways remain key unresolved questions."
                    )
                    concerns = [
                        "Adaptive resistance through RTK bypass and RAS pathway reactivation limits durability.",
                        "Co-mutations in STK11 and KEAP1 are mechanistically distinct resistance drivers that require separate strategies.",
                    ]
                    followups = ["Profile resistance mechanism spectrum in clinical post-progression biopsies."]
                elif is_egfr:
                    pos = (
                        f"{target_str} represents a well-validated oncogenic driver in {disease_str}. "
                        f"The mechanistic cascade from EGFR mutation through RAS/MAPK and PI3K/AKT is supported "
                        f"by decades of evidence, but acquired resistance mechanisms — particularly bypass via MET "
                        f"and HER2 — require targeted co-inhibition strategies."
                    )
                    concerns = [
                        "C797S mutation confers cis resistance to third-generation inhibitors.",
                        "Bypass mechanisms are heterogeneous and co-exist in the same patient.",
                    ]
                    followups = ["Map bypass resistance mechanism frequency in osimertinib-resistant clinical specimens."]
                elif is_braf:
                    pos = (
                        f"{target_str} V600E drives constitutive MAPK activation and is a validated target. "
                        f"The combination of BRAF and MEK inhibition is clinically established, but adaptive "
                        f"resistance through MAPK reactivation and immune evasion limits long-term benefit."
                    )
                    concerns = [
                        "Paradoxical ERK activation with BRAF-only inhibition requires MEK co-inhibition.",
                        "Immune checkpoint co-administration sequencing needs prospective validation.",
                    ]
                    followups = ["Characterize adaptive resistance kinetics in BRAF-inhibited patient tumor biopsies."]
                elif is_ret:
                    pos = (
                        f"{target_str} fusion and mutation-driven oncogenesis is clinically validated by selective "
                        f"RET inhibitor approvals. Solvent-front resistance mutations G810R/S/C are mechanistically "
                        f"distinct from bypass resistance and require next-generation kinase engineering."
                    )
                    concerns = [
                        "G810 solvent-front mutations confer resistance to current approved RET inhibitors.",
                        "Fusion partner identity may influence sensitivity to inhibition.",
                    ]
                    followups = ["Profile G810 resistance mutation frequency across RET-altered tumor histologies."]
                elif is_met:
                    pos = (
                        f"{target_str} exon 14 skipping drives receptor stabilization through impaired CBL-mediated "
                        f"ubiquitination and degradation. This is a validated therapeutic target with approved agents, "
                        f"but secondary MET mutations and bypass via KRAS limit durability."
                    )
                    concerns = [
                        "Distinction between exon 14 skipping driver and MET amplification secondary to EGFR therapy is critical.",
                        "Secondary MET D1228 and Y1230 mutations confer resistance to type Ib MET inhibitors.",
                    ]
                    followups = ["Validate MET exon 14 co-mutations with KRAS/EGFR in primary resistance specimens."]
                elif is_oncology:
                    pos = (
                        f"The mechanistic rationale for targeting {target_str} in {disease_str} is supported by "
                        f"retrieved evidence, but the causal link from target perturbation to therapeutic response "
                        f"requires validation in disease-relevant models. Pathway context and co-mutation landscape "
                        f"should be explicitly mapped."
                    )
                    concerns = [
                        "Target dependency may be context-dependent and requires isogenic model validation.",
                        "Co-mutations and resistance mechanisms should be mapped before clinical translation.",
                    ]
                    followups = [f"Run functional validation of {target_str} dependency in patient-derived tumor models."]
                else:
                    pos = (
                        f"Retrieved evidence supports a mechanistic rationale for {target_str} in {disease_str}, "
                        f"but pathway-level plausibility must be distinguished from validated therapeutic efficacy. "
                        f"Mechanistic validation in disease-relevant models is required."
                    )
                    concerns = [
                        "Pathway evidence does not prove target-disease causality.",
                        "Off-target biology must be characterized before efficacy interpretation.",
                    ]
                    followups = ["Run target knockout or knockdown in disease-relevant cellular models."]
                return pos, concerns, followups, "support_with_limits", 0.03

            elif agent == "literature_agent":
                pubmed_count = sum(1 for s in evidence_sources if "PubMed" in s or "pubmed" in s.lower())
                pos = (
                    f"PubMed retrieval surfaced {pubmed_count} literature evidence items for {target_str} "
                    f"in {disease_str}. Literature supports the mechanistic hypothesis when articles directly "
                    f"address target-disease biology; indirect or pathway-only citations must be separated "
                    f"from clinical precedence records."
                )
                concerns = [
                    "PubMed records must be inspected for study type — clinical vs. preclinical vs. review.",
                    "Query specificity affects recall; resistance and combination queries may need explicit follow-up.",
                ]
                followups = [f"Retrieve clinical trial registration and outcomes data for {target_str}-directed therapies."]
                return pos, concerns, followups, "support_with_limits", 0.02

            elif agent == "tooluniverse_agent":
                has_opentargets = any("OpenTargets" in s or "tooluniverse" in s.lower() for s in evidence_sources)
                if has_opentargets:
                    pos = (
                        f"Open Targets / ToolUniverse evidence contributes target-disease association scores and "
                        f"tractability data for {target_str}. Association scores are ranking heuristics, not "
                        f"clinical efficacy evidence; they support target validity grounding but not response prediction."
                    )
                else:
                    pos = (
                        f"ToolUniverse and Open Targets tools should be queried for {target_str} target-disease "
                        f"association, tractability, and approved drug records in {disease_str}. "
                        f"This would strengthen or constrain the hypothesis before wet-lab investment."
                    )
                concerns = [
                    "Open Targets association scores reflect evidence density, not clinical effect size.",
                    "Drug records should distinguish approved, clinical-stage, and preclinical compounds.",
                ]
                followups = [f"Pull ToolUniverse tractability and approved intervention records for {target_str}."]
                return pos, concerns, followups, "support_with_limits", 0.02

            elif agent == "molecule_agent":
                if is_kras:
                    pos = (
                        "Covalent KRAS G12C inhibitors (sotorasib, adagrasib) represent the current standard; "
                        "combination partners targeting SOS1, MEK, or co-occurring vulnerabilities are in clinical "
                        "evaluation. Compound records for these agents should distinguish approved use from "
                        "investigational combination contexts."
                    )
                elif is_egfr:
                    pos = (
                        "Third-generation EGFR inhibitors (osimertinib) have established pharmacology; "
                        "fourth-generation compounds and bi-specific approaches targeting resistance mutations "
                        "are investigational. Molecular specificity of each against resistance mutants requires explicit review."
                    )
                elif is_braf:
                    pos = (
                        "BRAF/MEK inhibitor combinations (dabrafenib/trametinib) are approved; "
                        "combination with anti-PD-1 in triplet regimens is investigational. "
                        "Drug record retrieval should confirm approved indications versus experimental settings."
                    )
                else:
                    pos = (
                        f"Candidate intervention records for {target_str} should be retrieved from PubChem and "
                        f"drug databases. Any molecules identified are leads only — potency, selectivity, "
                        f"ADMET properties, and disease-model activity must be characterized before prioritization."
                    )
                concerns = [
                    "Drug approval status differs by tumor type and mutation; approved ≠ active in all contexts.",
                    "Resistance mechanisms alter compound binding and require structural biology validation.",
                ]
                followups = [f"Retrieve comprehensive drug records and clinical trial status for {target_str} inhibitors."]
                return pos, concerns, followups, "support_with_limits", 0.02

            elif agent == "safety_agent":
                if is_oncology:
                    pos = (
                        f"Oncology therapeutic interventions targeting {target_str} carry class-specific toxicity "
                        f"profiles. Kinase inhibitors in this class commonly cause gastrointestinal, hepatic, and "
                        f"hematologic adverse events; off-target kinase inhibition requires explicit selectivity profiling. "
                        f"Safety claims must not be made from mechanism data alone."
                    )
                    concerns = [
                        "Off-target kinase inhibition in the broader kinome must be profiled before safety inference.",
                        "Resistance mutation binding can alter selectivity and introduce new off-target risks.",
                        "Combination regimens multiply toxicity risk and require independent safety review.",
                    ]
                else:
                    pos = (
                        f"Intervention-specific safety data for {target_str} in {disease_str} must be retrieved "
                        f"before any translational claim. Adverse event profiles, contraindications, and "
                        f"drug-drug interactions should be explicitly reviewed. This analysis does not support "
                        f"any safety conclusion."
                    )
                    concerns = [
                        "No safety inference from target biology alone.",
                        "Disease-context tolerability may differ from canonical safety profiles.",
                    ]
                followups = [f"Retrieve FDA adverse event data and clinical trial safety profiles for {target_str} inhibitors."]
                return pos, concerns, followups, "revise", -0.05

            elif agent == "omics_agent":
                pos = (
                    f"Pathway and omics-level evidence for {target_str} in {disease_str} should confirm "
                    f"that the proposed mechanism operates in the relevant disease cell context. "
                    f"Single-cell transcriptomics, CRISPR screen data, and pathway enrichment analysis "
                    f"would strengthen or refute the proposed mechanism before wet-lab investment."
                )
                concerns = [
                    "Bulk transcriptomic data may obscure cell-type-specific target activity.",
                    "Pathway models may not reflect the post-translational regulation relevant to the target.",
                ]
                followups = [f"Retrieve single-cell or CRISPR screen data for {target_str} dependency in {disease_str}."]
                return pos, concerns, followups, "support_with_limits", 0.01

            else:  # critic_agent
                pos = (
                    f"The {target_str} hypothesis in {disease_str} is plausible but must remain bounded to "
                    f"computational prioritization. Retrieved evidence does not constitute clinical proof of "
                    f"concept. The critical gaps are: unresolved resistance mechanism spectrum, absence of "
                    f"patient-level selectivity data, and missing intervention-specific safety characterization."
                )
                concerns = [
                    "Computational evidence does not prove clinical efficacy or safety.",
                    f"Resistance and bypass mechanisms for {target_str} inhibitors must be explicitly addressed.",
                    "Patient stratification strategy is underdetermined from current evidence.",
                ]
                followups = [
                    "Run resistance mechanism profiling in post-progression clinical specimens.",
                    "Retrieve patient stratification biomarker data from clinical trial subgroup analyses.",
                ]
                return pos, concerns, followups, "revise", -0.05

        positions = []
        for role in self._debate_scientist_roles(config):
            agent = role["agent_name"]
            pos, concerns, followups, vote, confidence_delta = _context_position(agent)
            positions.append(
                {
                    "agent_name": agent,
                    "discipline": role["discipline"],
                    "position": pos,
                    "key_claims": [state.hypothesis_card.get("hypothesis", "")[:300]],
                    "supporting_evidence_sources": evidence_sources,
                    "concerns": concerns,
                    "requested_followups": followups,
                    "confidence_delta": confidence_delta,
                    "vote": vote,
                    "mode": "deterministic_context_aware",
                }
            )
        return positions

    def _scientist_position_from_llm(
        self,
        state: ResearchRunState,
        config: dict[str, Any],
        role: dict[str, str],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        agent_name = role["agent_name"]
        position, call_summary = self._llm_json_detached(
            config,
            agent_name=agent_name,
            task="scientist_panel_position",
            system_prompt=(
                "You are an autonomous AI scientist: an LLM reasoner operating over ToolUniverse and "
                "live biomedical tool evidence. Take a specialist role, make evidence-grounded claims, "
                "challenge weak links, and do not claim clinical efficacy or safety without direct evidence."
            ),
            prompt=(
                "Return only JSON with keys position, key_claims, supporting_evidence_sources, concerns, "
                "requested_followups, confidence_delta, vote. "
                "vote must be one of support, support_with_limits, revise, abstain. "
                "confidence_delta must be between -0.2 and 0.2. Keep lists to at most 4 short strings.\n"
                f"Agent: {agent_name}\n"
                f"Discipline: {role['discipline']}\n"
                f"Debate stance: {role['stance']}\n"
                f"Objective: {state.objective}\n"
                f"Current hypothesis card: {json.dumps(state.hypothesis_card, default=str)[:2400]}\n"
                f"Scored evidence digest: {json.dumps(self._evidence_digest(state, 8, 280), default=str)[:4200]}"
            ),
            max_tokens=900,
        )
        position["agent_name"] = agent_name
        position["discipline"] = role["discipline"]
        return position, call_summary

    def _evidence_calibrated_confidence_floor(self, state: ResearchRunState) -> float | None:
        labels: dict[str, Any] = {}
        has_clinical_precedence = False
        has_relevant_clinical_literature = False
        for item in state.evidence:
            source = str(item.get("source") or "")
            structured = item.get("structured", {}) if isinstance(item.get("structured"), dict) else {}
            if source.startswith("Benchmark public context") and isinstance(structured.get("public_labels"), dict):
                labels = structured["public_labels"]
            evidence_type = str(item.get("score", {}).get("evidence_type") or structured.get("evidence_type") or "")
            if evidence_type == "clinical_precedence":
                has_clinical_precedence = True
            if evidence_type == "clinical_precedence_literature":
                has_relevant_clinical_literature = True
        try:
            association_score = float(labels.get("open_targets_association_score") or 0.0)
        except (TypeError, ValueError):
            association_score = 0.0
        pubmed_count = int(labels.get("pubmed_gene_disease_count") or 0)
        if has_clinical_precedence or has_relevant_clinical_literature:
            return 0.72
        if labels.get("open_targets_association_status") == "matched" and association_score >= 0.5 and pubmed_count >= 50:
            return 0.68
        if labels.get("open_targets_association_status") == "matched" and association_score >= 0.25:
            return 0.6
        return None

    def _debate_and_revise(
        self,
        state: ResearchRunState,
        trace: list[dict[str, Any]],
        config: dict[str, Any],
    ) -> ResearchRunState:
        state.current_state = AgentStateName.DEBATE_AND_REVISE
        roles = self._debate_scientist_roles(config)
        llm_calls: list[dict[str, Any]] = []
        if self._llm_enabled(config):
            positions = []
            provider_parallel_cap = 3 if config.get("llm_provider") == "anthropic" else len(roles)
            max_workers = max(1, min(int(config.get("agent_count", 6)), len(roles), provider_parallel_cap))
            self._runtime_event(
                "scientist_panel",
                "AGENT_PANEL_STARTED",
                {
                    "roles": [role["agent_name"] for role in roles],
                    "parallel_workers": max_workers,
                    "mode": "parallel_llm_scientist_panel",
                },
            )
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(self._scientist_position_from_llm, state, config, role) for role in roles]
                for future in as_completed(futures):
                    position, call_summary = future.result()
                    positions.append(position)
                    llm_calls.append(call_summary)
                    self._runtime_event(
                        position.get("agent_name", "scientist_agent"),
                        "AGENT_POSITION_COMPLETED",
                        {
                            "vote": position.get("vote", "review"),
                            "discipline": position.get("discipline"),
                            "position": str(position.get("position", ""))[:260],
                        },
                    )
            state.context.setdefault("llm_calls", []).extend(llm_calls)
            debate = self._llm_json(
                state,
                config,
                agent_name="critic_agent",
                task="cross_agent_debate",
                system_prompt=(
                    "You moderate a scientific debate between AI scientist agents. Identify consensus, "
                    "disagreement, overclaims, and required revisions. Be skeptical and evidence-bound."
                ),
                prompt=(
                    "Return only JSON with keys agreements, disagreements, overclaims, required_revisions, consensus. "
                    "consensus must be support, support_with_limits, revise, or abstain. Lists must be short.\n"
                    f"Objective: {state.objective}\n"
                    f"Hypothesis card: {json.dumps(state.hypothesis_card, default=str)[:2400]}\n"
                    f"Scientist positions: {json.dumps(positions, default=str)[:6500]}"
                ),
                max_tokens=1000,
            )
            adjudication = self._llm_json(
                state,
                config,
                agent_name="pi_agent",
                task="pi_debate_adjudication",
                system_prompt=(
                    "You are the principal investigator adjudicating a debate among AI scientist agents. "
                    "Revise the hypothesis to preserve supported claims, soften unsupported claims, and enforce guardrails."
                ),
                prompt=(
                    "Return only JSON with keys accepted_claims, softened_or_rejected_claims, revised_hypothesis, "
                    "confidence_adjustment, final_confidence, rationale. final_confidence must be 0-1 or null.\n"
                    f"Objective: {state.objective}\n"
                    f"Current hypothesis card: {json.dumps(state.hypothesis_card, default=str)[:2400]}\n"
                    f"Scientist positions: {json.dumps(positions, default=str)[:6500]}\n"
                    f"Debate critique: {json.dumps(debate, default=str)[:2400]}"
                ),
                max_tokens=1000,
            )
        else:
            positions = self._deterministic_scientist_positions(state, config)
            debate = {
                "agreements": ["Mechanistic relevance is plausible and evidence-supported."],
                "disagreements": ["Strength of intervention-specific support is not established."],
                "overclaims": ["Do not imply clinical efficacy or safety."],
                "required_revisions": ["State the result as a candidate hypothesis requiring validation."],
                "consensus": "support_with_limits",
            }
            adjudication = {
                "accepted_claims": [
                    f"{self._primary_target(state)}-linked pathway modulation is biologically plausible enough to investigate in {self._primary_disease(state)} only if external evidence supports it."
                ],
                "softened_or_rejected_claims": ["Any claim of efficacy or safety is rejected without direct evidence."],
                "revised_hypothesis": state.hypothesis_card.get("hypothesis", ""),
                "confidence_adjustment": -0.03,
                "final_confidence": None,
                "rationale": "Local deterministic debate preserves the bounded hypothesis and lowers confidence slightly.",
            }

        base_confidence = float(state.hypothesis_card.get("confidence", 0.5) or 0.5)
        revised_hypothesis = str(adjudication.get("revised_hypothesis") or "").strip()
        if revised_hypothesis:
            state.hypothesis_card["hypothesis"] = revised_hypothesis
        if adjudication.get("final_confidence") is not None:
            final_confidence = float(adjudication.get("final_confidence"))
        else:
            final_confidence = base_confidence + float(adjudication.get("confidence_adjustment", 0.0) or 0.0)
        confidence_floor = self._evidence_calibrated_confidence_floor(state)
        if confidence_floor is not None and final_confidence < confidence_floor:
            final_confidence = confidence_floor
            state.hypothesis_card.setdefault("limitations", []).append(
                "Confidence was calibrated upward only for target-disease grounding or clinical precedence; it is not an efficacy or safety probability."
            )
        state.hypothesis_card["confidence"] = max(0.0, min(1.0, round(final_confidence, 2)))
        softened = self._string_list(adjudication.get("softened_or_rejected_claims"))
        if softened:
            limitations = state.hypothesis_card.setdefault("limitations", [])
            for item in softened:
                if item not in limitations:
                    limitations.append(item)
        # Rebuild claim graph from the revised hypothesis so claim texts reflect
        # the debate-adjudicated language, not the pre-debate hypothesis_card output.
        if revised_hypothesis:
            revised_claim_graph = build_claim_graph(state.hypothesis_card, state.evidence)
            revised_coverage = build_evidence_coverage_matrix(
                state.context.get("case_profile", {}),
                state.evidence,
                revised_claim_graph,
            )
            state.context["claim_graph"] = revised_claim_graph
            state.context["evidence_coverage_matrix"] = revised_coverage
            state.hypothesis_card["claim_graph"] = revised_claim_graph
            state.hypothesis_card["evidence_coverage_matrix"] = revised_coverage
        debate_record = {
            "scientist_positions": positions,
            "debate": debate,
            "pi_adjudication": adjudication,
            "collaboration_model": (
                "parallel_llm_scientist_panel" if self._llm_enabled(config) else "deterministic_local_scientist_panel"
            ),
        }
        state.context["agent_debate"] = debate_record
        state.hypothesis_card["agent_debate"] = debate_record
        self._record(
            trace,
            "scientist_panel",
            state.current_state.value,
            {
                "hypothesis_card": state.hypothesis_card,
                "evidence_count": len(state.evidence),
                "roles": roles,
            },
            {**debate_record, "revised_hypothesis": state.hypothesis_card.get("hypothesis"), "llm_calls": state.context.get("llm_calls", [])},
        )
        return state

    def _critique_and_refine(
        self,
        state: ResearchRunState,
        trace: list[dict[str, Any]],
        config: dict[str, Any],
    ) -> ResearchRunState:
        state.current_state = AgentStateName.CRITIQUE_AND_REFINE
        if self._llm_enabled(config):
            state.critique = self._llm_json(
                state,
                config,
                agent_name="critic_agent",
                task="skeptical_critique",
                system_prompt=(
                    "You are a skeptical biomedical reviewer. Identify overclaims, missing evidence, "
                    "contradictions, safety gaps, and validation needs. Make abstention explicit when evidence is insufficient."
                ),
                prompt=(
                    "Return only JSON with keys critique_type, severity, critique, recommended_fix, "
                    "abstention_required, claim_boundary.\n"
                    f"Hypothesis card: {json.dumps(state.hypothesis_card, default=str)[:6000]}\n"
                    f"Evidence digest: {json.dumps(self._evidence_digest(state, 14), default=str)[:8000]}\n"
                    f"Scientific strategy: {json.dumps(state.context.get('scientific_strategy', {}), default=str)[:3000]}"
                ),
                max_tokens=1000,
            )
            state.critique.setdefault("claim_boundary", "candidate hypothesis; no clinical efficacy or safety claim")
        else:
            state.critique = {
                "critique_type": "translation_gap",
                "severity": "medium",
                "critique": (
                    "The mechanism is plausible, but deterministic evidence is not sufficient to rank clinical "
                    "candidates or claim efficacy."
                ),
                "recommended_fix": (
                    "Run strict mode with a real LLM, live public APIs, ToolUniverse target-disease tools, "
                    "compound potency/selectivity, ADMET, and safety review before molecule ranking."
                ),
                "abstention_required": False,
                "claim_boundary": "candidate hypothesis; no clinical efficacy or safety claim",
            }
        abstention = build_abstention_assessment(
            state.context.get("objective_classification", {}),
            state.evidence,
            state.context.get("claim_graph", {}),
        )
        state.context["abstention"] = abstention
        state.critique["abstention"] = abstention
        if abstention["abstention_required"]:
            state.critique["abstention_required"] = True
            state.critique["claim_boundary"] = abstention["allowed_output"]
        # Build a minimal task dict for quality-control calls.
        # On local/showcase runs there is no benchmark_task; fall back to
        # gene/disease extracted from the biomedical context so that the
        # actionability and contradiction assessors have entity anchors.
        _benchmark_task = state.context.get("benchmark_task") or {}
        _task_for_critics: dict[str, Any] = {
            "gene_symbol": _benchmark_task.get("gene_symbol") or self._primary_target(state),
            "disease_name": _benchmark_task.get("disease_name") or self._primary_disease(state),
            **{k: v for k, v in _benchmark_task.items() if k not in {"gene_symbol", "disease_name"}},
        }
        biotruth_critic = evaluate_hypothesis(
            task=_task_for_critics,
            hypothesis=state.hypothesis_card,
            evidence=state.evidence,
            tool_calls=state.tool_outputs,
            public_labels=_benchmark_task.get("public_labels", {}),
        )
        contradiction_analysis = detect_contradictions(
            task=_task_for_critics,
            evidence=state.evidence,
            tool_calls=state.tool_outputs,
        )
        actionability_profile = assess_actionability(
            task=_task_for_critics,
            evidence=state.evidence,
            evidence_hierarchy=state.context.get("evidence_hierarchy", {}),
            contradiction_analysis=contradiction_analysis,
        )
        abstention_policy = evaluate_abstention_policy(
            critic=biotruth_critic,
            evidence_hierarchy=state.context.get("evidence_hierarchy", {}),
            contradiction_analysis=contradiction_analysis,
            actionability_profile=actionability_profile,
            existing_abstention=state.context.get("abstention", {}),
            public_labels=_benchmark_task.get("public_labels", {}),
        )
        state.context["adaptive_tool_plan"] = plan_adaptive_tools(
            task=_task_for_critics,
            evidence_hierarchy=state.context.get("evidence_hierarchy", {}),
            contradiction_analysis=contradiction_analysis,
            max_recommendations=max(2, min(int(config.get("strategy_repair_max_queries", 2)) + 2, 6)),
        )
        state.context["biotruth_critic"] = biotruth_critic
        state.context["contradiction_analysis"] = contradiction_analysis
        state.context["actionability_profile"] = actionability_profile
        state.context["abstention_policy"] = abstention_policy
        state.context["scientific_strategy"] = calibrate_scientific_strategy_with_review(
            state.context.get("scientific_strategy", {}),
            evidence=state.evidence,
            critique=state.critique,
            abstention_policy=abstention_policy,
            biotruth_critic=biotruth_critic,
            actionability_profile=actionability_profile,
        )
        state.critique["biotruth_critic"] = biotruth_critic
        state.critique["contradiction_analysis"] = contradiction_analysis
        state.critique["actionability_profile"] = actionability_profile
        state.critique["abstention_policy"] = abstention_policy
        state.hypothesis_card["scientific_strategy"] = state.context["scientific_strategy"]
        state.hypothesis_card["biotruth_critic"] = biotruth_critic
        state.hypothesis_card["contradiction_analysis"] = contradiction_analysis
        state.hypothesis_card["actionability_profile"] = actionability_profile
        state.hypothesis_card["abstention_policy"] = abstention_policy
        if abstention_policy["decision"] in {"abstain", "conflicting"}:
            state.critique["abstention_required"] = True
            state.critique["claim_boundary"] = abstention_policy["claim_boundary"]
            state.context["abstention"] = {
                **state.context.get("abstention", {}),
                "abstention_required": abstention_policy["abstention_required"],
                "reasons": sorted(
                    set(
                        state.context.get("abstention", {}).get("reasons", [])
                        + biotruth_critic.get("abstention_reasons", [])
                        + abstention_policy.get("reasons", [])
                    )
                ),
                "allowed_output": abstention_policy["claim_boundary"],
            }
            self._enforce_abstention_on_hypothesis(state)
        self._record(
            trace,
            "critic_agent",
            state.current_state.value,
            {"hypothesis_card": state.hypothesis_card},
            {**state.critique, "llm_calls": state.context.get("llm_calls", [])},
        )
        return state

    def _enforce_abstention_on_hypothesis(self, state: ResearchRunState) -> None:
        abstention_policy = state.context.get("abstention_policy", {})
        decision = str(abstention_policy.get("decision") or "").lower()
        if decision not in {"abstain", "conflicting"}:
            return

        target = self._primary_target(state)
        disease = self._primary_disease(state)
        boundary = str(abstention_policy.get("claim_boundary") or "insufficient evidence")
        reasons = [str(reason) for reason in abstention_policy.get("reasons", []) if reason]
        reason_text = "; ".join(reasons[:4]) if reasons else "available evidence does not support a bounded claim"

        if decision == "abstain":
            status = "abstained"
            title = f"Insufficient evidence for {target} as a {disease} target"
            hypothesis = (
                f"AutoScientist abstains from supporting {target} as a therapeutic target for {disease}. "
                f"The supported conclusion is that the target-disease claim remains insufficiently grounded: "
                f"{reason_text}. Further work should validate disease relevance before prioritizing mechanism, "
                "translation, or intervention claims."
            )
            confidence = min(float(state.hypothesis_card.get("confidence", 0.0) or 0.0), 0.2)
        else:
            status = "conflicting_evidence"
            title = f"Conflicting evidence review for {target} and {disease}"
            hypothesis = (
                f"AutoScientist does not make an unqualified support claim for {target} in {disease}. "
                f"The evidence is conflicting or materially limited: {reason_text}. Any follow-up should "
                "resolve the conflicting evidence before target prioritization."
            )
            confidence = min(float(state.hypothesis_card.get("confidence", 0.0) or 0.0), 0.45)

        limitations = state.hypothesis_card.setdefault("limitations", [])
        limitations.append(f"Abstention policy decision `{decision}` enforced: {boundary}.")
        state.hypothesis_card.update(
            {
                "title": title,
                "hypothesis": hypothesis,
                "scientific_assessment": [boundary],
                "confidence": round(max(0.0, confidence), 2),
                "status": status,
            }
        )

    def _propose_experiments(
        self,
        state: ResearchRunState,
        trace: list[dict[str, Any]],
        config: dict[str, Any],
    ) -> ResearchRunState:
        state.current_state = AgentStateName.PROPOSE_EXPERIMENTS
        experiments = self.tools["experiment_recommendation_tool"].run(
            {
                "hypothesis_card": state.hypothesis_card,
                "scientific_strategy": state.context.get("scientific_strategy", {}),
                "critique": state.critique,
            }
        ).model_dump()
        base_experiments = experiments["output"]["experiments"]
        ranked = rank_experiments_by_strategy(
            base_experiments,
            state.context.get("scientific_strategy", {}),
        )
        # ── LLM experiment enrichment ─────────────────────────────────────────────
        if self._llm_enabled(config):
            target = self._primary_target(state)
            disease = self._primary_disease(state)
            strategy = state.context.get("scientific_strategy", {})
            gaps = strategy.get("gaps", [])
            gaps_summary = "; ".join(
                f"{g['id']} ({g['severity']}): {g['rationale']}" for g in gaps[:4]
            )
            exp_json = self._llm_json(
                state,
                config,
                agent_name="experiment_designer_agent",
                task="experiment_proposal",
                system_prompt=(
                    "You are an expert translational oncology scientist designing rigorous next validation "
                    "experiments. Propose specific, actionable experiments with clear decision gates, "
                    "success criteria, and failure modes. Prioritize by information gain relative to "
                    "unresolved scientific gaps. Be concrete: name assays, models, and readouts."
                ),
                prompt=(
                    "Return only JSON with key 'experiments': array of 4-5 experiment objects. "
                    "Each must have: name (concise ≤15 words), type "
                    "(computational|wet_lab|computational_plus_wet_lab|clinical_translational), "
                    "cost (low|low-medium|medium|medium-high|high), "
                    "feasibility (high|medium|low), "
                    "expected_information_gain (very_high|high|medium|low), "
                    "decision_gate (1 sentence: when to advance), "
                    "success_criteria (array of 2-3 specific strings), "
                    "failure_modes (array of 1-2 strings).\n"
                    "Rank by: (1) resolving the highest-severity gap, (2) information gain per cost, "
                    "(3) proximity to clinical translation.\n"
                    f"Target: {target}\n"
                    f"Disease: {disease}\n"
                    f"Current hypothesis: {str(state.hypothesis_card.get('hypothesis', ''))[:600]}\n"
                    f"Scientific strategy gaps: {gaps_summary}\n"
                    f"Existing experiment seeds (use as starting points, improve specificity): "
                    f"{json.dumps([e.get('name') for e in ranked[:3]], default=str)}"
                ),
                max_tokens=int(config.get("llm_max_tokens", 1200)),
            )
            llm_experiments = exp_json.get("experiments") if isinstance(exp_json.get("experiments"), list) else []
            if llm_experiments and not exp_json.get("_parse_fallback"):
                # Merge: re-rank the LLM experiments with strategy scoring
                merged = rank_experiments_by_strategy(
                    llm_experiments,
                    state.context.get("scientific_strategy", {}),
                )
                # If LLM produced ≥3 valid experiments, prefer them; else merge with ranked fallback
                state.experiments = merged if len(merged) >= 3 else rank_experiments_by_strategy(
                    llm_experiments + base_experiments,
                    state.context.get("scientific_strategy", {}),
                )
            else:
                state.experiments = ranked
        else:
            state.experiments = ranked
        state.experiments = score_experiment_gates(
            state.experiments,
            state.context.get("case_profile", {}),
            state.context.get("evidence_coverage_matrix", {}),
        )
        state.context["experiment_gate_plan"] = {
            "schema": "autosci.experiment_gate_plan.v0.1",
            "experiments": state.experiments,
            "top_decision_impact_score": state.experiments[0].get("decision_impact_score") if state.experiments else None,
        }
        self._record(
            trace,
            "experiment_designer_agent",
            state.current_state.value,
            {"hypothesis_card": state.hypothesis_card, "critique": state.critique},
            {
                "experiments": state.experiments,
                "scientific_strategy": state.context.get("scientific_strategy", {}),
                "experiment_gate_plan": state.context.get("experiment_gate_plan", {}),
            },
        )
        self._emit_checkpoint(state, "experiments_proposed", config)
        return state

    def _generate_report(
        self,
        state: ResearchRunState,
        trace: list[dict[str, Any]],
        config: dict[str, Any],
    ) -> ResearchRunState:
        state.current_state = AgentStateName.GENERATE_REPORT
        state.report = {
            "title": f"{self._primary_target(state)} / {self._primary_disease(state)} Candidate Hypothesis Report",
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
            "biomedical_context": state.context.get("biomedical_context", {}),
            "objective_classification": state.context.get("objective_classification", {}),
            "case_profile": state.context.get("case_profile", {}),
            "capability_plan": state.context.get("capability_plan", {}),
            "evaluation_criteria": state.context.get("evaluation_criteria", []),
            "claim_graph": state.context.get("claim_graph", {}),
            "evidence_coverage_matrix": state.context.get("evidence_coverage_matrix", {}),
            "experiment_gate_plan": state.context.get("experiment_gate_plan", {}),
            "evidence_hierarchy": state.context.get("evidence_hierarchy", {}),
            "adaptive_tool_plan": state.context.get("adaptive_tool_plan", {}),
            "scientific_strategy": state.context.get("scientific_strategy", {}),
            "abstention": state.context.get("abstention", {}),
            "abstention_policy": state.context.get("abstention_policy", {}),
            "actionability_profile": state.context.get("actionability_profile", {}),
            "biotruth_critic": state.context.get("biotruth_critic", {}),
            "contradiction_analysis": state.context.get("contradiction_analysis", {}),
            "open_scientist": {
                "health": state.context.get("open_scientist_health", {}),
            },
            "llm_calls": state.context.get("llm_calls", []),
        }
        if self._llm_enabled(config):
            max_tokens = int(config.get("llm_max_tokens", 1200))
            rich_mode = max_tokens >= 1000
            report_json = self._llm_json(
                state,
                config,
                agent_name="publisher_agent",
                task="final_report_synthesis",
                system_prompt=(
                    "You are a senior biomedical scientist writing the final synthesis for an AI-generated "
                    "scientific dossier. Produce a precise, evidence-grounded, publication-quality summary. "
                    "Distinguish established clinical precedence from unresolved questions. Do not assert "
                    "clinical efficacy or safety without direct clinical evidence in the retrieved data. "
                    "Never present an established target-drug relationship as a new discovery."
                ),
                prompt=(
                    "Return only JSON with keys: title, summary"
                    + (", key_claims" if rich_mode else "")
                    + ".\n"
                    f"- title: concise scientific title (10-15 words), name the specific target and disease\n"
                    f"- summary: {('180-240' if rich_mode else '80-120')} words. "
                    "Cover: (1) clinical precedence status, (2) key mechanism, "
                    "(3) primary resistance or unresolved question, (4) ranked next step. "
                    "Be specific — name targets, variants, drugs, and trial results present in the evidence. "
                    "Do not invent details absent from the evidence.\n"
                    + (
                        "- key_claims: array of 3-4 strings, each a single falsifiable scientific claim "
                        "directly supported by the retrieved evidence. No efficacy or safety claims.\n"
                        if rich_mode
                        else ""
                    )
                    + "If the evidence shows clinical precedence, state it as precedence and identify the "
                    "remaining scientific uncertainty (resistance, safety, patient-selection) rather than "
                    "treating the target as unvalidated.\n"
                    f"Hypothesis card: {json.dumps(state.hypothesis_card, default=str)[:5000]}\n"
                    f"Evidence digest: {json.dumps(self._evidence_digest(state, 12, 400), default=str)[:4000]}\n"
                    f"Critique: {json.dumps(state.critique, default=str)[:2000]}\n"
                    f"Experiments: {json.dumps(state.experiments[:4], default=str)[:2500]}"
                ),
                max_tokens=max_tokens,
            )
            if report_json.get("title"):
                state.report["title"] = report_json["title"]
            if report_json.get("summary"):
                state.report["summary"] = report_json["summary"]
            key_claims = self._string_list(report_json.get("key_claims"))
            if key_claims:
                state.report["key_claims"] = key_claims
                # Also write to hypothesis_card so it flows into the board post content_json
                state.hypothesis_card["key_claims"] = key_claims
        self._enforce_abstention_on_report(state)
        state.report["report_evaluation"] = evaluate_report_against_criteria(
            state.report,
            state.context.get("evaluation_criteria", []),
        )
        self._record(
            trace,
            "publisher_agent",
            state.current_state.value,
            {
                "hypothesis_card": state.hypothesis_card,
                "critique": state.critique,
                "experiments": state.experiments,
            },
            {
                "report": state.report,
                "report_evaluation": state.report["report_evaluation"],
                "llm_calls": state.context.get("llm_calls", []),
            },
        )
        return state

    def _enforce_abstention_on_report(self, state: ResearchRunState) -> None:
        abstention_policy = state.context.get("abstention_policy", {})
        decision = str(abstention_policy.get("decision") or "").lower()
        if decision not in {"abstain", "conflicting"}:
            return

        self._enforce_abstention_on_hypothesis(state)
        state.report["title"] = state.hypothesis_card.get("title", state.report.get("title"))
        state.report["summary"] = state.hypothesis_card.get("hypothesis", state.report.get("summary"))
        state.report["confidence"] = state.hypothesis_card.get("confidence")
        state.report["decision"] = decision
        state.report["claim_boundary"] = abstention_policy.get("claim_boundary")
        state.report["guardrails"] = list(
            dict.fromkeys(
                [
                    f"Abstention policy decision `{decision}` is enforced.",
                    str(abstention_policy.get("claim_boundary") or "Do not make an unsupported target-disease claim."),
                    "No clinical efficacy claim is made.",
                    "No safety claim is made.",
                    *[str(item) for item in state.report.get("guardrails", [])],
                ]
            )
        )

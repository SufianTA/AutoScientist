from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Callable

from app.services.llm_provider import call_llm, parse_json_object, require_real_provider
from app.services.tooluniverse_adapter import ToolUniverseAdapter
from agents.app.graph import AgentOrchestrator
from agents.app.model_tool_runner import execute_model_tool
from agents.app.state import AgentStateName, ResearchRunState


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
        trace.append(trace_item)
        callback = getattr(self, "_progress_callback", None)
        if callable(callback):
            callback(trace_item)

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
        result = call_llm(
            provider=config["llm_provider"],
            model=config["llm_model"],
            api_key_env_var=config.get("llm_api_key_env_var") or None,
            base_url=config.get("llm_base_url") or None,
            system_prompt=system_prompt,
            prompt=prompt,
            temperature=0.2,
            max_tokens=max_tokens,
        )
        try:
            result["json"] = parse_json_object(result["text"])
        except RuntimeError:
            compact_prompt = (
                f"{prompt}\n\nYour previous response was not parseable JSON. "
                "Return one compact JSON object only, with no markdown and no commentary. "
                "Keep every array to at most 5 short strings."
            )
            result = call_llm(
                provider=config["llm_provider"],
                model=config["llm_model"],
                api_key_env_var=config.get("llm_api_key_env_var") or None,
                base_url=config.get("llm_base_url") or None,
                system_prompt=system_prompt,
                prompt=compact_prompt,
                temperature=0.0,
                max_tokens=min(max_tokens, 900),
            )
            try:
                result["json"] = parse_json_object(result["text"])
            except RuntimeError:
                result["json"] = self._fallback_llm_json(task, result["text"])
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
        result = call_llm(
            provider=config["llm_provider"],
            model=config["llm_model"],
            api_key_env_var=config.get("llm_api_key_env_var") or None,
            base_url=config.get("llm_base_url") or None,
            system_prompt=system_prompt,
            prompt=prompt,
            temperature=0.2,
            max_tokens=max_tokens,
        )
        try:
            parsed = parse_json_object(result["text"])
        except RuntimeError:
            compact_prompt = (
                f"{prompt}\n\nYour previous response was not parseable JSON. "
                "Return one compact JSON object only, with no markdown and no commentary. "
                "Keep every array to at most 5 short strings."
            )
            result = call_llm(
                provider=config["llm_provider"],
                model=config["llm_model"],
                api_key_env_var=config.get("llm_api_key_env_var") or None,
                base_url=config.get("llm_base_url") or None,
                system_prompt=system_prompt,
                prompt=compact_prompt,
                temperature=0.0,
                max_tokens=min(max_tokens, 900),
            )
            try:
                parsed = parse_json_object(result["text"])
            except RuntimeError:
                parsed = self._fallback_llm_json(task, result["text"])
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
        return self._normalize_context(context, state.objective)

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
        genes = [
            match
            for match in re.findall(r"\b[A-Z][A-Z0-9]{2,9}\b", objective)
            if match not in stop and not match.startswith("HTTP")
        ]
        diseases: list[str] = []
        for pattern in [
            r"for ([A-Z][A-Za-z0-9 /-]+?)(?:\.|,|;| and | with | by |$)",
            r"driven ([A-Z][A-Za-z0-9 /-]+?)(?:\.|,|;| and | with | by |$)",
            r"in ([A-Z][A-Za-z0-9 /-]+?)(?:\.|,|;| and | with | by |$)",
        ]:
            match = re.search(pattern, objective)
            if match:
                diseases.append(match.group(1).strip())
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
        queries = []
        if genes and diseases:
            queries.append(f"{genes[0]} {diseases[0]} mechanism")
            queries.append(f"{genes[0]} {diseases[0]} safety therapeutic")
        else:
            queries.append(objective[:180])
        return {
            "primary_genes": list(dict.fromkeys(genes))[:4],
            "diseases": list(dict.fromkeys(diseases))[:3],
            "candidate_interventions": list(dict.fromkeys(candidates))[:6],
            "pathways": [],
            "pubmed_queries": queries[:4],
            "analysis_goal": objective,
            "extraction_method": "heuristic",
        }

    def _normalize_context(self, context: dict[str, Any], objective: str) -> dict[str, Any]:
        genes = self._string_list(context.get("primary_genes"))
        diseases = []
        for disease in self._string_list(context.get("diseases")):
            cleaned = re.sub(r"^[A-Z0-9]+-driven\s+", "", disease, flags=re.I).strip()
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
        genes = list(dict.fromkeys([*explicit_genes, *genes]))[:4]
        normalized = {
            "primary_genes": genes,
            "diseases": diseases[:2],
            "candidate_interventions": self._string_list(context.get("candidate_interventions"))[:6],
            "pathways": self._string_list(context.get("pathways"))[:4],
            "pubmed_queries": self._string_list(context.get("pubmed_queries"))[:4],
            "analysis_goal": str(context.get("analysis_goal") or objective),
            "extraction_method": context.get("extraction_method", "llm"),
        }
        if not normalized["pubmed_queries"]:
            pieces = normalized["primary_genes"] + normalized["diseases"] + normalized["pathways"]
            base_query = " ".join(pieces) or objective[:180]
            normalized["pubmed_queries"] = [
                f"{base_query} mechanism",
                f"{base_query} therapeutic safety",
                f"{base_query} candidate intervention",
            ]
        else:
            normalized["pubmed_queries"] = [
                re.sub(r"([A-Z0-9]+)\s+\1-driven\s+", r"\1 ", query, flags=re.I)
                for query in normalized["pubmed_queries"]
            ]
        return normalized

    def _string_list(self, value: Any) -> list[str]:
        if not value:
            return []
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    def _evidence_digest(self, state: ResearchRunState, limit: int = 12) -> list[dict[str, Any]]:
        def rank(item: dict[str, Any]) -> tuple[float, int]:
            score = item.get("score", {}).get("score")
            try:
                numeric_score = float(score)
            except (TypeError, ValueError):
                numeric_score = 0.0
            source = str(item.get("source", ""))
            source_bonus = 0
            if "ToolUniverse" in source or "OpenTargets" in source:
                source_bonus += 2
            if source.startswith("PubMed"):
                source_bonus += 1
            if source == "NCBI Gene":
                source_bonus += 1
            return (numeric_score, source_bonus)

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
                    "text": str(item.get("text", ""))[:900],
                    "citations": citations,
                }
            )
        return digest

    def _explicit_gene_symbols(self, objective: str) -> list[str]:
        stop = {"AND", "THE", "USE", "NOT", "DNA", "RNA", "LLM"}
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
        return diseases[0] if diseases else "the disease context"

    def _plan_research(
        self,
        state: ResearchRunState,
        trace: list[dict[str, Any]],
        config: dict[str, Any],
    ) -> ResearchRunState:
        state.current_state = AgentStateName.PLAN_RESEARCH
        biomedical_context = self._extract_context(state, config)
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
        self._record(
            trace,
            "finder_agent",
            state.current_state.value,
            {
                "objective": state.objective,
                "biomedical_context": state.context.get("biomedical_context", {}),
                "available_custom_tools": sorted(self.tools.keys()),
            },
            {
                "selected_tools": state.selected_tools,
                "selection_policy": (
                    "live public APIs plus ToolUniverse/OpenTargets and configured model tools"
                    if config.get("real_data_enabled")
                    else "local deterministic planning and scoring tools plus configured model tools"
                ),
            },
        )
        return state

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
        self._record(
            trace,
            "mechanism_agent",
            state.current_state.value,
            {"selected_tools": state.selected_tools},
            {
                "evidence": state.evidence,
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
        genes = context.get("primary_genes", [])[:2]
        diseases = context.get("diseases", [])[:3]
        candidates = context.get("candidate_interventions", [])[:8]
        pubmed_queries = context.get("pubmed_queries", [])[:5]
        live_calls: list[tuple[str, str, dict[str, Any]]] = []
        for gene in genes:
            live_calls.append(("knowledge_agent", "ncbi_gene_profile_tool", {"gene_symbol": gene, "organism": "Homo sapiens"}))
        for query in pubmed_queries:
            live_calls.append(("literature_agent", "pubmed_literature_search_tool", {"query": query, "retmax": 5}))
        if candidates:
            live_calls.append(("molecule_agent", "pubchem_candidate_lookup_tool", {"names": candidates}))
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

        def execute_call(agent_name: str, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
            if tool_name in self.tools:
                result = self.tools[tool_name].run(payload).model_dump()
                source = "live_public_biomedical"
            else:
                tooluniverse_adapter = ToolUniverseAdapter(scan_all=False)
                result = tooluniverse_adapter.execute(tool_name, payload)
                source = "tooluniverse"
            return {
                "agent_name": agent_name,
                "tool_name": tool_name,
                "tool_source": source,
                "input": payload,
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
        follow_up_outputs = self._run_tooluniverse_followups(state, live_tool_outputs)
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
                "tool_output_count": len(state.tool_outputs),
                "custom_model_tool_count": len(model_tool_outputs),
                "live_public_tool_count": len(
                    [item for item in live_tool_outputs if item["tool_source"] == "live_public_biomedical"]
                ),
                "tooluniverse_tool_count": len(
                    [item for item in live_tool_outputs if item["tool_source"] == "tooluniverse"]
                )
                + len(follow_up_outputs),
                "agent_tool_assignments": [
                    {
                        "agent_name": item["agent_name"],
                        "tool_name": item["tool_name"],
                        "status": item["result"].get("status"),
                    }
                    for item in [*live_tool_outputs, *follow_up_outputs]
                ],
            },
        )
        return state

    def _run_tooluniverse_followups(
        self,
        state: ResearchRunState,
        live_tool_outputs: list[dict[str, Any]],
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
        for efo_id in list(dict.fromkeys(efo_ids))[:2]:
            result = adapter.execute("OpenTargets_get_associated_targets_by_disease_efoId", {"efoId": efo_id})
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
        for item in state.evidence:
            if item.get("source", "").startswith("PubMed:") and item.get("structured", {}).get("count") == 0:
                score_output = {
                    "label": "irrelevant",
                    "score": 0.1,
                    "evidence_type": "literature_search",
                    "rationale": "The live PubMed query returned zero records, so it cannot support the hypothesis.",
                    "warnings": ["Absence of retrieved records is not evidence against the hypothesis."],
                }
            elif self._llm_enabled(config):
                score_output = self._llm_json(
                    state,
                    config,
                    agent_name="critic_agent",
                    task="evidence_quality_scoring",
                    system_prompt=(
                        "You are a skeptical biomedical evidence evaluator. Classify whether the evidence "
                        "supports, weakly supports, is mechanistically relevant, is irrelevant, contradicts, "
                        "or indicates safety/translational concern. Do not overclaim."
                    ),
                    prompt=(
                        "Return only JSON with keys label, score, evidence_type, rationale, warnings. "
                        "Allowed labels: strong_support, weak_support, mechanistic_relevance, irrelevant, "
                        "contradicts, safety_concern. Score must be 0-1.\n"
                        f"Hypothesis: {hypothesis_seed}\n"
                        f"Evidence source: {item['source']}\n"
                        f"Evidence text: {item['text']}\n"
                        f"Structured evidence: {json.dumps(item.get('structured', {}), default=str)[:3500]}"
                    ),
                    max_tokens=700,
                )
                score_output["score"] = float(score_output.get("score", 0.0))
            else:
                score = self.tools["evidence_quality_scorer_tool"].run(
                    {
                        "hypothesis": hypothesis_seed,
                        "evidence_text": item["text"],
                        "evidence_source": item["source"],
                    }
                ).model_dump()
                state.tool_outputs.append(
                    {
                        "tool_name": "evidence_quality_scorer_tool",
                        "tool_source": "custom",
                        "result": score,
                    }
                )
                score_output = score["output"]
            scored.append({**item, "score": score_output})
        state.evidence = scored
        self._record(
            trace,
            "critic_agent",
            state.current_state.value,
            {"evidence_count": len(scored), "strictness": config.get("evidence_strictness", "balanced")},
            {"scored_evidence": scored, "llm_calls": state.context.get("llm_calls", [])},
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
            hypothesis_json = self._llm_json(
                state,
                config,
                agent_name="mechanism_agent",
                task="hypothesis_synthesis",
                system_prompt=(
                    "You are a biomedical mechanism scientist. Synthesize a cautious therapeutic or "
                    "mechanistic candidate hypothesis from the retrieved evidence. Keep guardrails explicit."
                ),
                prompt=(
                    "Return only JSON with keys title, hypothesis, scientific_assessment, "
                    "candidate_intervention_summary, limitations. Use short values. "
                    "scientific_assessment and limitations are arrays of at most 3 short strings. "
                    "The hypothesis must be at most 120 words. Do not assert efficacy or safety. "
                    "Do not assert ligand-independent constitutive signaling unless the retrieved evidence directly supports it; "
                    "when evidence is mixed, use broader wording such as aberrant or neomorphic pathway signaling.\n"
                    f"Objective: {state.objective}\n"
                    f"Evidence digest: {json.dumps(self._evidence_digest(state, 14), default=str)[:9000]}"
                ),
                max_tokens=1000,
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
        self._record(
            trace,
            "mechanism_agent",
            state.current_state.value,
            {"scored_evidence": state.evidence},
            {"hypothesis_card": state.hypothesis_card, "llm_calls": state.context.get("llm_calls", [])},
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
        positions = []
        for role in self._debate_scientist_roles(config):
            agent = role["agent_name"]
            if agent == "critic_agent":
                position = "The hypothesis is plausible but must remain bounded to computational prioritization."
                concerns = [
                    "Tool and literature evidence do not prove clinical efficacy.",
                    "Candidate interventions require potency, selectivity, dose, and safety review.",
                ]
                vote = "revise"
                confidence_delta = -0.05
            elif agent == "safety_agent":
                position = "Safety and translation gaps should lower confidence until intervention-specific safety is reviewed."
                concerns = [
                    "No safety claim should be made from target/pathway evidence alone.",
                    "Pediatric and rare-disease translation risks require explicit review.",
                ]
                vote = "revise"
                confidence_delta = -0.05
            else:
                position = (
                    "Retrieved evidence supports a bounded mechanistic hypothesis, but not validated therapeutic efficacy."
                )
                concerns = ["Evidence should be separated into direct support, indirect pathway relevance, and gaps."]
                vote = "support_with_limits"
                confidence_delta = 0.02
            positions.append(
                {
                    "agent_name": agent,
                    "discipline": role["discipline"],
                    "position": position,
                    "key_claims": [state.hypothesis_card.get("hypothesis", "")],
                    "supporting_evidence_sources": evidence_sources,
                    "concerns": concerns,
                    "requested_followups": ["Run intervention-specific potency, selectivity, and safety evidence retrieval."],
                    "confidence_delta": confidence_delta,
                    "vote": vote,
                    "mode": "deterministic_local",
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
                f"Current hypothesis card: {json.dumps(state.hypothesis_card, default=str)[:5000]}\n"
                f"Scored evidence digest: {json.dumps(self._evidence_digest(state, 14), default=str)[:10000]}"
            ),
            max_tokens=900,
        )
        position["agent_name"] = agent_name
        position["discipline"] = role["discipline"]
        return position, call_summary

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
            max_workers = max(1, min(int(config.get("agent_count", 6)), len(roles)))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(self._scientist_position_from_llm, state, config, role) for role in roles]
                for future in as_completed(futures):
                    position, call_summary = future.result()
                    positions.append(position)
                    llm_calls.append(call_summary)
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
                    f"Hypothesis card: {json.dumps(state.hypothesis_card, default=str)[:5000]}\n"
                    f"Scientist positions: {json.dumps(positions, default=str)[:10000]}"
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
                    f"Current hypothesis card: {json.dumps(state.hypothesis_card, default=str)[:5000]}\n"
                    f"Scientist positions: {json.dumps(positions, default=str)[:10000]}\n"
                    f"Debate critique: {json.dumps(debate, default=str)[:5000]}"
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
        state.hypothesis_card["confidence"] = max(0.0, min(1.0, round(final_confidence, 2)))
        softened = self._string_list(adjudication.get("softened_or_rejected_claims"))
        if softened:
            limitations = state.hypothesis_card.setdefault("limitations", [])
            for item in softened:
                if item not in limitations:
                    limitations.append(item)
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
                    f"Evidence digest: {json.dumps(self._evidence_digest(state, 14), default=str)[:8000]}"
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
        self._record(
            trace,
            "critic_agent",
            state.current_state.value,
            {"hypothesis_card": state.hypothesis_card},
            {**state.critique, "llm_calls": state.context.get("llm_calls", [])},
        )
        return state

    def _propose_experiments(
        self,
        state: ResearchRunState,
        trace: list[dict[str, Any]],
        config: dict[str, Any],
    ) -> ResearchRunState:
        state.current_state = AgentStateName.PROPOSE_EXPERIMENTS
        experiments = self.tools["experiment_recommendation_tool"].run(
            {"hypothesis_card": state.hypothesis_card}
        ).model_dump()
        state.experiments = experiments["output"]["experiments"]
        self._record(
            trace,
            "experiment_designer_agent",
            state.current_state.value,
            {"hypothesis_card": state.hypothesis_card, "critique": state.critique},
            {"experiments": state.experiments},
        )
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
            "llm_calls": state.context.get("llm_calls", []),
        }
        if self._llm_enabled(config):
            report_json = self._llm_json(
                state,
                config,
                agent_name="publisher_agent",
                task="final_report_synthesis",
                system_prompt=(
                    "You are a biomedical report publisher. Write a concise final scientific synthesis "
                    "using only the supplied evidence and explicit guardrails."
                ),
                prompt=(
                    "Return only JSON with keys title and summary. Do not claim clinical efficacy or safety.\n"
                    f"Hypothesis card: {json.dumps(state.hypothesis_card, default=str)[:6000]}\n"
                    f"Critique: {json.dumps(state.critique, default=str)[:3000]}\n"
                    f"Experiments: {json.dumps(state.experiments, default=str)[:3000]}"
                ),
                max_tokens=800,
            )
            if report_json.get("title"):
                state.report["title"] = report_json["title"]
            if report_json.get("summary"):
                state.report["summary"] = report_json["summary"]
        self._record(
            trace,
            "publisher_agent",
            state.current_state.value,
            {
                "hypothesis_card": state.hypothesis_card,
                "critique": state.critique,
                "experiments": state.experiments,
            },
            {"report": state.report, "llm_calls": state.context.get("llm_calls", [])},
        )
        return state

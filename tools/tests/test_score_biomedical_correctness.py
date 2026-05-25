import json
from pathlib import Path

from tools import score_biomedical_correctness as scorer
from tools.score_biomedical_correctness import (
    build_judge_prompt,
    build_score_packet,
    build_score_packets,
    heuristic_score,
    load_benchmark_results,
    load_json,
    score_packets,
    summarize_scores,
    write_outputs,
)


def test_biotruth_heuristic_scoring_writes_summary(tmp_path: Path) -> None:
    bench = tmp_path / "bench"
    bench.mkdir()
    result = {
        "schema": "autosci.benchmark_task_result.v0.1",
        "task": {
            "id": "il6_rheumatoid_arthritis__target_validity_review",
            "case_id": "il6_rheumatoid_arthritis",
            "template_id": "target_validity_review",
            "domain": "autoimmune_inflammation",
            "gene_symbol": "IL6",
            "disease_name": "rheumatoid arthritis",
            "public_labels": {
                "open_targets_association_score": 0.82,
                "pubmed_gene_disease_count": 100,
            },
        },
        "ablation": "full",
        "run_id": "run_1",
        "status": "completed",
        "integrations": {
            "public_biomedical": {"executed": True, "call_count": 4},
            "tooluniverse": {"executed": True, "call_count": 2},
        },
        "replay": {"available": True},
        "value_assessment": {"score": 95},
        "report": {
            "hypothesis": {
                "title": "IL6 in rheumatoid arthritis",
                "text": "IL6 signaling is mechanistically linked to rheumatoid arthritis with uncertainty and safety caveats.",
            },
            "evidence": [
                {"source": "Open Targets", "text": "IL6 has target-disease evidence."},
                {"source": "PubMed", "text": "IL6 rheumatoid arthritis literature."},
                {"source": "ToolUniverse", "text": "Mechanism and pathway evidence."},
                {"source": "Open Targets", "text": "Clinical and tractability signal."},
                {"source": "PubMed", "text": "Counterevidence and limitations."},
                {"source": "PubMed", "text": "Safety and toxicity considerations."},
            ],
            "experiments": [
                {
                    "name": "Perturb IL6 pathway in disease-relevant cells",
                    "readout": "mechanism, controls, and failure criteria",
                }
            ],
            "guardrails": ["Do not infer clinical use from association score alone."],
        },
        "tool_calls": [
            {"tool_name": "pubmed_literature_search_tool", "tool_source": "live_public_biomedical", "status": "success"},
            {"tool_name": "opentargets_association_tool", "tool_source": "tooluniverse", "status": "success"},
            {"tool_name": "replay_export", "tool_source": "local_board", "status": "success"},
            {"tool_name": "memory_write", "tool_source": "scistate_graph", "status": "success"},
        ],
    }
    (bench / "il6_rheumatoid_arthritis__target_validity_review__full.json").write_text(
        json.dumps(result),
        encoding="utf-8",
    )

    rubric = load_json(Path("benchmarks/biotruth_rubric_v0_1.json"))
    results = load_benchmark_results(bench, ablations=["full"])
    packets = build_score_packets(results, rubric)
    scored = [{"packet": packets[0], "score": heuristic_score(packets[0], rubric)}]

    class Args:
        bench_dir = bench
        mode = "heuristic"

    summary = summarize_scores(scored, Args(), rubric)
    output = write_outputs(scored, summary, bench)

    assert summary["overall"]["mean_weighted_score"] > 50
    assert summary["by_ablation"]["full"]["count"] == 1
    assert Path(output["scores_path"]).exists()
    assert Path(output["markdown_path"]).exists()


def test_judge_prompt_uses_exact_json_schema() -> None:
    rubric = load_json(Path("benchmarks/biotruth_rubric_v0_1.json"))
    prompt = build_judge_prompt(
        {"task": {"id": "il6_rheumatoid_arthritis__target_validity_review"}, "answer": {}},
        rubric,
    )

    assert '"..."' not in prompt
    for dimension in rubric["dimensions"]:
        assert f'"{dimension["id"]}": 0' in prompt


def test_score_packet_includes_biotruth_critic() -> None:
    packet = build_score_packet(
        {
            "task": {"id": "case", "gene_symbol": "BRAF", "disease_name": "melanoma"},
            "ablation": "full",
            "run_id": "run_1",
            "status": "completed",
            "report": {
                "biotruth_critic": {
                    "schema": "autosci.biotruth_critic.v0.1",
                    "verdict": "support",
                    "weighted_score": 82.0,
                }
            },
        },
        {"schema": "autosci.biotruth_rubric.v0.1"},
    )

    assert packet["answer"]["biotruth_critic"]["verdict"] == "support"


def test_judge_mode_records_provider_failure(monkeypatch) -> None:
    rubric = load_json(Path("benchmarks/biotruth_rubric_v0_1.json"))

    def fail_json(**_: object) -> dict[str, object]:
        raise RuntimeError("bad judge json")

    monkeypatch.setattr(scorer, "call_llm_json", fail_json)

    class Args:
        max_results = 0
        mode = "judge"
        llm_provider = "gemini"
        llm_model = "gemini-2.5-flash"
        llm_api_key_env_var = ""
        llm_base_url = ""
        llm_max_tokens = 1600

    scored = score_packets(Args(), [{"task": {"id": "case_1"}}], rubric)

    assert scored[0]["score"]["mode"] == "llm_judge_failed"
    assert "judge_failed" in scored[0]["score"]["critical_failures"]


def test_heuristic_score_rewards_evidence_hierarchy_and_biotruth_critic() -> None:
    rubric = load_json(Path("benchmarks/biotruth_rubric_v0_1.json"))
    packet = build_score_packet(
        {
            "task": {
                "id": "case",
                "gene_symbol": "TNF",
                "disease_name": "rheumatoid arthritis",
                "public_labels": {"open_targets_association_score": 0.75, "pubmed_gene_disease_count": 200},
            },
            "ablation": "full",
            "run_id": "run_1",
            "status": "completed",
            "integrations": {
                "public_biomedical": {"executed": True, "call_count": 5},
                "tooluniverse": {"executed": True, "call_count": 2},
            },
            "replay": {"available": True},
            "report": {
                "hypothesis": {"text": "TNF rheumatoid arthritis hypothesis with safety and confidence limits."},
                "evidence": [{"source": "ClinicalTrials.gov", "text": "clinical trial evidence"}] * 8,
                "experiments": [{"name": "controlled perturbation", "readout": "failure criteria"}],
                "evidence_hierarchy": {
                    "high_tier_evidence_count": 2,
                    "hierarchy_score": 72,
                },
                "biotruth_critic": {"verdict": "support", "weighted_score": 84},
                "abstention_policy": {"decision": "support_allowed"},
                "contradiction_analysis": {"contradiction_search_attempted": True, "contradiction_count": 0},
            },
            "tool_calls": [
                {"tool_name": "clinical_trials_search_tool", "tool_source": "live_public_biomedical", "status": "success"}
            ]
            * 5,
        },
        rubric,
    )

    score = heuristic_score(packet, rubric)

    assert score["evidence_certainty"] == "high"
    assert score["dimension_scores"]["evidence_grounding"] >= 4


def test_heuristic_score_flags_unresolved_contradiction() -> None:
    rubric = load_json(Path("benchmarks/biotruth_rubric_v0_1.json"))
    packet = build_score_packet(
        {
            "task": {
                "id": "case",
                "gene_symbol": "TNF",
                "disease_name": "rheumatoid arthritis",
                "public_labels": {"open_targets_association_score": 0.75, "pubmed_gene_disease_count": 200},
            },
            "ablation": "full",
            "run_id": "run_1",
            "status": "completed",
            "integrations": {"public_biomedical": {"executed": True, "call_count": 3}},
            "report": {
                "hypothesis": {"text": "TNF rheumatoid arthritis is validated as therapeutic."},
                "evidence": [{"source": "PubMed", "text": "TNF rheumatoid arthritis"}],
                "evidence_hierarchy": {"high_tier_evidence_count": 0, "hierarchy_score": 10},
                "biotruth_critic": {"verdict": "conflicting", "weighted_score": 35},
                "abstention_policy": {"decision": "support_allowed"},
                "contradiction_analysis": {"contradiction_search_attempted": True, "contradiction_count": 1},
            },
        },
        rubric,
    )

    score = heuristic_score(packet, rubric)

    assert score["evidence_certainty"] == "very_low"
    assert "unsupported_causal_claim" in score["critical_failures"]


def test_v02_rubric_scores_expected_decision_and_label_breakdowns() -> None:
    rubric = load_json(Path("benchmarks/biotruth_rubric_v0_2.json"))
    packet = build_score_packet(
        {
            "task": {
                "id": "case",
                "domain": "oncology",
                "gene_symbol": "CFTR",
                "disease_name": "melanoma",
                "gold_label": "insufficient_evidence",
                "expected_decision": "abstain",
                "expected_evidence": ["absence_of_target_disease_support"],
                "public_labels": {"open_targets_association_score": 0.0, "pubmed_gene_disease_count": 0},
            },
            "ablation": "full",
            "run_id": "run_1",
            "status": "completed",
            "integrations": {"public_biomedical": {"executed": True, "call_count": 2}},
            "report": {
                "hypothesis": {"text": "CFTR melanoma evidence is insufficient; abstain from therapeutic claim."},
                "evidence": [{"source": "PubMed", "text": "CFTR melanoma no disease-specific support"}],
                "evidence_hierarchy": {"high_tier_evidence_count": 0, "hierarchy_score": 20},
                "biotruth_critic": {"verdict": "abstain", "weighted_score": 25},
                "abstention_policy": {"decision": "abstain"},
                "contradiction_analysis": {"contradiction_search_attempted": True, "contradiction_count": 0},
            },
        },
        rubric,
    )
    score = heuristic_score(packet, rubric)

    class Args:
        bench_dir = Path("unused")
        mode = "heuristic"

    summary = summarize_scores([{"packet": packet, "score": score}], Args(), rubric)

    assert packet["task"]["gold_label"] == "insufficient_evidence"
    assert score["dimension_scores"]["scientific_decision_correctness"] == 5
    assert summary["by_gold_label"]["insufficient_evidence"]["count"] == 1
    assert summary["by_expected_decision"]["abstain"]["count"] == 1


def test_score_packet_preserves_abstention_decision_when_policy_is_truncated() -> None:
    rubric = load_json(Path("benchmarks/biotruth_rubric_v0_2.json"))
    large_inputs = {f"field_{index}": "x" * 120 for index in range(40)}
    packet = build_score_packet(
        {
            "task": {
                "id": "egfr_ra",
                "domain": "autoimmune_inflammation",
                "gene_symbol": "EGFR",
                "disease_name": "rheumatoid arthritis",
                "gold_label": "insufficient_evidence",
                "expected_decision": "abstain",
                "public_labels": {
                    "open_targets_association_score": 0.0,
                    "pubmed_gene_disease_count": 235,
                },
            },
            "ablation": "full",
            "run_id": "run_1",
            "status": "completed",
            "integrations": {
                "public_biomedical": {"executed": True, "call_count": 10},
                "tooluniverse": {"executed": True, "call_count": 3},
            },
            "report": {
                "hypothesis": {
                    "text": "AutoScientist abstains from supporting EGFR as a target for rheumatoid arthritis.",
                    "confidence": 0.2,
                    "status": "abstained",
                },
                "evidence": [{"source": "OpenTargets", "text": "EGFR rheumatoid arthritis not matched"}] * 8,
                "evidence_hierarchy": {"high_tier_evidence_count": 1, "hierarchy_score": 55},
                "biotruth_critic": {"verdict": "weak_support", "weighted_score": 70},
                "abstention_policy": {
                    "decision": "abstain",
                    "abstention_required": True,
                    "claim_boundary": "insufficient-evidence response",
                    "inputs": large_inputs,
                },
                "contradiction_analysis": {"contradiction_search_attempted": True, "finding_count": 0},
            },
            "replay": {"available": True},
            "tool_calls": [{"tool_name": "opentargets", "status": "success"}] * 6,
        },
        rubric,
    )

    assert packet["answer"]["abstention_policy"]["truncated"] is True
    assert packet["answer"]["abstention_policy"]["decision"] == "abstain"

    score = heuristic_score(packet, rubric)

    assert score["dimension_scores"]["scientific_decision_correctness"] == 5
    assert "incorrect_abstention_behavior" not in score["critical_failures"]


def test_support_allowed_is_not_critical_failure_for_safety_only_limitations() -> None:
    rubric = load_json(Path("benchmarks/biotruth_rubric_v0_2.json"))
    packet = build_score_packet(
        {
            "task": {
                "id": "tnf_ra",
                "domain": "autoimmune_inflammation",
                "gene_symbol": "TNF",
                "disease_name": "rheumatoid arthritis",
                "gold_label": "strong_support",
                "expected_decision": "support_allowed",
                "public_labels": {
                    "open_targets_association_score": 0.64,
                    "pubmed_gene_disease_count": 13000,
                },
            },
            "ablation": "full",
            "run_id": "run_1",
            "status": "completed",
            "integrations": {
                "public_biomedical": {"executed": True, "call_count": 10},
                "tooluniverse": {"executed": True, "call_count": 4},
            },
            "report": {
                "hypothesis": {
                    "text": "TNF is supported as a rheumatoid arthritis target with explicit safety limitations.",
                    "confidence": 0.72,
                },
                "evidence": [{"source": "OpenTargets", "text": "TNF rheumatoid arthritis target validation"}] * 8,
                "evidence_hierarchy": {"high_tier_evidence_count": 3, "hierarchy_score": 68},
                "biotruth_critic": {"verdict": "support", "weighted_score": 90},
                "abstention_policy": {"decision": "support_allowed"},
                "contradiction_analysis": {
                    "contradiction_search_attempted": True,
                    "finding_count": 4,
                    "categories": ["safety", "resistance_or_compensation"],
                    "coverage": {"negative_evidence": False, "safety": True},
                },
                "guardrails": ["No safety claim is made."],
            },
            "replay": {"available": True},
            "tool_calls": [{"tool_name": "opentargets", "status": "success"}] * 6,
        },
        rubric,
    )

    score = heuristic_score(packet, rubric)

    assert score["dimension_scores"]["scientific_decision_correctness"] == 5
    assert "unsupported_causal_claim" not in score["critical_failures"]

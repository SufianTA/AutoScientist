import json
from pathlib import Path

from tools.build_biotruth_benchmark import expand_tasks
from tools.run_cancer_resistance_case_study import build_pipeline_argv, parse_args


MANIFEST_PATH = Path("benchmarks/autoscientist_deep_egfr_nsclc_resistance_case.json")
RUNBOOK_PATH = Path("docs/DEEP_EGFR_NSCLC_RESISTANCE_CASE_STUDY_RUNBOOK.md")
SCRIPT_PATH = Path("tools/run_cancer_resistance_case_study.py")


def test_deep_egfr_nsclc_manifest_is_auditable_and_not_person_specific() -> None:
    manifest_text = MANIFEST_PATH.read_text(encoding="utf-8")
    runbook_text = RUNBOOK_PATH.read_text(encoding="utf-8")
    script_text = SCRIPT_PATH.read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)

    combined = "\n".join([manifest_text, runbook_text, script_text])
    banned_names = ["".join(["Mar", "inka"]), "Zit" + "nik", "Har" + "vard"]
    for banned_name in banned_names:
        assert banned_name not in combined
    assert "personalized_for_reviewer" not in combined
    assert "named_external_reviewer" not in combined

    assert manifest["schema"] == "autosci.biotruth_manifest.v0.1"
    assert manifest["selection_policy"]["recommended_agent_count"] == 12
    assert len(manifest["seed_cases"]) == 1
    assert len(manifest["task_templates"]) == 4

    case = manifest["seed_cases"][0]
    assert case["id"] == "egfr_osimertinib_nsclc_resistance_deep"
    assert case["gene_symbol"] == "EGFR"
    assert case["disease_name"] == "non-small cell lung carcinoma"
    assert case["expected_decision"] == "support_allowed"
    assert "osimertinib_resistance" in case["expected_evidence"]
    assert "MET_amplification_or_bypass" in case["expected_evidence"]
    assert "counterevidence_or_missing_evidence" in case["expected_evidence"]
    assert case["public_labels"]["open_targets_association_status"] == "matched"
    assert case["public_labels"]["open_targets_matched_disease_id"] == "EFO_0003060"

    tasks = expand_tasks(manifest)
    assert len(tasks) == 4
    for task in tasks:
        objective = task["objective"].lower()
        assert "egfr" in objective
        assert "osimertinib" in objective
        assert "non-small cell lung carcinoma" in objective
        assert "resistance" in objective
        assert any(term in objective for term in ["met", "emt", "c797s", "histologic"])
        assert {"public_biomedical", "tooluniverse", "sciflow_policy", "scistate_graph"}.issubset(
            set(task["expected_capabilities"])
        )


def test_cancer_resistance_runner_defaults_to_strict_real_showcase_study() -> None:
    args = parse_args(["--dry-run"])
    argv = build_pipeline_argv(args)

    assert "--strict-real-run" in argv
    assert "--train-neural-policy" in argv
    assert "--skip-build" in argv
    assert "benchmarks/autoscientist_deep_egfr_nsclc_resistance_case.json" in argv
    assert args.ablations == ["full"]
    assert args.agent_count == 12
    assert args.strategy_repair_max_queries == 6
    assert args.review_package_name == "autoscientist_deep_egfr_nsclc_resistance_review"

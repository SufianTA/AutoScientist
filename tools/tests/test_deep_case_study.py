import json
from pathlib import Path

from tools.build_biotruth_benchmark import expand_tasks
from tools.run_deep_case_study import build_pipeline_argv, parse_args


MANIFEST_PATH = Path("benchmarks/autoscientist_deep_ra_refractory_case.json")


def test_deep_ra_manifest_is_auditable_and_not_person_specific() -> None:
    manifest_text = MANIFEST_PATH.read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)

    assert "personalized_for_reviewer" not in manifest_text
    assert "named_external_reviewer" not in manifest_text
    assert manifest["schema"] == "autosci.biotruth_manifest.v0.1"
    assert manifest["selection_policy"]["recommended_agent_count"] == 12
    assert len(manifest["seed_cases"]) == 1
    assert len(manifest["task_templates"]) == 4

    case = manifest["seed_cases"][0]
    assert case["id"] == "tnf_refractory_rheumatoid_arthritis_deep"
    assert case["gene_symbol"] == "TNF"
    assert case["disease_name"] == "rheumatoid arthritis"
    assert case["expected_decision"] == "support_allowed"
    assert "nonresponse_or_loss_of_response" in case["expected_evidence"]
    assert case["public_labels"]["open_targets_association_status"] == "matched"

    tasks = expand_tasks(manifest)
    assert len(tasks) == 4
    for task in tasks:
        objective = task["objective"].lower()
        assert "rheumatoid arthritis" in objective
        assert "tnf" in objective
        assert any(term in objective for term in ["refractory", "non-response", "loss of response"])
        assert {"public_biomedical", "tooluniverse", "sciflow_policy", "scistate_graph"}.issubset(
            set(task["expected_capabilities"])
        )


def test_deep_case_runner_defaults_to_strict_real_ablation_study() -> None:
    args = parse_args(["--dry-run"])
    argv = build_pipeline_argv(args)

    assert "--strict-real-run" in argv
    assert "--train-neural-policy" in argv
    assert "--skip-build" in argv
    assert "benchmarks/autoscientist_deep_ra_refractory_case.json" in argv
    assert "full" in args.ablations
    assert "plain_llm" in args.ablations
    assert "no_public_tools" in args.ablations
    assert "no_memory" in args.ablations
    assert "no_sciflow" in args.ablations
    assert args.agent_count == 12
    assert args.strategy_repair_max_queries == 6

from __future__ import annotations

from tools.analyze_autoscientist_benchmark import decision_calibration


def test_analysis_decision_calibration_groups_by_ablation_and_expected_decision() -> None:
    calibration = decision_calibration(
        [
            {
                "ablation": "full",
                "run_id": "run_1",
                "task": {
                    "id": "case_1",
                    "expected_decision": "support_allowed",
                    "gold_label": "strong_support",
                },
                "report": {
                    "abstention_policy": {"decision": "support_allowed"},
                    "actionability_profile": {"recommended_decision": "support_allowed"},
                },
                "artifact_path": "case_1.json",
            },
            {
                "ablation": "plain_llm",
                "run_id": "run_2",
                "task": {
                    "id": "case_2",
                    "expected_decision": "abstain",
                    "gold_label": "insufficient_evidence",
                },
                "report": {
                    "abstention_policy": {"decision": "support_allowed"},
                    "actionability_profile": {"recommended_decision": "abstain"},
                },
                "artifact_path": "case_2.json",
            },
        ]
    )

    assert calibration["overall"]["accuracy"] == 0.5
    assert calibration["by_ablation"]["full"]["accuracy"] == 1.0
    assert calibration["by_ablation"]["plain_llm"]["accuracy"] == 0.0
    assert calibration["by_expected_decision"]["abstain"]["observed_decisions"] == {"support_allowed": 1}
    assert calibration["mismatches"][0]["actionability"] == "abstain"

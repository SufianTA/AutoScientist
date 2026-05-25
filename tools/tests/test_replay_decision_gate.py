from __future__ import annotations

import json
from pathlib import Path

from tools.replay_decision_gate import run_gate, write_outputs


def test_replay_decision_gate_passes_synthetic_coverage(tmp_path: Path) -> None:
    gate = run_gate(artifact_dirs=[], include_synthetic=True, min_accuracy=1.0)
    output = write_outputs(gate, tmp_path)

    assert gate["status"] == "passed"
    assert gate["accuracy"] == 1.0
    assert gate["coverage"]["by_expected_decision"] == {
        "abstain": 1,
        "conflicting": 1,
        "support_allowed": 2,
        "tentative_only": 2,
    }
    assert Path(output["gate_json"]).exists()
    assert Path(output["gate_markdown"]).exists()


def test_replay_decision_gate_replays_benchmark_artifact(tmp_path: Path) -> None:
    bench = tmp_path / "bench"
    bench.mkdir()
    artifact = {
        "schema": "autosci.benchmark_task_result.v0.1",
        "task": {
            "id": "targeta_disease__target_validity_review",
            "case_id": "targeta_disease",
            "gene_symbol": "TARGETA",
            "disease_name": "immune arthritis",
            "expected_decision": "support_allowed",
        },
        "ablation": "full",
        "hypothesis": {
            "title": "TARGETA immune arthritis",
            "hypothesis": "TARGETA inhibition has disease-specific clinical efficacy and safety limits.",
            "confidence": 0.8,
        },
        "report": {
            "evidence": [
                {
                    "source": "ClinicalTrials.gov",
                    "text": (
                        "A completed phase 3 interventional trial reported effective TARGETA "
                        "antibody treatment with improved response in immune arthritis."
                    ),
                    "evidence_type": "clinical_precedence",
                },
                {
                    "source": "PubMed",
                    "text": "Human patient cohorts link TARGETA signaling to immune arthritis mechanism.",
                    "evidence_type": "literature",
                },
            ]
        },
        "tool_calls": [
            {
                "tool_name": "clinical_trials_search_tool",
                "input": {"query": "TARGETA immune arthritis failed trial adverse toxicity"},
                "status": "success",
            }
        ],
    }
    (bench / "targeta_disease__target_validity_review__r1__full.json").write_text(
        json.dumps(artifact),
        encoding="utf-8",
    )

    gate = run_gate(artifact_dirs=[bench], include_synthetic=False, min_accuracy=1.0)

    assert gate["status"] == "passed"
    assert gate["case_count"] == 1
    assert gate["rows"][0]["observed_decision"] == "support_allowed"

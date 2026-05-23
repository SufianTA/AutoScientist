import json
from pathlib import Path
from types import SimpleNamespace

from tools.build_biotruth_benchmark import build_manifest, expand_tasks, write_outputs


def test_build_biotruth_manifest_from_mocked_public_sources(tmp_path: Path, monkeypatch) -> None:
    seed_cases = tmp_path / "seed_cases.json"
    seed_cases.write_text(
        json.dumps(
            {
                "seed_cases": [
                    {
                        "id": "il6_rheumatoid_arthritis",
                        "domain": "autoimmune_inflammation",
                        "gene_symbol": "IL6",
                        "target_ensembl_id": "ENSG00000136244",
                        "disease_name": "rheumatoid arthritis",
                        "disease_efo_id": "EFO_0000685",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    def fake_open_targets(target_ensembl_id: str, *, association_scan_size: int, timeout_seconds: int) -> dict:
        return {
            "status": "success",
            "target": {
                "id": target_ensembl_id,
                "approvedSymbol": "IL6",
                "associatedDiseases": {
                    "count": 1,
                    "rows": [
                        {
                            "score": 0.82,
                            "disease": {"id": "EFO_0000685", "name": "rheumatoid arthritis"},
                            "datatypeScores": [{"id": "known_drug", "score": 0.9}],
                        }
                    ],
                },
            },
        }

    def fake_ncbi_count(query: str, *, db: str, timeout_seconds: int) -> dict:
        return {"status": "success", "query": query, "db": db, "count": 100, "url": "https://example.test"}

    monkeypatch.setattr("tools.build_biotruth_benchmark.fetch_open_targets_target_context", fake_open_targets)
    monkeypatch.setattr("tools.build_biotruth_benchmark.fetch_ncbi_count", fake_ncbi_count)

    args = SimpleNamespace(
        seed_cases=str(seed_cases),
        rubric="benchmarks/biotruth_rubric_v0_1.json",
        max_cases=1,
        templates_per_case=4,
        association_scan_size=10,
        public_timeout_seconds=5,
        offline_public_context=False,
    )
    manifest = build_manifest(args)
    tasks = expand_tasks(manifest)
    output = write_outputs(manifest, tmp_path / "biotruth.json")

    assert manifest["schema"] == "autosci.biotruth_manifest.v0.1"
    assert manifest["seed_cases"][0]["public_labels"]["open_targets_association_status"] == "matched"
    assert manifest["seed_cases"][0]["public_labels"]["evidence_availability"] == "high"
    assert len(tasks) == 4
    assert Path(output["manifest_path"]).exists()
    assert Path(output["tasks_jsonl_path"]).exists()

from pathlib import Path
from types import SimpleNamespace

from tools.build_public_benchmark_dataset import build_public_manifest, slugify, write_outputs


def test_slugify_public_case_id() -> None:
    assert slugify("IL6 rheumatoid arthritis!") == "il6_rheumatoid_arthritis"


def test_build_public_manifest_from_mocked_sources(tmp_path: Path, monkeypatch) -> None:
    input_manifest = tmp_path / "seed.json"
    input_manifest.write_text(
        """
        {
          "seed_cases": [
            {
              "id": "il6_rheumatoid_arthritis",
              "domain": "autoimmune",
              "gene_symbol": "IL6",
              "target_ensembl_id": "ENSG00000136244"
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    def fake_open_targets(target_ensembl_id: str, *, size: int) -> dict:
        return {
            "target": {
                "id": target_ensembl_id,
                "approvedSymbol": "IL6",
                "approvedName": "interleukin 6",
                "associatedDiseases": {
                    "rows": [
                        {"score": 0.81, "disease": {"id": "EFO_0000685", "name": "rheumatoid arthritis"}}
                    ]
                },
            }
        }

    def fake_ncbi_count(query: str, *, db: str, timeout_seconds: int) -> dict:
        return {"status": "success", "query": query, "db": db, "count": 42, "url": "https://example.test"}

    monkeypatch.setattr("tools.build_public_benchmark_dataset.fetch_open_targets_associations", fake_open_targets)
    monkeypatch.setattr("tools.build_public_benchmark_dataset.fetch_ncbi_count", fake_ncbi_count)

    args = SimpleNamespace(
        input_manifest=str(input_manifest),
        max_targets=1,
        associations_per_target=1,
        min_open_targets_score=0.2,
        min_pubmed_count=1,
        public_timeout_seconds=5,
        include_omics_template=True,
    )

    manifest = build_public_manifest(args)
    result = write_outputs(manifest, tmp_path / "bench.json")

    assert manifest["schema"] == "autosci.benchmark_manifest.v0.2"
    assert manifest["seed_cases"][0]["public_labels"]["open_targets_association_score"] == 0.81
    assert any(template["id"] == "omics_context_validation" for template in manifest["task_templates"])
    assert Path(result["manifest_path"]).exists()
    assert Path(result["dataset_jsonl_path"]).exists()

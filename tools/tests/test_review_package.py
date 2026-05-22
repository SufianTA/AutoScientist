from pathlib import Path

from tools.collect_review_package import collect_review_package, parse_args, redact


def test_redact_removes_secret_like_values() -> None:
    text = "ANTHROPIC_API_KEY=sk-ant-" + ("a" * 40)

    assert "sk-ant" not in redact(text)


def test_collect_review_package_from_benchmark_dir(tmp_path: Path) -> None:
    bench = tmp_path / "bench"
    bench.mkdir()
    (bench / "benchmark_summary.md").write_text("# Summary\n", encoding="utf-8")
    (bench / "benchmark_summary.json").write_text('{"ok": true}', encoding="utf-8")
    (bench / "scistate_graph.json").write_text('{"nodes": []}', encoding="utf-8")
    (bench / ".env").write_text("ANTHROPIC_API_KEY=sk-ant-" + ("a" * 40), encoding="utf-8")

    args = parse_args([
        "--bench-dir",
        str(bench),
        "--output-dir",
        str(tmp_path / "packages"),
    ])
    result = collect_review_package(args)

    assert Path(result["zip_path"]).exists()
    assert result["secret_like_matches"] == []
    assert not (Path(result["package_dir"]) / "benchmark_run" / ".env").exists()

from __future__ import annotations

import json

import pandas as pd
import pytest

from src.data.loader import load_dataset
from src.data.megavul_audit import (
    audit_huggingface_mirror,
    candidate_matrix,
    canonicalize_official_simple,
    summarize_official_simple,
)


def _official_frame() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "cve_id": "CVE-2024-0001", "cwe_ids": ["CWE-787"], "repo_name": "org/repo",
            "commit_hash": "abc", "git_url": "https://github.com/org/repo/commit/abc",
            "file_path": "a.c", "func_name": "copy", "func_before": "unsafe();",
            "func": "safe();", "is_vul": True,
        },
        {
            "cve_id": "CVE-2024-0001", "cwe_ids": [], "repo_name": "org/repo",
            "commit_hash": "abc", "git_url": "https://github.com/org/repo/commit/abc",
            "file_path": "b.c", "func_name": "helper", "func_before": None,
            "func": "helper();", "is_vul": False,
        },
        {
            "cve_id": "CVE-2024-0002", "cwe_ids": ["CWE-787"], "repo_name": "org/other",
            "commit_hash": "def", "git_url": "https://github.com/org/other/commit/def",
            "file_path": "a.c", "func_name": "copy", "func_before": "unsafe();",
            "func": "safe();", "is_vul": True,
        },
    ])


def test_canonicalize_uses_before_fix_code_for_vulnerable_record() -> None:
    result = canonicalize_official_simple(_official_frame())

    assert result["source_code"].tolist() == ["unsafe();", "helper();", "unsafe();"]
    assert result["cwe_list"].tolist() == [["CWE-787"], [], ["CWE-787"]]
    assert result["repository"].tolist() == [
        "github.com/org/repo", "github.com/org/repo", "github.com/org/other",
    ]


def test_canonicalize_rejects_processed_mirror_schema() -> None:
    mirror = pd.DataFrame([{"vulnerable_code": "x", "fixed_code": "y"}])

    with pytest.raises(ValueError, match="Thiếu field bắt buộc"):
        canonicalize_official_simple(mirror)


def test_official_summary_keeps_rows_and_reports_duplicate_conflict() -> None:
    tables = summarize_official_simple(canonicalize_official_simple(_official_frame()))
    summary = tables["summary"].set_index("metric")["value"]

    assert summary["total_samples"] == 3
    assert summary["vulnerable_samples"] == 2
    assert summary["vulnerable_with_cwe"] == 2
    assert summary["unique_cwe"] == 1
    duplicate = tables["duplicate_summary"].set_index("level")
    assert duplicate.loc["raw_source", "duplicate_groups"] == 1
    assert int(tables["author_comparison"].set_index("metric").loc["total_samples", "difference"]) < 0


def test_huggingface_mirror_with_repeated_rows_is_not_official(tmp_path) -> None:
    frame = pd.DataFrame({
        "cve_id": ["CVE-1", "CVE-1"],
        "hash": ["same", "same"],
        "repo_url": ["https://example/commit/a", "https://example/commit/a"],
        "cwe_id": ["CWE-787", "CWE-787"],
        "language": ["c", "c"],
        "file_paths": ["a.c", "a.c"],
        "vulnerable_code": ["unsafe();", "unsafe();"],
        "fixed_code": ["safe();", "safe();"],
    })
    frame.to_parquet(tmp_path / "0000.parquet", index=False)

    audit = audit_huggingface_mirror(tmp_path)

    assert audit.usable_as_official_release is False
    assert any("dòng metadata lặp" in reason for reason in audit.reasons)
    assert any("schema gốc" in reason for reason in audit.reasons)


def test_candidate_matrix_does_not_treat_author_counts_as_local_measurements(tmp_path) -> None:
    summary = tmp_path / "dataset_summary.csv"
    summary.write_text("metric,value\ntotal_samples,10\nvulnerable_samples,4\nunique_cwe,2\n", encoding="utf-8")

    matrix = candidate_matrix(summary).set_index("criterion")

    assert matrix.loc["tổng function", "megavul_measured"] == "chưa đo"
    assert matrix.loc["tổng function", "megavul_author_reported"] != matrix.loc["tổng function", "megavul_measured"]


def test_loader_selects_megavul_file_by_dataset_name(tmp_path) -> None:
    raw_dir = tmp_path / "megavul"
    raw_dir.mkdir()
    (raw_dir / "other.json").write_text(json.dumps([{"x": 1}]), encoding="utf-8")
    (raw_dir / "megavul_simple.json").write_text(json.dumps([{"is_vul": True}]), encoding="utf-8")

    loaded = load_dataset("megavul", raw_dir)

    assert loaded.source_file.name == "megavul_simple.json"
    assert len(loaded.frame) == 1

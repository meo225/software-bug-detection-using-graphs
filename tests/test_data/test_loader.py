"""Test audit dataset dùng synthetic fixture, không dùng số liệu từ paper."""

from __future__ import annotations

import json

import pandas as pd

from src.data.cwe import parse_cwe_labels
from src.data.diversevul_audit import run_audit
from src.data.loader import load_dataset
from src.data.preprocessing import normalize_whitespace


def fixture_frame() -> pd.DataFrame:
    return pd.DataFrame([
        {"project": "alpha", "commit_id": "a1", "target": 1, "func": "int f(){\n return 1;\n}\n", "cwe": ["CWE-787", "CWE-119"]},
        {"project": "alpha", "commit_id": "a2", "target": 1, "func": "int f(){\r\n return 1;   \r\n}\r\n", "cwe": "CWE-787"},
        {"project": "beta", "commit_id": "b1", "target": 1, "func": "void g() {}", "cwe": None},
        {"project": "beta", "commit_id": "b2", "target": 0, "func": "void g() {}", "cwe": "[]"},
    ])


def test_dataset_loader_reads_jsonl_without_dropping_rows(tmp_path) -> None:
    raw_dir = tmp_path / "diversevul"
    raw_dir.mkdir()
    path = raw_dir / "diversevul.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for record in fixture_frame().to_dict(orient="records"):
            handle.write(json.dumps(record) + "\n")
    loaded = load_dataset("diversevul", raw_dir)
    assert loaded.source_file == path.resolve()
    assert len(loaded.frame) == 4
    assert list(loaded.frame.columns) == ["project", "commit_id", "target", "func", "cwe"]


def test_cwe_preprocessing_keeps_every_label() -> None:
    assert parse_cwe_labels(["CWE-787", "CWE-119"]) == ["CWE-787", "CWE-119"]
    assert parse_cwe_labels("['CWE-125', 'CWE-416']") == ["CWE-125", "CWE-416"]
    assert parse_cwe_labels(None) == []


def test_audit_reports_multi_cwe_duplicates_and_conflicts_without_dropping_rows() -> None:
    frame = fixture_frame()
    result = run_audit(frame)
    assert len(result.records) == len(frame)
    summary = result.tables["multi_cwe_summary"].set_index("category")["sample_count"]
    assert summary.to_dict() == {"zero_cwe": 1, "exactly_one_cwe": 1, "two_or_more_cwe": 1}
    duplicate = result.tables["duplicate_summary"].set_index("level")
    assert duplicate.loc["raw_source", "duplicate_groups"] == 1
    assert duplicate.loc["normalized_source", "duplicate_groups"] == 2
    assert duplicate.loc["normalized_source", "vulnerable_label_conflict_groups"] == 1
    assert result.tables["project_distribution"].set_index("project").loc["beta", "total_samples"] == 2


def test_normalization_does_not_collapse_internal_whitespace() -> None:
    source = '\nconst char *s = "a   b";  \r\n\r\n'
    assert normalize_whitespace(source) == 'const char *s = "a   b";'

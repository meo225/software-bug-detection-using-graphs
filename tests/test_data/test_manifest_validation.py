"""Regression cho Strategy A: row-N = dataset record index 0-based + validation fail-closed.

Bao phủ: record đầu/cuối, hai record liền kề cùng metadata (chỉ hash phân biệt
được), ranh giới project/commit, biến thể cwe rỗng/multi, ID sai/tầm vực, hash
mismatch, không sinh artifact khi lỗi, và enrich manifest deterministic +
idempotent. Không test nào đọc dataset thật (736 MB) — dữ liệu thật được kiểm
chứng ở checkpoint dry run.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_graph_extraction import (  # noqa: E402
    BASE_COLUMNS,
    HASH_COLUMN,
    ManifestValidationError,
    enrich_manifest,
    load_records_at_indices,
    metadata_mismatches,
    normalize_cwe,
    parse_sample_id,
    read_manifest,
    source_sha256,
    validate_samples,
    write_manifest,
)

PILOT_MANIFEST = ROOT / "data" / "sample_manifests" / "diversevul_graph_sample.csv"


def make_record(project: str, commit: str, cwe: list[str], target: int, func: str) -> dict:
    return {"project": project, "commit_id": commit, "cwe": cwe, "target": target, "func": func}


def write_dataset(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def make_manifest_row(sample_id: str, project: str, commit: str, cwe: str, func: str) -> dict:
    return {
        "sample_id": sample_id,
        "project": project,
        "commit": commit,
        "cwe": cwe,
        "label": "vulnerable",
        "source_reference": f"dataset row sample_id={sample_id}",
        "func": func,
    }


def write_manifest_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


class TestParseSampleId:
    @pytest.mark.parametrize("sample_id,expected", [("row-0", 0), ("row-1", 1), ("row-330491", 330491)])
    def test_valid_ids(self, sample_id: str, expected: int) -> None:
        assert parse_sample_id(sample_id) == expected

    @pytest.mark.parametrize(
        "sample_id",
        ["row-abc", "row--1", "row-1.5", "foo-1", "row-", "", "row-007", "ROW-1", "row 1", None, 7],
    )
    def test_invalid_ids_fail_closed(self, sample_id: object) -> None:
        with pytest.raises(ManifestValidationError):
            parse_sample_id(sample_id)


class TestBoundaryRecord:
    def test_first_and_last_record_resolution(self, tmp_path: Path) -> None:
        dataset = tmp_path / "tiny.jsonl"
        records = [
            make_record("p-first", "c-first", ["CWE-1"], 1, "int a(void) { return 1; }"),
            make_record("p-mid", "c-mid", [], 0, "int b(void) { return 2; }"),
            make_record("p-last", "c-last", ["CWE-2", "CWE-3"], 1, "int c(void) { return 3; }"),
        ]
        write_dataset(dataset, records)
        found = load_records_at_indices(dataset, {0, 2})
        assert found[0]["project"] == "p-first"
        assert found[2]["project"] == "p-last"

    def test_out_of_range_index_fails(self, tmp_path: Path) -> None:
        dataset = tmp_path / "tiny.jsonl"
        write_dataset(dataset, [make_record("p", "c", [], 1, "int f(void) { return 0; }")])
        with pytest.raises(ManifestValidationError, match="vượt tầm"):
            load_records_at_indices(dataset, {5})


class TestAdjacentIdenticalMetadata:
    """Hai record liền kề cùng project/commit/cwe/label: metadata-only KHÔNG phân biệt được."""

    def setup_dataset_and_rows(self, tmp_path: Path) -> tuple[Path, list[dict]]:
        dataset = tmp_path / "adjacent.jsonl"
        func_a = "int f(void) { int x = 1; return x; }"
        func_b = "int g(void) { int y = 2; return y; }"
        records = [
            make_record("same-project", "same-commit", ["CWE-119"], 1, func_a),
            make_record("same-project", "same-commit", ["CWE-119"], 1, func_b),
        ]
        write_dataset(dataset, records)
        rows = []
        for index, func in ((0, func_a), (1, func_b)):
            row = make_manifest_row(f"row-{index}", "same-project", "same-commit", "CWE-119", func)
            row[HASH_COLUMN] = source_sha256(records[index])
            rows.append(row)
        return dataset, rows

    def test_metadata_matches_both_records(self, tmp_path: Path) -> None:
        dataset, rows = self.setup_dataset_and_rows(tmp_path)
        records = load_records_at_indices(dataset, {0, 1})
        assert metadata_mismatches(rows[0], records[0]) == []
        assert metadata_mismatches(rows[0], records[1]) == []

    def test_hash_distinguishes_records(self, tmp_path: Path) -> None:
        dataset, rows = self.setup_dataset_and_rows(tmp_path)
        records = load_records_at_indices(dataset, {0, 1})
        assert source_sha256(records[0]) != source_sha256(records[1])
        results = validate_samples(rows, records, total_records=2, require_hash=True)
        assert all(result.ok for result in results)

    def test_wrong_record_fails_hash_even_with_matching_metadata(self, tmp_path: Path) -> None:
        dataset, rows = self.setup_dataset_and_rows(tmp_path)
        records = load_records_at_indices(dataset, {0, 1})
        swapped = [dict(rows[1], sample_id="row-0", source_reference="dataset row sample_id=row-0"),
                   dict(rows[0], sample_id="row-1", source_reference="dataset row sample_id=row-1")]
        results = validate_samples(swapped, records, total_records=2, require_hash=True)
        assert all(not result.ok for result in results)
        assert all(result.hash_status == "MISMATCH" for result in results)


class TestProjectCommitBoundary:
    def test_transition_between_projects_and_commits(self, tmp_path: Path) -> None:
        dataset = tmp_path / "boundary.jsonl"
        records = [
            make_record("project-a", "commit-a", ["CWE-94"], 1, "int a(void) { return 1; }"),
            make_record("project-b", "commit-b", ["CWE-416"], 1, "int b(void) { return 2; }"),
        ]
        write_dataset(dataset, records)
        row_a = make_manifest_row("row-0", "project-a", "commit-a", "CWE-94", records[0]["func"])
        row_b = make_manifest_row("row-1", "project-b", "commit-b", "CWE-416", records[1]["func"])
        row_a[HASH_COLUMN] = source_sha256(records[0])
        row_b[HASH_COLUMN] = source_sha256(records[1])
        results = validate_samples([row_a, row_b], load_records_at_indices(dataset, {0, 1}), 2, True)
        assert [result.ok for result in results] == [True, True]
        wrong = dict(row_b, cwe="CWE-94")
        results = validate_samples([wrong], load_records_at_indices(dataset, {1}), 2, True)
        assert not results[0].ok
        assert results[0].metadata_status == "MISMATCH"


class TestCweVariant:
    def test_empty_and_multi_cwe_are_preserved_not_excluded(self, tmp_path: Path) -> None:
        dataset = tmp_path / "cwe.jsonl"
        records = [
            make_record("p", "c1", [], 1, "int a(void) { return 1; }"),
            make_record("p", "c2", ["CWE-119", "CWE-787"], 1, "int b(void) { return 2; }"),
        ]
        write_dataset(dataset, records)
        rows = [
            make_manifest_row("row-0", "p", "c1", "", records[0]["func"]),
            make_manifest_row("row-1", "p", "c2", "CWE-119|CWE-787", records[1]["func"]),
        ]
        rows[0][HASH_COLUMN] = source_sha256(records[0])
        rows[1][HASH_COLUMN] = source_sha256(records[1])
        results = validate_samples(rows, load_records_at_indices(dataset, {0, 1}), 2, True)
        assert all(result.ok for result in results)

    def test_cwe_mismatch_fails(self, tmp_path: Path) -> None:
        dataset = tmp_path / "cwe2.jsonl"
        record = make_record("p", "c", ["CWE-119"], 1, "int a(void) { return 1; }")
        write_dataset(dataset, [record])
        row = make_manifest_row("row-0", "p", "c", "CWE-120", record["func"])
        row[HASH_COLUMN] = source_sha256(record)
        results = validate_samples([row], load_records_at_indices(dataset, {0}), 1, True)
        assert not results[0].ok
        assert "cwe" in results[0].errors[0]


class TestLabelAndHash:
    def test_unknown_target_fails_closed(self) -> None:
        record = make_record("p", "c", [], 2, "int a(void) { return 1; }")
        row = make_manifest_row("row-0", "p", "c", "", "int a(void) { return 1; }")
        with pytest.raises(ManifestValidationError):
            metadata_mismatches(row, record)

    def test_missing_func_fails_closed(self) -> None:
        with pytest.raises(ManifestValidationError):
            source_sha256({"project": "p"})

    def test_blank_func_fails_closed(self) -> None:
        with pytest.raises(ManifestValidationError):
            source_sha256({"func": "   \n  "})

    def test_hash_is_sha256_of_utf8_source(self) -> None:
        import hashlib

        func = "int h(void) { return 42; }"
        assert source_sha256({"func": func}) == hashlib.sha256(func.encode("utf-8")).hexdigest()


class TestNoPartialArtifact:
    def test_failed_resolution_aborts_before_any_output(self, tmp_path: Path) -> None:
        """Index vượt tầm ném lỗi từ lớp resolve — chưa có gì được ghi ra đĩa."""
        dataset = tmp_path / "np.jsonl"
        record = make_record("p", "c", ["CWE-1"], 1, "int a(void) { return 1; }")
        write_dataset(dataset, [record])
        row = make_manifest_row("row-9", "p", "c", "CWE-1", record["func"])
        rows = read_manifest(_manifest_from_rows(tmp_path, [row], with_hash=False))
        with pytest.raises(ManifestValidationError, match="vượt tầm"):
            load_records_at_indices(dataset, {parse_sample_id(rows[0]["sample_id"])})
        out_dir = tmp_path / "graphs"
        assert not out_dir.exists()


def _manifest_from_rows(tmp_path: Path, rows: list[dict], with_hash: bool) -> Path:
    path = tmp_path / "manifest.csv"
    columns = BASE_COLUMNS + ([HASH_COLUMN] if with_hash else [])
    slim = [{key: value for key, value in row.items() if key in columns} for row in rows]
    write_manifest_csv(path, slim, columns)
    return path


class TestEnrichManifest:
    def _fixture(self, tmp_path: Path) -> tuple[Path, Path]:
        dataset = tmp_path / "enrich.jsonl"
        funcs = ["int a(void) { return 1; }", "int b(void) { return 2; }"]
        records = [make_record("p1", "c1", ["CWE-1"], 1, funcs[0]),
                   make_record("p2", "c2", [], 1, funcs[1])]
        write_dataset(dataset, records)
        rows = [
            make_manifest_row("row-1", "p2", "c2", "", funcs[1]),
            make_manifest_row("row-0", "p1", "c1", "CWE-1", funcs[0]),
        ]
        manifest = _manifest_from_rows(tmp_path, rows, with_hash=False)
        return manifest, dataset

    def test_enrich_adds_hash_preserves_order_and_fields(self, tmp_path: Path) -> None:
        manifest, dataset = self._fixture(tmp_path)
        original_first_data = manifest.read_text(encoding="utf-8").splitlines()[1]
        enrich_manifest(manifest, dataset)
        after_rows = list(csv.DictReader(manifest.open(encoding="utf-8", newline="")))
        assert list(after_rows[0].keys()) == BASE_COLUMNS + [HASH_COLUMN]
        assert [row["sample_id"] for row in after_rows] == ["row-1", "row-0"]
        records = load_records_at_indices(dataset, {0, 1})
        by_index = {0: records[0], 1: records[1]}
        for row in after_rows:
            index = parse_sample_id(row["sample_id"])
            assert row[HASH_COLUMN] == source_sha256(by_index[index])
        enriched_first_data = manifest.read_text(encoding="utf-8").splitlines()[1]
        for column in BASE_COLUMNS:
            original_value = original_first_data.split(",")[BASE_COLUMNS.index(column)]
            enriched_value = enriched_first_data.split(",")[BASE_COLUMNS.index(column)]
            assert original_value == enriched_value
        first_line = manifest.read_text(encoding="utf-8").splitlines()[0]
        assert first_line == ",".join(BASE_COLUMNS + [HASH_COLUMN])

    def test_enrich_is_idempotent(self, tmp_path: Path) -> None:
        manifest, dataset = self._fixture(tmp_path)
        enrich_manifest(manifest, dataset)
        once = manifest.read_bytes()
        enrich_manifest(manifest, dataset)
        assert manifest.read_bytes() == once

    def test_validate_after_enrich_passes(self, tmp_path: Path) -> None:
        manifest, dataset = self._fixture(tmp_path)
        enrich_manifest(manifest, dataset)
        rows = read_manifest(manifest)
        records = load_records_at_indices(dataset, {parse_sample_id(row["sample_id"]) for row in rows})
        results = validate_samples(rows, records, total_records=2, require_hash=True)
        assert all(result.ok for result in results)


class TestRealManifestShape:
    """Kiểm hình dáng manifest pilot thật sau enrich — chỉ đọc, rẻ."""

    def test_pilot_manifest_enriched_shape(self) -> None:
        rows = read_manifest(PILOT_MANIFEST)
        assert len(rows) == 30
        assert list(rows[0].keys()) == BASE_COLUMNS + [HASH_COLUMN]
        for row in rows:
            assert re.fullmatch(r"[0-9a-f]{64}", row[HASH_COLUMN])
            parse_sample_id(row["sample_id"])
            assert normalize_cwe(json.loads(json.dumps(row["cwe"]))) == row["cwe"].strip()

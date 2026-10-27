import csv
import json
from pathlib import Path
import multiprocessing
import time

import pytest

import scripts.extract_subset as extract_subset
from scripts.extract_subset import (
    BATCH_DEFINITIONS,
    SESSION_COUNT,
    TOTAL_SAMPLES,
    SampleExtractionOutcome,
    seed_from_previous,
    write_fallback_failure_json,
)
from scripts.merge_and_report_3_3 import main as merge_main


def test_batch_definitions_coverage():
    """Verify that the sessions strictly partition 0 to 9,077 with no overlaps or gaps."""
    assert TOTAL_SAMPLES == 9077
    assert sorted(BATCH_DEFINITIONS) == list(range(1, SESSION_COUNT + 1))

    expected_start = 0
    for index in sorted(BATCH_DEFINITIONS):
        start, end = BATCH_DEFINITIONS[index]
        assert start == expected_start
        assert end > start
        expected_start = end
    assert expected_start == TOTAL_SAMPLES

    sizes = [end - start for start, end in BATCH_DEFINITIONS.values()]
    assert max(sizes) - min(sizes) <= 1
    assert max(sizes) <= 2000


def test_write_fallback_failure_json(tmp_path: Path):
    """Verify failure json adheres to Task 3.1 Tier-1 schema."""
    out_file = tmp_path / "row-999.json"
    write_fallback_failure_json(
        dest_path=out_file,
        sample_id="row-999",
        cwe="CWE-119",
        project_wise_split="train",
        seen_project_split="train",
        graph_type="graph_a",
        status="AST_EXTRACTION_ERROR",
        error_message="Test error message",
    )

    assert out_file.is_file()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["sample_id"] == "row-999"
    assert data["cwe"] == "CWE-119"
    assert data["project_wise_split"] == "train"
    assert data["seen_project_split"] == "train"
    assert data["graph_type"] == "graph_a"
    assert data["status"] == "AST_EXTRACTION_ERROR"
    assert data["ddg_status"] == "NOT_COMPUTED"
    assert data["num_nodes"] == 0
    assert data["num_edges"] == 0
    assert data["nodes"] == []
    assert data["edges"] == []
    assert data["error_message"] == "Test error message"


def test_merge_and_report_mock(tmp_path: Path, monkeypatch):
    """Test merge tool with mock batch directories."""
    # Create mock manifest with 2 samples
    manifest_path = tmp_path / "mock_manifest.csv"
    with open(manifest_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "sample_id", "cwe", "project", "commit", "cve", "group_id", "project_wise_split", "seen_project_split"
        ])
        writer.writeheader()
        writer.writerow({
            "sample_id": "row-0", "cwe": "CWE-787", "project": "qemu",
            "commit": "abc", "cve": "CVE-1", "group_id": "g-1",
            "project_wise_split": "train", "seen_project_split": "train"
        })
        writer.writerow({
            "sample_id": "row-1", "cwe": "CWE-119", "project": "linux",
            "commit": "def", "cve": "CVE-2", "group_id": "g-2",
            "project_wise_split": "test", "seen_project_split": "test"
        })

    # Create mock batch 1
    batch_1 = tmp_path / "batch_1"
    (batch_1 / "graph_a").mkdir(parents=True)
    (batch_1 / "graph_b").mkdir(parents=True)

    json_a_0 = {
        "sample_id": "row-0", "cwe": "CWE-787", "status": "SUCCESS", "num_nodes": 2, "num_edges": 1,
        "nodes": [{"id": 0}, {"id": 1}], "edges": [{"src": 0, "dst": 1, "type": 0}]
    }
    json_b_0 = {
        "sample_id": "row-0", "cwe": "CWE-787", "status": "SUCCESS", "num_nodes": 2, "num_edges": 2,
        "nodes": [{"id": 0}, {"id": 1}], "edges": [{"src": 0, "dst": 1, "type": 0}, {"src": 0, "dst": 1, "type": 1}]
    }
    (batch_1 / "graph_a" / "row-0.json").write_text(json.dumps(json_a_0), encoding="utf-8")
    (batch_1 / "graph_b" / "row-0.json").write_text(json.dumps(json_b_0), encoding="utf-8")

    # Create mock batch 2 (failed sample)
    batch_2 = tmp_path / "batch_2"
    (batch_2 / "graph_a").mkdir(parents=True)
    (batch_2 / "graph_b").mkdir(parents=True)

    json_a_1 = {
        "sample_id": "row-1", "cwe": "CWE-119", "status": "AST_EXTRACTION_ERROR", "num_nodes": 0, "num_edges": 0,
        "nodes": [], "edges": [], "error_message": "failed"
    }
    json_b_1 = {
        "sample_id": "row-1", "cwe": "CWE-119", "status": "AST_EXTRACTION_ERROR", "num_nodes": 0, "num_edges": 0,
        "nodes": [], "edges": [], "error_message": "failed"
    }
    (batch_2 / "graph_a" / "row-1.json").write_text(json.dumps(json_a_1), encoding="utf-8")
    (batch_2 / "graph_b" / "row-1.json").write_text(json.dumps(json_b_1), encoding="utf-8")

    output_dir = tmp_path / "merged_out"
    report_file = tmp_path / "3_3_extraction.md"

    test_args = [
        "merge_and_report_3_3.py",
        "--batch-dirs", str(batch_1), str(batch_2),
        "--manifest", str(manifest_path),
        "--output-dir", str(output_dir),
        "--report-out", str(report_file),
    ]
    monkeypatch.setattr("sys.argv", test_args)
    rc = merge_main()
    assert rc == 0
    assert report_file.is_file()
    assert (output_dir / "graph_a" / "row-0.json").is_file()
    assert (output_dir / "graph_a" / "row-1.json").is_file()
    assert (output_dir / "graph_a" / "manifest.csv").is_file()
    assert (output_dir / "graph_b" / "manifest.csv").is_file()

    report_content = report_file.read_text(encoding="utf-8")
    assert "Task 3.3" in report_content
    assert "CWE-787" in report_content
    assert "CWE-119" in report_content


MANIFEST_FIELDS = [
    "sample_id", "cwe", "project", "commit", "cve", "group_id", "project_wise_split", "seen_project_split"
]
PROCESSED_IDS: list[str] = []


def _write_graph_pair(root: Path, sample_id: str, *, corrupt_b: bool = False) -> None:
    for kind in ("graph_a", "graph_b"):
        directory = root / kind
        directory.mkdir(parents=True, exist_ok=True)
        payload = {
            "sample_id": sample_id, "status": "SUCCESS", "num_nodes": 1,
            "num_edges": 0, "nodes": [], "edges": [],
        }
        text = json.dumps(payload)
        if corrupt_b and kind == "graph_b":
            text = text[:10]
        (directory / f"{sample_id}.json").write_text(text, encoding="utf-8")


def fake_process_single_sample(row, record, graph_a_dir, graph_b_dir, config):
    sample_id = row["sample_id"]
    PROCESSED_IDS.append(sample_id)
    time.sleep(0.05)
    for directory in (graph_a_dir, graph_b_dir):
        (directory / f"{sample_id}.json").write_text(
            json.dumps({"sample_id": sample_id, "status": "SUCCESS", "num_nodes": 1,
                        "num_edges": 0, "nodes": [], "edges": []}),
            encoding="utf-8",
        )
    return SampleExtractionOutcome(
        sample_id=sample_id, index=int(sample_id.split("-")[1]), cwe="CWE-1", project="p",
        project_wise_split="train", seen_project_split="train", status="SUCCESS",
        error_message=None, num_nodes=1, num_edges_a=0, num_edges_b=0, ast_edges=0,
        cfg_edges=0, ddg_edges=0, parse_seconds=None, extraction_seconds=None, total_seconds=0.05,
    )


def _make_inputs(tmp_path: Path, count: int) -> tuple[Path, Path]:
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text(
        "\n".join(json.dumps({"func": f"int f{i}(void) {{ return {i}; }}"}) for i in range(count)) + "\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.csv"
    with open(manifest, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        for i in range(count):
            writer.writerow({
                "sample_id": f"row-{i}", "cwe": "CWE-1", "project": "p", "commit": "c", "cve": "v",
                "group_id": f"g-{i}", "project_wise_split": "train", "seen_project_split": "train",
            })
    return dataset, manifest


def _run_main(monkeypatch, dataset: Path, manifest: Path, output_dir: Path, *extra: str) -> int:
    argv = [
        "extract_subset.py", "--dataset", str(dataset), "--manifest", str(manifest),
        "--output-dir", str(output_dir), "--start-idx", "0", "--end-idx", "40", *extra,
    ]
    monkeypatch.setattr("sys.argv", argv)
    monkeypatch.setattr(extract_subset, "process_single_sample", fake_process_single_sample)
    return extract_subset.main()


def _manifest_rows(output_dir: Path) -> list[dict[str, str]]:
    manifest_files = list(output_dir.glob("manifest_*.csv"))
    assert len(manifest_files) == 1
    with open(manifest_files[0], "r", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_seed_from_previous_copies_only_valid_pairs(tmp_path: Path):
    previous = tmp_path / "kaggle_input" / "old_run" / "output_batch_2"
    _write_graph_pair(previous, "row-1")
    _write_graph_pair(previous, "row-2", corrupt_b=True)
    _write_graph_pair(previous, "row-99")
    (previous / "graph_a" / "row-3.json").write_text("{}", encoding="utf-8")

    dest = tmp_path / "out"
    (dest / "graph_a").mkdir(parents=True)
    (dest / "graph_b").mkdir(parents=True)

    copied = seed_from_previous(
        [tmp_path / "kaggle_input"], dest / "graph_a", dest / "graph_b", {"row-1", "row-2", "row-3"}
    )

    assert copied == 1
    assert (dest / "graph_a" / "row-1.json").is_file()
    assert (dest / "graph_b" / "row-1.json").is_file()
    assert not (dest / "graph_a" / "row-2.json").exists()
    assert not (dest / "graph_a" / "row-99.json").exists()


def test_resume_from_skips_seeded_samples(tmp_path: Path, monkeypatch):
    dataset, manifest = _make_inputs(tmp_path, 40)
    previous = tmp_path / "previous"
    for i in range(10):
        _write_graph_pair(previous, f"row-{i}")
    PROCESSED_IDS.clear()

    rc = _run_main(monkeypatch, dataset, manifest, tmp_path / "out", "--workers", "1",
                   "--resume-from", str(previous))

    assert rc == 0
    assert len(PROCESSED_IDS) == 30
    assert not {f"row-{i}" for i in range(10)} & set(PROCESSED_IDS)
    assert len(_manifest_rows(tmp_path / "out")) == 40


def test_max_runtime_stops_gracefully_sequential(tmp_path: Path, monkeypatch):
    dataset, manifest = _make_inputs(tmp_path, 40)
    PROCESSED_IDS.clear()

    rc = _run_main(monkeypatch, dataset, manifest, tmp_path / "out", "--workers", "1",
                   "--max-runtime-hours", "0.00003")

    out = tmp_path / "out"
    assert rc == 0
    done = len(list((out / "graph_a").glob("*.json")))
    assert 0 < done < 40
    assert len(_manifest_rows(out)) == done == len(list((out / "graph_b").glob("*.json")))


@pytest.mark.skipif(
    multiprocessing.get_start_method() != "fork", reason="test patches the worker function and needs fork"
)
def test_max_runtime_stops_gracefully_with_pool(tmp_path: Path, monkeypatch):
    dataset, manifest = _make_inputs(tmp_path, 40)

    rc = _run_main(monkeypatch, dataset, manifest, tmp_path / "out", "--workers", "2",
                   "--max-runtime-hours", "0.00003")

    out = tmp_path / "out"
    assert rc == 0
    done = len(list((out / "graph_a").glob("*.json")))
    assert 0 < done < 40
    assert len(_manifest_rows(out)) == done == len(list((out / "graph_b").glob("*.json")))


@pytest.mark.skipif(
    multiprocessing.get_start_method() != "fork", reason="test patches the worker function and needs fork"
)
def test_pool_processes_everything_without_limit(tmp_path: Path, monkeypatch):
    dataset, manifest = _make_inputs(tmp_path, 40)

    rc = _run_main(monkeypatch, dataset, manifest, tmp_path / "out", "--workers", "3")

    assert rc == 0
    assert len(_manifest_rows(tmp_path / "out")) == 40


def test_merge_treats_corrupt_json_as_missing(tmp_path: Path, monkeypatch):
    manifest = tmp_path / "manifest.csv"
    with open(manifest, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        for i in range(2):
            writer.writerow({
                "sample_id": f"row-{i}", "cwe": "CWE-1", "project": "p", "commit": "c", "cve": "v",
                "group_id": f"g-{i}", "project_wise_split": "train", "seen_project_split": "train",
            })
    batch = tmp_path / "batch"
    _write_graph_pair(batch, "row-0")
    _write_graph_pair(batch, "row-1", corrupt_b=True)
    with open(batch / "manifest_batch.csv", "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["sample_id", "status"])
        writer.writeheader()
        writer.writerow({"sample_id": "row-0", "status": "SUCCESS"})
        writer.writerow({"sample_id": "row-1", "status": "SUCCESS"})
    monkeypatch.setattr("sys.argv", [
        "merge_and_report_3_3.py", "--batch-dirs", str(batch), "--manifest", str(manifest),
        "--output-dir", str(tmp_path / "merged"), "--report-out", str(tmp_path / "report.md"),
    ])

    assert merge_main() == 0
    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "Số lượng mẫu chưa xử lý: 1" in report
    assert "nhưng thiếu hoặc hỏng tệp graph: 1" in report

    with open(tmp_path / "3_3_failed_samples.csv", "r", encoding="utf-8") as handle:
        failed = list(csv.DictReader(handle))
    assert [(row["sample_id"], row["status"]) for row in failed] == [("row-1", "NOT_PROCESSED")]


def test_apply_jvm_heap_limit_sets_xmx_once(monkeypatch):
    monkeypatch.setenv("JAVA_TOOL_OPTIONS", "")

    assert extract_subset.apply_jvm_heap_limit(4) == "-Xmx4096m"
    # Gọi lại hoặc đã có -Xmx thì không thêm lần nữa.
    assert extract_subset.apply_jvm_heap_limit(2) == "-Xmx4096m"

    monkeypatch.setenv("JAVA_TOOL_OPTIONS", "-Xmx1g")
    assert extract_subset.apply_jvm_heap_limit(4) == "-Xmx1g"

    monkeypatch.delenv("JAVA_TOOL_OPTIONS", raising=False)
    assert extract_subset.apply_jvm_heap_limit(0) is None
    assert "JAVA_TOOL_OPTIONS" not in extract_subset.os.environ


def test_sequential_run_logs_sample_start_with_memory(tmp_path: Path, monkeypatch, capsys):
    dataset, manifest = _make_inputs(tmp_path, 3)
    PROCESSED_IDS.clear()
    monkeypatch.setenv("JAVA_TOOL_OPTIONS", "")

    rc = _run_main(monkeypatch, dataset, manifest, tmp_path / "out", "--workers", "1",
                   "--jvm-heap-gb", "3")

    out = capsys.readouterr().out
    assert rc == 0
    assert out.count("Bắt đầu: row-") == 3
    assert "RAM trống:" in out
    assert extract_subset.os.environ["JAVA_TOOL_OPTIONS"] == "-Xmx3072m"


def test_skip_samples_writes_quarantined_records_without_running(tmp_path: Path, monkeypatch):
    dataset, manifest = _make_inputs(tmp_path, 5)
    PROCESSED_IDS.clear()

    rc = _run_main(monkeypatch, dataset, manifest, tmp_path / "out", "--workers", "1",
                   "--skip-samples", "row-1", "row-3")

    out = tmp_path / "out"
    assert rc == 0
    rows = {r["sample_id"]: r for r in _manifest_rows(out)}
    assert len(rows) == 5
    assert rows["row-1"]["status"] == "QUARANTINED"
    assert rows["row-3"]["status"] == "QUARANTINED"
    assert "row-1" not in PROCESSED_IDS and "row-3" not in PROCESSED_IDS
    for sample_id in ("row-1", "row-3"):
        for graph_dir in ("graph_a", "graph_b"):
            data = json.loads((out / graph_dir / f"{sample_id}.json").read_text(encoding="utf-8"))
            assert data["status"] == "QUARANTINED"

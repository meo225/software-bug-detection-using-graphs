import csv
import json
from pathlib import Path
from scripts.extract_subset import BATCH_DEFINITIONS, TOTAL_SAMPLES, write_fallback_failure_json, SampleExtractionOutcome
from scripts.merge_and_report_3_3 import main as merge_main


def test_batch_definitions_coverage():
    """Verify that the 3 batches strictly partition 0 to 9,077 with no overlaps or gaps."""
    assert TOTAL_SAMPLES == 9077
    b1_start, b1_end = BATCH_DEFINITIONS[1]
    b2_start, b2_end = BATCH_DEFINITIONS[2]
    b3_start, b3_end = BATCH_DEFINITIONS[3]

    assert b1_start == 0
    assert b1_end == b2_start == 3000
    assert b2_end == b3_start == 6000
    assert b3_end == TOTAL_SAMPLES == 9077

    total_covered = (b1_end - b1_start) + (b2_end - b2_start) + (b3_end - b3_start)
    assert total_covered == TOTAL_SAMPLES


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

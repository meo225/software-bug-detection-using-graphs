"""Kiểm thử baseline không dùng graph (Task 4.1a) trên dữ liệu tổng hợp."""

import csv
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from src.models import text_baselines as tb

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_baselines_4_1a.py"
SCHEMA = ROOT / "configs" / "graph" / "schema_spec.yaml"


def make_dataset(tmp_path: Path) -> tuple[Path, Path]:
    """Hai CWE, mỗi lớp có token đặc trưng, chia train, validation, test."""
    graph_dir = tmp_path / "graph_a"
    graph_dir.mkdir()
    manifest = tmp_path / "manifest.csv"
    cwes = {"CWE-119": "memcpy buffer overflow", "CWE-416": "free use dangling pointer"}
    rows = []
    for i in range(60):
        cwe = "CWE-119" if i % 2 == 0 else "CWE-416"
        split = "train" if i < 40 else ("validation" if i < 50 else "test")
        sid = f"row-{i}"
        status = "SUCCESS" if i != 7 else "AST_EXTRACTION_ERROR"
        nodes = [{"id": 0, "node_type": "Method", "code_token": f"fn {cwes[cwe]} x{i % 3}"},
                 {"id": 1, "node_type": "Identifier", "code_token": cwes[cwe].split()[0]}]
        (graph_dir / f"{sid}.json").write_text(
            json.dumps({"sample_id": sid, "status": status, "nodes": nodes}), encoding="utf-8")
        rows.append({"sample_id": sid, "cwe": cwe, "project": "p", "commit": "c", "cve": "v",
                     "group_id": sid, "project_wise_split": split, "seen_project_split": split})
    with open(manifest, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return graph_dir, manifest


def test_load_samples_skips_failed_graphs(tmp_path: Path) -> None:
    graph_dir, manifest = make_dataset(tmp_path)
    samples = tb.load_samples(graph_dir, manifest, tb.load_cwe_mapping(SCHEMA))

    assert len(samples) == 59
    assert "row-7" not in {s["sample_id"] for s in samples}
    assert samples[0]["text_method"].startswith("fn ")
    assert "buffer" in samples[0]["text_nodes"]


def test_majority_and_random_predictions() -> None:
    assert list(tb.predict_majority([1, 1, 2], 4)) == [1, 1, 1, 1]
    first = tb.predict_random([0, 0, 1, 2], 100, seed=1)
    assert np.array_equal(first, tb.predict_random([0, 0, 1, 2], 100, seed=1))
    assert set(first) <= {0, 1, 2}


def test_tfidf_separates_distinct_vocabularies() -> None:
    train_text = ["memcpy buffer overflow"] * 5 + ["free use dangling pointer"] * 5
    train_y = [0] * 5 + [1] * 5
    pred = tb.fit_predict_tfidf(train_text, train_y, ["memcpy buffer", "free pointer"], seed=0)
    assert list(pred) == [0, 1]


def test_script_writes_outputs(tmp_path: Path) -> None:
    graph_dir, manifest = make_dataset(tmp_path)
    out_dir = tmp_path / "out"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--graph-a-dir", str(graph_dir), "--manifest", str(manifest),
         "--out-dir", str(out_dir), "--seeds", "1", "2"],
        capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr

    with open(out_dir / "results.csv", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    models = {r["model"] for r in rows}
    assert models == {"majority", "random", "token_method", "token_nodes"}
    token = [r for r in rows if r["model"] == "token_nodes" and r["split"] == "test"]
    assert all(float(r["accuracy"]) == 1.0 for r in token)
    assert (out_dir / "summary.md").is_file()
    assert (out_dir / "per_class.csv").is_file()

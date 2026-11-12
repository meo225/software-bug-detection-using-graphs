"""Test converter 4.0 trên dữ liệu tổng hợp nhỏ, kiểm tra các bất biến của đặc tả."""

import csv
import json
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")

from src.graph.processed import (  # noqa: E402
    build_processed, build_vocab, choose_token_length, percentile,
)

SCHEMA = Path(__file__).resolve().parents[2] / "configs/graph/schema_spec.yaml"


def test_percentile_nearest_rank() -> None:
    assert percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 95) == 10
    assert percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 50) == 5
    assert percentile([7], 95) == 7


def test_choose_token_length_caps_and_floors() -> None:
    assert choose_token_length([100] * 20, 95, 32) == 32
    assert choose_token_length([0] * 20, 95, 32) == 1
    assert choose_token_length([3, 3, 3, 4], 95, 32) == 4


def test_build_vocab_deterministic_and_min_freq() -> None:
    from collections import Counter

    v = build_vocab(Counter({"b": 3, "a": 3, "c": 1}), 2, ("<PAD>", "<UNK>"))
    assert v == {"<PAD>": 0, "<UNK>": 1, "a": 2, "b": 3}


def _graph(sid: str, status: str, toks: list[str], edges: list[tuple[int, int, int]]) -> dict:
    nodes = [{"id": 0, "node_type": "Method", "code_token": " ".join(toks) + " zz yy xx ww"}]
    nodes += [{"id": i + 1, "node_type": "Identifier", "code_token": t, "rel_line_number": 0.5}
              for i, t in enumerate(toks)]
    return {"sample_id": sid, "status": status, "nodes": nodes,
            "edges": [{"src": s, "dst": d, "type": t} for s, d, t in edges]}


@pytest.fixture()
def dataset(tmp_path: Path):
    classes = ["CWE-119", "CWE-120"]
    rows = []
    for i in range(12):
        sid = f"row-{i}"
        split = "train" if i < 8 else ("validation" if i < 10 else "test")
        rows.append({"sample_id": sid, "cwe": classes[i % 2], "project": "p", "commit": "c",
                     "cve": "x", "group_id": "g", "project_wise_split": split,
                     "seen_project_split": split})
        status = "OVERSIZED_GRAPH" if i == 0 else "SUCCESS"
        a = _graph(sid, status, ["alpha", "beta", "only_val"] if i >= 8 else ["alpha", "beta"],
                   [(0, 1, 0), (1, 2, 0)])
        b = _graph(sid, status, a["nodes"] and [n["code_token"] for n in a["nodes"][1:]],
                   [(0, 1, 0), (1, 2, 0), (1, 2, 1), (2, 99, 2)])
        for kind, rec in (("graph_a", a), ("graph_b", b)):
            (tmp_path / kind).mkdir(exist_ok=True)
            (tmp_path / kind / f"{sid}.json").write_text(json.dumps(rec))
    # mẫu có status lỗi và mẫu thiếu tệp
    bad = _graph("row-bad", "PARSE_ERROR", ["a"], [])
    for kind in ("graph_a", "graph_b"):
        (tmp_path / kind / "row-bad.json").write_text(json.dumps(bad))
    rows.append({"sample_id": "row-bad", "cwe": "CWE-119", "project": "p", "commit": "c", "cve": "x",
                 "group_id": "g", "project_wise_split": "train", "seen_project_split": "train"})
    manifest = tmp_path / "manifest.csv"
    with open(manifest, "w", newline="") as h:
        w = csv.DictWriter(h, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return tmp_path, manifest


def test_build_processed_invariants(dataset) -> None:
    root, manifest = dataset
    out = root / "out"
    meta = build_processed(root, manifest, SCHEMA, out)

    assert meta["n_valid_samples"] == 12 and meta["skipped"] == {"status_không_hợp_lệ": 1}
    pw = meta["protocols"]["project_wise"]
    assert pw["splits"]["graph_a_train"]["n"] == 8
    assert pw["splits"]["graph_a_validation"]["n"] == 2
    assert pw["splits"]["graph_a_test"]["n"] == 2

    vocab = json.loads((out / "project_wise" / "vocab.json").read_text())
    # token chỉ xuất hiện ở validation không được vào vocabulary
    assert "only_val" not in vocab["token"]
    assert vocab["token"]["<PAD>"] == 0 and vocab["token"]["<UNK>"] == 1

    val = torch.load(out / "project_wise" / "graph_a_validation.pt")
    assert (val[0]["x_tok"] == vocab["token"]["<UNK>"]).any()  # only_val -> UNK
    assert val[0]["x_tok"].shape[1] == vocab["k"]

    train_b = torch.load(out / "project_wise" / "graph_b_train.pt")
    g = train_b[1]
    assert g["edge_index"].shape == (2, 3)  # cạnh trỏ tới id 99 bị loại
    assert set(g["edge_type"].tolist()) == {0, 1}
    assert g["y"].item() in (0, 1)
    assert train_b[0]["sample_id"] == "row-0" and train_b[0]["is_oversized"] is True
    assert train_b[1]["is_oversized"] is False

    with open(out / "cwe_counts.csv") as h:
        counts = list(csv.DictReader(h))
    total_train = sum(int(r["n"]) for r in counts if r["protocol"] == "project_wise" and r["split"] == "train")
    assert total_train == 8


def test_k_computed_from_train_only(dataset) -> None:
    root, manifest = dataset
    meta = build_processed(root, manifest, SCHEMA, root / "out2")
    # node không phải Method trong train đều có đúng 1 token
    assert meta["protocols"]["project_wise"]["k"] == 1
    assert meta["protocols"]["project_wise"]["train_token_len_p95_raw"] == 1


def test_train_script_end_to_end(dataset) -> None:
    """Chạy thật scripts/train_gnn.py trên dữ liệu tổng hợp, kiểm tra tệp kết quả."""
    import subprocess
    import sys

    root, manifest = dataset
    out = root / "proc"
    build_processed(root, manifest, SCHEMA, out)
    res = root / "res"
    script = Path(__file__).resolve().parents[2] / "scripts" / "train_gnn.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--processed-dir", str(out), "--out-dir", str(res),
         "--protocols", "project_wise", "--seeds", "1", "--max-epochs", "2", "--dim", "8",
         "--batch-size", "4"], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-2000:]
    rows = list(csv.DictReader(open(res / "results.csv")))
    assert {(r["graph"], r["model"], r["split"]) for r in rows} == {
        (g, m, s) for g in ("graph_a", "graph_b") for m in ("gcn", "ggnn") for s in ("validation", "test")}
    assert (res / "summary.md").is_file() and (res / "per_class.csv").is_file()


def test_validate_passes_and_reports_duplicates(dataset) -> None:
    from src.graph.processed_checks import validate_processed

    root, manifest = dataset
    out = root / "outv"
    build_processed(root, manifest, SCHEMA, out)
    report = validate_processed(out, manifest, expected_valid=12, expected_oversized={"graph_a": 1})
    failed = [c for c in report["checks"] if not c["passed"]]
    assert report["passed"], failed
    dup = report["protocols"]["project_wise"]["model_input_duplicates"]["graph_a"]
    # validation/test của fixture chứa token only_val nên không trùng train
    assert dup["train_duplicates_within_train"] == 7  # 8 graph train giống nhau
    assert dup["held_out"]["validation"]["n_overlap"] == 0


def test_validate_detects_tampered_manifest(dataset) -> None:
    from src.graph.processed_checks import validate_processed

    root, manifest = dataset
    out = root / "outt"
    build_processed(root, manifest, SCHEMA, out)
    path = out / "project_wise" / "manifest.csv"
    text = path.read_text().replace(",test,", ",train,", 1)
    path.write_text(text)
    report = validate_processed(out, manifest)
    assert not report["passed"]


def test_real_pilot_graphs_convert(dataset) -> None:
    """Dữ liệu pilot thật của Task 3.2 trong repo đọc và đếm node, cạnh khớp JSON gốc."""
    from src.graph.processed_checks import convert_pilot

    pilot = Path(__file__).resolve().parents[2] / "reports/graph/3_2_pilot"
    if not (pilot / "graph_a").is_dir():
        pytest.skip("Không có dữ liệu pilot")
    root, manifest = dataset
    out = root / "outp"
    build_processed(root, manifest, SCHEMA, out)
    result = convert_pilot(pilot, out, out / "pilot")
    assert result["n_pilot_files"] > 0 and result["n_converted"] > 0
    assert result["count_mismatches_vs_json"] == []
    loaded = torch.load(out / "pilot" / "graph_b.pt")
    assert all(int(g["y"]) == -1 for g in loaded)


def test_train_script_edge_types_option(dataset) -> None:
    """--edge-types chạy được trên Graph B và được ghi trong metadata."""
    import subprocess
    import sys

    root, manifest = dataset
    out = root / "proc_e"
    build_processed(root, manifest, SCHEMA, out)
    script = Path(__file__).resolve().parents[2] / "scripts" / "train_gnn.py"
    base = [sys.executable, str(script), "--processed-dir", str(out), "--protocols", "project_wise",
            "--graphs", "graph_b", "--models", "ggnn", "--seeds", "1", "--max-epochs", "1", "--dim", "8",
            "--batch-size", "4"]
    ok = subprocess.run(base + ["--out-dir", str(root / "res_e"), "--edge-types", "0", "1"],
                        capture_output=True, text=True)
    assert ok.returncode == 0, ok.stderr[-2000:]
    meta = json.loads((root / "res_e" / "metadata.json").read_text())
    assert meta["arguments"]["edge_types"] == [0, 1]
    bad = subprocess.run(base + ["--out-dir", str(root / "res_f"), "--edge-types", "0", "--save-checkpoints"],
                         capture_output=True, text=True)
    assert bad.returncode != 0

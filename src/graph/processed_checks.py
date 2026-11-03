"""Kiểm tra dữ liệu đã xử lý của Task 4.0 và chuyển đổi bộ pilot.

``validate_processed`` đọc lại các tệp ``.pt`` đã lưu (không dùng biến trong bộ nhớ của lúc
dựng) rồi kiểm tra các bất biến của ``docs/4_0_data_interface_spec.md`` mục 8, kèm thống kê
kích thước và số mẫu có input mô hình trùng giữa train và validation hoặc test.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from src.graph.processed import (
    GRAPH_KINDS, PROTOCOL_COLUMNS, SPLITS, VALID_STATUSES, encode_graph, ids_hash, percentile,
    read_graph,
)

N_CLASSES = 23


def content_hash(item: dict[str, Any]) -> str:
    """Băm input mô hình của một graph: loại node, token, cạnh và loại cạnh (không gồm nhãn)."""
    h = hashlib.sha256()
    for key in ("x_type", "x_tok", "edge_index", "edge_type"):
        tensor = item[key]
        h.update(str(tuple(tensor.shape)).encode())
        h.update(tensor.numpy().tobytes())
    return h.hexdigest()


def _dist(values: list[int]) -> dict[str, Any]:
    if not values:
        return {"n": 0}
    return {"n": len(values), "min": min(values), "p50": percentile(values, 50),
            "p95": percentile(values, 95), "max": max(values),
            "mean": round(sum(values) / len(values), 2)}


def validate_processed(
    processed_dir: Path,
    original_manifest: Path,
    expected_valid: int | None = None,
    expected_oversized: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Chạy toàn bộ kiểm tra. ``checks`` là danh sách (tên, đạt, chi tiết); ``passed`` là tất cả đạt."""
    import torch

    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: Any = None) -> None:
        checks.append({"name": name, "passed": bool(ok), "detail": detail})

    with open(original_manifest, "r", encoding="utf-8") as handle:
        original = {r["sample_id"]: r for r in csv.DictReader(handle)}
    meta = json.loads((processed_dir / "metadata.json").read_text(encoding="utf-8"))
    if expected_valid is not None:
        check("tổng số mẫu hợp lệ khớp báo cáo 3.3", meta["n_valid_samples"] == expected_valid,
              {"thực tế": meta["n_valid_samples"], "kỳ vọng": expected_valid})

    report: dict[str, Any] = {"protocols": {}}
    for protocol, column in PROTOCOL_COLUMNS.items():
        pdir = processed_dir / protocol
        vocab = json.loads((pdir / "vocab.json").read_text(encoding="utf-8"))
        n_types, n_tokens, k = len(vocab["node_type"]), len(vocab["token"]), vocab["k"]
        with open(pdir / "manifest.csv", "r", encoding="utf-8") as handle:
            manifest = list(csv.DictReader(handle))
        by_split = {s: [r["sample_id"] for r in manifest if r["split"] == s] for s in SPLITS}

        # Không mẫu nào ở hai split; split khớp manifest gốc.
        seen: Counter = Counter(r["sample_id"] for r in manifest)
        check(f"{protocol}: không mẫu nào xuất hiện ở hai split", max(seen.values()) == 1)
        wrong = [r["sample_id"] for r in manifest if original[r["sample_id"]][column] != r["split"]]
        check(f"{protocol}: split khớp manifest gốc", not wrong, wrong[:5])

        # Vocabulary chỉ fit trên train: băm danh sách id train được ghi lúc dựng phải khớp.
        check(f"{protocol}: vocabulary ghi nhận đúng tập train",
              vocab.get("train_ids_sha256") == ids_hash(by_split["train"]))

        loaded: dict[str, dict[str, list]] = {}
        stats: dict[str, Any] = {}
        for kind in GRAPH_KINDS:
            loaded[kind] = {s: torch.load(pdir / f"{kind}_{s}.pt") for s in SPLITS}
        for split in SPLITS:
            ids_a = [g["sample_id"] for g in loaded["graph_a"][split]]
            ids_b = [g["sample_id"] for g in loaded["graph_b"][split]]
            check(f"{protocol}/{split}: danh sách mẫu khớp manifest và Graph A trùng Graph B",
                  ids_a == by_split[split] == ids_b)
            node_mismatch = [a["sample_id"] for a, b in zip(loaded["graph_a"][split],
                             loaded["graph_b"][split]) if a["x_type"].shape != b["x_type"].shape
                             or not torch.equal(a["x_tok"], b["x_tok"])]
            check(f"{protocol}/{split}: node Graph A và Graph B giống nhau", not node_mismatch,
                  node_mismatch[:5])

        bad: list[str] = []
        for kind in GRAPH_KINDS:
            for split in SPLITS:
                for g in loaded[kind][split]:
                    n = g["x_type"].shape[0]
                    ok = (0 <= int(g["y"]) < N_CLASSES and int(g["x_type"].max()) < n_types
                          and g["x_tok"].shape == (n, k) and int(g["x_tok"].max()) < n_tokens
                          and g["edge_index"].shape[0] == 2
                          and (g["edge_index"].numel() == 0
                               or (int(g["edge_index"].min()) >= 0 and int(g["edge_index"].max()) < n))
                          and g["edge_index"].shape[1] == g["edge_type"].shape[0]
                          and (kind == "graph_b" or int(g["edge_type"].sum()) == 0)
                          and (g["edge_type"].numel() == 0 or int(g["edge_type"].max()) <= 2)
                          and 0.0 <= float(g["x_rel"].min()) and float(g["x_rel"].max()) <= 1.0)
                    if not ok:
                        bad.append(f"{kind}/{split}/{g['sample_id']}")
        check(f"{protocol}: chỉ số, hình dạng tensor, loại cạnh và nhãn hợp lệ", not bad, bad[:5])

        if expected_oversized:
            for kind, expected in expected_oversized.items():
                got = sum(g["is_oversized"] for s in SPLITS for g in loaded[kind][s])
                check(f"{protocol}/{kind}: số graph quá lớn khớp báo cáo 3.3", got == expected,
                      {"thực tế": got, "kỳ vọng": expected})

        # Thống kê kích thước và mức cắt token (chỉ Graph B vì cùng node với Graph A).
        for split in SPLITS:
            gs = loaded["graph_b"][split]
            real = [(g["x_tok"] != 0).sum(1) for g in gs]
            truncated = sum(int(((r == k)).sum()) for r in real)
            total_nodes = sum(len(r) for r in real)
            stats[split] = {
                "nodes_per_graph": _dist([g["x_type"].shape[0] for g in gs]),
                "edges_graph_b": _dist([g["edge_index"].shape[1] for g in gs]),
                "edges_by_type_graph_b": {str(t): sum(int((g["edge_type"] == t).sum()) for g in gs)
                                          for t in (0, 1, 2)},
                "nodes_at_token_limit_k": {"n": truncated, "share": round(truncated / max(total_nodes, 1), 4)},
                "oversized": sum(g["is_oversized"] for g in gs),
            }

        # Input mô hình trùng giữa train và validation hoặc test.
        duplicates: dict[str, Any] = {}
        for kind in GRAPH_KINDS:
            train_hash: dict[str, set[int]] = defaultdict(set)
            for g in loaded[kind]["train"]:
                train_hash[content_hash(g)].add(int(g["y"]))
            within = len(loaded[kind]["train"]) - len(train_hash)
            held: dict[str, Any] = {}
            for split in ("validation", "test"):
                hits = [g for g in loaded[kind][split] if content_hash(g) in train_hash]
                conflict = [g for g in hits if int(g["y"]) not in train_hash[content_hash(g)]]
                held[split] = {"n_overlap": len(hits), "n_label_conflict": len(conflict),
                               "by_cwe_index": dict(Counter(int(g["y"]) for g in hits))}
            duplicates[kind] = {"train_duplicates_within_train": within, "held_out": held}
        report["protocols"][protocol] = {"k": k, "stats": stats, "model_input_duplicates": duplicates,
                                         "counts": {s: len(v) for s, v in by_split.items()}}

    report["checks"] = checks
    report["passed"] = all(c["passed"] for c in checks)
    return report


def convert_pilot(pilot_root: Path, processed_dir: Path, out_dir: Path,
                  protocol: str = "project_wise") -> dict[str, Any]:
    """Chuyển graph pilot Task 3.2 sang cùng định dạng, dùng vocabulary train của ``protocol``.

    Nhãn pilot là chuỗi CWE thô (có mẫu nhiều CWE), nên ``y = -1`` và chỉ dùng kiểm tra chạy được.
    """
    import torch

    vocab = json.loads((processed_dir / protocol / "vocab.json").read_text(encoding="utf-8"))
    k = vocab["k"]
    out_dir.mkdir(parents=True, exist_ok=True)
    pilot_ids = sorted(p.stem for p in (pilot_root / "graph_a").glob("row-*.json"))
    converted: dict[str, list] = {"graph_a": [], "graph_b": []}
    rows, mismatches = [], []
    for sid in pilot_ids:
        row: dict[str, Any] = {"sample_id": sid}
        pair = {kind: read_graph(pilot_root / kind / f"{sid}.json") for kind in GRAPH_KINDS}
        row["status"] = {kind: (pair[kind] or {}).get("status") for kind in GRAPH_KINDS}
        if any(pair[kind] is None or pair[kind].get("status") not in VALID_STATUSES for kind in GRAPH_KINDS):
            row["converted"] = False
            rows.append(row)
            continue
        for kind in GRAPH_KINDS:
            item = encode_graph(pair[kind], vocab["node_type"], vocab["token"], k, -1)
            expected = (pair[kind].get("num_nodes"), pair[kind].get("num_edges"))
            got = (item["x_type"].shape[0], item["edge_index"].shape[1])
            if expected != got:
                mismatches.append({"sample_id": sid, "kind": kind, "json": expected, "tensor": got})
            converted[kind].append(item)
        row["converted"] = True
        rows.append(row)
    for kind in GRAPH_KINDS:
        torch.save(converted[kind], out_dir / f"{kind}.pt")
    result = {"protocol_vocab": protocol, "n_pilot_files": len(pilot_ids),
              "n_converted": len(converted["graph_a"]),
              "n_not_converted": len(pilot_ids) - len(converted["graph_a"]),
              "count_mismatches_vs_json": mismatches, "rows": rows}
    (out_dir / "pilot_report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                               encoding="utf-8")
    return result

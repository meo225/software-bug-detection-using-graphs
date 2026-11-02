"""Chuyển graph JSON của Task 3.3 sang tensor đã xử lý (phần tối thiểu của Task 4.0).

Đầu vào: thư mục ``graph_a`` và ``graph_b`` (mỗi mẫu một tệp ``<sample_id>.json``),
manifest split và ``schema_spec.yaml``. Đầu ra theo ``docs/4_0_data_interface_spec.md``:
mỗi tổ hợp (graph, protocol, split) là một tệp ``.pt`` chứa danh sách ``dict`` tensor.

Quy tắc chống rò rỉ: vocabulary và độ dài token K chỉ lấy từ tập train của từng protocol.
Mọi giá trị số (K, ngưỡng tần suất) hoặc được tính từ dữ liệu train hoặc là tham số
cấu hình, không có hằng số ước lượng.
"""

from __future__ import annotations

import csv
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import yaml

PAD, UNK, MASK = "<PAD>", "<UNK>", "<MASK>"
VALID_STATUSES = frozenset({"SUCCESS", "OVERSIZED_GRAPH"})
PROTOCOL_COLUMNS = {
    "project_wise": "project_wise_split",
    "seen_project": "seen_project_split",
}
SPLITS = ("train", "validation", "test")
GRAPH_KINDS = ("graph_a", "graph_b")


def load_schema(schema_path: Path) -> dict[str, Any]:
    with open(schema_path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def read_graph(path: Path) -> dict[str, Any] | None:
    """Đọc một tệp graph JSON, trả ``None`` nếu thiếu hoặc hỏng."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def token_list(code_token: Any) -> list[str]:
    """Tách ``code_token`` theo khoảng trắng (nguồn đã chuẩn hóa ở Task 3.3)."""
    return str(code_token or "").split()


def percentile(values: list[int], q: float) -> int:
    """Phân vị q (0..100) kiểu nearest-rank, trả số nguyên."""
    if not values:
        raise ValueError("Không có giá trị để tính phân vị")
    ordered = sorted(values)
    rank = max(1, math.ceil(q / 100.0 * len(ordered)))
    return ordered[rank - 1]


def choose_token_length(
    tokens_per_node: Iterable[int], percentile_q: float = 95.0, cap: int = 32
) -> int:
    """K = phân vị q của số token mỗi node (train), chặn trên ``cap``, tối thiểu 1."""
    return max(1, min(cap, percentile(list(tokens_per_node), percentile_q)))


def build_vocab(counter: Counter, min_freq: int, specials: tuple[str, ...]) -> dict[str, int]:
    """Vocabulary xác định: token đặc biệt trước, rồi theo tần suất giảm dần, hòa thì theo chữ cái."""
    vocab = {name: i for i, name in enumerate(specials)}
    for token, freq in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0])):
        if freq >= min_freq and token not in vocab:
            vocab[token] = len(vocab)
    return vocab


def encode_graph(
    record: dict[str, Any],
    type_vocab: dict[str, int],
    tok_vocab: dict[str, int],
    k: int,
    y: int,
):
    """Mã hóa một graph thành dict tensor. Trả về ``None`` nếu không có node."""
    import torch

    nodes = record.get("nodes", [])
    if not nodes:
        return None
    n = len(nodes)
    index = {node["id"]: i for i, node in enumerate(nodes)}
    if len(index) != n:
        raise ValueError(f"{record.get('sample_id')}: id node trùng lặp")

    x_type = torch.empty(n, dtype=torch.long)
    x_tok = torch.zeros(n, k, dtype=torch.long)
    x_rel = torch.zeros(n, dtype=torch.float32)
    unk_type, unk_tok = type_vocab[UNK], tok_vocab[UNK]
    for i, node in enumerate(nodes):
        x_type[i] = type_vocab.get(node.get("node_type"), unk_type)
        for j, tok in enumerate(token_list(node.get("code_token"))[:k]):
            x_tok[i, j] = tok_vocab.get(tok, unk_tok)
        rel = node.get("rel_line_number")
        x_rel[i] = float(rel) if rel is not None else 0.0

    src, dst, etype = [], [], []
    for edge in record.get("edges", []):
        if edge["src"] in index and edge["dst"] in index:
            src.append(index[edge["src"]])
            dst.append(index[edge["dst"]])
            etype.append(int(edge["type"]))
    edge_index = torch.tensor([src, dst], dtype=torch.long).reshape(2, -1)

    # Cờ lấy từ status của Task 3.3 để khớp số liệu nghiệm thu (554 graph A, 997 graph B).
    is_oversized = record.get("status") == "OVERSIZED_GRAPH"
    return {
        "sample_id": record["sample_id"],
        "x_type": x_type,
        "x_tok": x_tok,
        "x_rel": x_rel,
        "edge_index": edge_index,
        "edge_type": torch.tensor(etype, dtype=torch.long),
        "y": torch.tensor([y], dtype=torch.long),
        "is_oversized": bool(is_oversized),
    }


def read_manifest(manifest_path: Path, cwe_mapping: dict[str, int]) -> list[dict[str, Any]]:
    """Các dòng manifest có CWE thuộc 23 lớp, kèm nhãn số."""
    with open(manifest_path, "r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return [
        {**row, "y": cwe_mapping[row["cwe"]]} for row in rows if row.get("cwe") in cwe_mapping
    ]


def build_processed(
    graph_root: Path,
    manifest_path: Path,
    schema_path: Path,
    out_dir: Path,
    min_token_freq: int | None = None,
    k_percentile: float = 95.0,
    k_cap: int = 32,
    k_override: int | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Tạo toàn bộ dữ liệu xử lý. Trả về dict thống kê để ghi vào ``metadata.json``."""
    import torch

    schema = load_schema(schema_path)
    cwe_mapping = {str(k): int(v) for k, v in schema["cwe_mapping"].items()}
    if min_token_freq is None:
        min_token_freq = int(schema["vocabulary_policy"]["min_token_frequency"])
    rows = read_manifest(manifest_path, cwe_mapping)
    if limit:
        rows = rows[:limit]

    # Đọc graph một lần. Mẫu hợp lệ: cả hai graph có status hợp lệ.
    records: dict[str, dict[str, dict[str, Any]]] = {}
    skipped: Counter = Counter()
    for row in rows:
        sid = row["sample_id"]
        pair = {}
        for kind in GRAPH_KINDS:
            rec = read_graph(graph_root / kind / f"{sid}.json")
            if rec is None:
                skipped["thiếu_hoặc_hỏng_tệp"] += 1
                pair = {}
                break
            if rec.get("status") not in VALID_STATUSES:
                skipped["status_không_hợp_lệ"] += 1
                pair = {}
                break
            pair[kind] = rec
        if pair:
            if len(pair["graph_a"]["nodes"]) != len(pair["graph_b"]["nodes"]):
                raise ValueError(f"{sid}: số node Graph A và Graph B khác nhau")
            records[sid] = pair

    out_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, Any] = {
        "spec_version": "1.1",
        "min_token_freq": min_token_freq,
        "k_percentile": k_percentile,
        "k_cap": k_cap,
        "n_manifest_rows_in_23_classes": len(rows),
        "n_valid_samples": len(records),
        "skipped": dict(skipped),
        "protocols": {},
    }
    counts_rows: list[dict[str, Any]] = []

    for protocol, column in PROTOCOL_COLUMNS.items():
        split_rows = {s: [r for r in rows if r[column] == s and r["sample_id"] in records]
                      for s in SPLITS}
        train_ids = [r["sample_id"] for r in split_rows["train"]]

        # Vocabulary và K chỉ từ train. Node Graph B trùng Graph A nên dùng Graph A.
        type_counter: Counter = Counter()
        tok_counter: Counter = Counter()
        tokens_per_node: list[int] = []
        for sid in train_ids:
            for node in records[sid]["graph_a"]["nodes"]:
                type_counter[node.get("node_type")] += 1
                toks = token_list(node.get("code_token"))
                tok_counter.update(toks)
                if node.get("node_type") != "Method":  # Method chứa cả hàm, luôn bị cắt
                    tokens_per_node.append(len(toks))
        k = k_override or choose_token_length(tokens_per_node, k_percentile, k_cap)
        type_vocab = build_vocab(type_counter, 1, (PAD, UNK))
        tok_vocab = build_vocab(tok_counter, min_token_freq, (PAD, UNK, MASK))

        proto_dir = out_dir / protocol
        proto_dir.mkdir(parents=True, exist_ok=True)
        (proto_dir / "vocab.json").write_text(
            json.dumps({"node_type": type_vocab, "token": tok_vocab, "k": k},
                       ensure_ascii=False), encoding="utf-8")

        meta["protocols"][protocol] = {
            "k": k,
            "n_node_types": len(type_vocab),
            "n_tokens": len(tok_vocab),
            "train_nodes_without_method": len(tokens_per_node),
            "train_token_len_p95_raw": percentile(tokens_per_node, 95.0) if tokens_per_node else None,
            "splits": {},
        }
        manifest_out: list[dict[str, Any]] = []
        for split in SPLITS:
            for kind in GRAPH_KINDS:
                items = []
                for r in split_rows[split]:
                    item = encode_graph(records[r["sample_id"]][kind], type_vocab, tok_vocab,
                                        k, r["y"])
                    if item is not None:
                        items.append(item)
                torch.save(items, proto_dir / f"{kind}_{split}.pt")
                meta["protocols"][protocol]["splits"][f"{kind}_{split}"] = {
                    "n": len(items),
                    "n_oversized": sum(i["is_oversized"] for i in items),
                }
            for r in split_rows[split]:
                manifest_out.append({"sample_id": r["sample_id"], "split": split, "y": r["y"]})
            per_cwe = Counter(r["y"] for r in split_rows[split])
            for cwe, y in cwe_mapping.items():
                counts_rows.append({"protocol": protocol, "split": split, "cwe": cwe,
                                    "y": y, "n": per_cwe.get(y, 0)})
        with open(proto_dir / "manifest.csv", "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["sample_id", "split", "y"])
            writer.writeheader()
            writer.writerows(manifest_out)

    with open(out_dir / "cwe_counts.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["protocol", "split", "cwe", "y", "n"])
        writer.writeheader()
        writer.writerows(counts_rows)
    (out_dir / "metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta

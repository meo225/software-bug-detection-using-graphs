"""Baseline không dùng graph cho Task 4.1a: majority, random và token.

Văn bản đầu vào lấy từ chính các tệp Graph A của Task 3.3 để mọi model dùng
chung một tập mẫu hợp lệ và cùng cách chuẩn hóa token:

- ``method``: ``code_token`` của node Method, là phần đầu của hàm. Dữ liệu 3.3 cắt
  chuỗi này ở khoảng 250 token (kết thúc bằng ``...``).
- ``nodes``: ghép ``code_token`` của mọi node, phủ toàn bộ hàm nhưng lặp token ở
  các node lồng nhau.

Vocabulary và trọng số TF-IDF chỉ fit trên tập train của từng protocol.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import yaml

VALID_STATUSES = frozenset({"SUCCESS", "OVERSIZED_GRAPH"})
PROTOCOL_COLUMNS = {
    "project_wise": "project_wise_split",
    "seen_project": "seen_project_split",
}
SPLITS = ("train", "validation", "test")


def load_cwe_mapping(schema_path: Path) -> dict[str, int]:
    """Đọc ánh xạ CWE sang chỉ số lớp từ ``schema_spec.yaml``."""
    with open(schema_path, "r", encoding="utf-8") as handle:
        return {str(k): int(v) for k, v in yaml.safe_load(handle)["cwe_mapping"].items()}


def load_samples(
    graph_a_dir: Path, manifest_path: Path, cwe_mapping: dict[str, int]
) -> list[dict[str, Any]]:
    """Đọc mẫu hợp lệ cùng văn bản token và cột split của hai protocol."""
    with open(manifest_path, "r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    samples: list[dict[str, Any]] = []
    for row in rows:
        path = graph_a_dir / f"{row['sample_id']}.json"
        if not path.is_file():
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if record.get("status") not in VALID_STATUSES or row["cwe"] not in cwe_mapping:
            continue
        nodes = record.get("nodes", [])
        method_text = next(
            (n.get("code_token") or "" for n in nodes if n.get("node_type") == "Method"), ""
        )
        samples.append(
            {
                "sample_id": row["sample_id"],
                "y": cwe_mapping[row["cwe"]],
                "project_wise": row[PROTOCOL_COLUMNS["project_wise"]],
                "seen_project": row[PROTOCOL_COLUMNS["seen_project"]],
                "text_method": method_text,
                "text_nodes": " ".join(n.get("code_token") or "" for n in nodes),
            }
        )
    return samples


def split_samples(
    samples: Iterable[dict[str, Any]], protocol: str
) -> dict[str, list[dict[str, Any]]]:
    """Chia mẫu theo cột split của protocol, giữ nguyên thứ tự."""
    parts: dict[str, list[dict[str, Any]]] = {name: [] for name in SPLITS}
    for sample in samples:
        if sample[protocol] in parts:
            parts[sample[protocol]].append(sample)
    return parts


def predict_majority(train_y: list[int], n_eval: int) -> np.ndarray:
    """Luôn dự đoán lớp phổ biến nhất của tập train."""
    majority = Counter(train_y).most_common(1)[0][0]
    return np.full(n_eval, majority, dtype=int)


def predict_random(train_y: list[int], n_eval: int, seed: int) -> np.ndarray:
    """Dự đoán ngẫu nhiên theo phân bố lớp của tập train (stratified random)."""
    counts = Counter(train_y)
    classes = sorted(counts)
    probs = np.array([counts[c] for c in classes], dtype=float)
    probs /= probs.sum()
    return np.random.default_rng(seed).choice(classes, size=n_eval, p=probs)


def fit_predict_tfidf(
    train_text: list[str],
    train_y: list[int],
    eval_text: list[str],
    seed: int,
    max_features: int = 200_000,
) -> np.ndarray:
    """TF-IDF 1 và 2 gram cộng hồi quy logistic có trọng số lớp, fit chỉ trên train."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression

    vectorizer = TfidfVectorizer(
        token_pattern=r"\S+",
        lowercase=False,
        ngram_range=(1, 2),
        min_df=2,
        max_features=max_features,
        sublinear_tf=True,
    )
    x_train = vectorizer.fit_transform(train_text)
    model = LogisticRegression(
        class_weight="balanced", max_iter=1000, random_state=seed
    )
    model.fit(x_train, train_y)
    return model.predict(vectorizer.transform(eval_text))

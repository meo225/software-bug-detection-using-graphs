"""Tập văn bản hàm cho Task 4.5.

Mô hình text cần mã nguồn gốc, trong khi Kaggle Dataset của Task 4.0 chỉ chứa id
token theo vocabulary tự học. Module này định nghĩa định dạng trung gian do
``scripts/build_text_dataset.py`` sinh ra, và phần đọc lại dùng chung cho mã
huấn luyện lẫn test.

Mỗi dòng của tệp ``.jsonl.gz`` là một mẫu:

- ``sample_id``: khóa ``row-N`` giống manifest của Task 2.3.
- ``func``: mã nguồn gốc, giữ nguyên khoảng trắng và comment.
- ``cwe``: nhãn CWE dạng chuỗi.
- ``y``: chỉ số lớp trong [0, 22] theo ``cwe_mapping`` của ``schema_spec.yaml``.
- ``project_wise`` và ``seen_project``: tên split của từng protocol.

Tập mẫu phải trùng đúng tập mà các model graph dùng, nếu không thì số của
Task 4.5 không đặt cạnh được số của Task 4.1 đến 4.3.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any, Iterable, Iterator

import yaml

FIELDS = ("sample_id", "func", "cwe", "y", "project_wise", "seen_project")
PROTOCOLS = ("project_wise", "seen_project")
SPLITS = ("train", "validation", "test")

# Số mẫu mỗi split, lấy từ dữ liệu đã xử lý của Task 4.0. Dùng để chặn trường hợp
# tập văn bản lệch khỏi tập mà model graph đã chạy.
EXPECTED_SPLIT_SIZES = {
    "project_wise": {"train": 6101, "validation": 762, "test": 936},
    "seen_project": {"train": 6272, "validation": 764, "test": 763},
}
EXPECTED_TOTAL = 7799


def load_cwe_mapping(schema_path: Path) -> dict[str, int]:
    """Đọc ánh xạ CWE sang chỉ số lớp từ ``schema_spec.yaml``."""
    with open(schema_path, "r", encoding="utf-8") as handle:
        return {str(k): int(v) for k, v in yaml.safe_load(handle)["cwe_mapping"].items()}


def labels_from_mapping(cwe_mapping: dict[str, int]) -> list[str]:
    """Danh sách tên lớp theo chỉ số 0..K-1."""
    return [cwe for cwe, _ in sorted(cwe_mapping.items(), key=lambda kv: kv[1])]


def write_text_dataset(path: Path, samples: Iterable[dict[str, Any]]) -> int:
    """Ghi tệp ``.jsonl.gz``, trả về số mẫu đã ghi."""
    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    # mtime=0 và filename rỗng để hai lần chạy trên cùng dữ liệu cho ra tệp giống hệt nhau.
    # Mặc định gzip nhúng tên tệp cùng thời điểm ghi vào header, làm hỏng tính lặp lại.
    with open(path, "wb") as handle:
        with gzip.GzipFile(filename="", mode="wb", fileobj=handle, mtime=0) as raw:
            for sample in samples:
                missing = [f for f in FIELDS if f not in sample]
                if missing:
                    raise KeyError(f"Mẫu thiếu trường {missing}: {sample.get('sample_id')}")
                line = json.dumps({f: sample[f] for f in FIELDS}, ensure_ascii=False)
                raw.write(line.encode("utf-8") + b"\n")
                written += 1
    return written


def iter_text_dataset(path: Path) -> Iterator[dict[str, Any]]:
    """Đọc từng mẫu, không giữ cả tệp trong bộ nhớ."""
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except ValueError as error:
                raise ValueError(f"Dòng {number} của {path} không phải JSON hợp lệ") from error


def load_text_dataset(path: Path, n_classes: int | None = None) -> list[dict[str, Any]]:
    """Đọc toàn bộ tệp và kiểm tra tính toàn vẹn cơ bản."""
    samples = list(iter_text_dataset(path))
    if not samples:
        raise ValueError(f"Tệp rỗng: {path}")
    seen: set[str] = set()
    for sample in samples:
        missing = [f for f in FIELDS if f not in sample]
        if missing:
            raise KeyError(f"Mẫu thiếu trường {missing}: {sample.get('sample_id')}")
        sample_id = sample["sample_id"]
        if sample_id in seen:
            raise ValueError(f"sample_id lặp lại: {sample_id}")
        seen.add(sample_id)
        if not isinstance(sample["func"], str) or not sample["func"].strip():
            raise ValueError(f"Mẫu {sample_id} không có mã nguồn")
        if n_classes is not None and not 0 <= int(sample["y"]) < n_classes:
            raise ValueError(f"Mẫu {sample_id} có nhãn ngoài khoảng: {sample['y']}")
    return samples


def split_text_samples(
    samples: Iterable[dict[str, Any]], protocol: str
) -> dict[str, list[dict[str, Any]]]:
    """Chia mẫu theo cột split của một protocol, giữ nguyên thứ tự trong tệp."""
    if protocol not in PROTOCOLS:
        raise ValueError(f"Protocol không hợp lệ: {protocol}")
    parts: dict[str, list[dict[str, Any]]] = {name: [] for name in SPLITS}
    for sample in samples:
        name = sample[protocol]
        if name in parts:
            parts[name].append(sample)
    return parts


def split_sizes(samples: Iterable[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Đếm số mẫu từng split của cả hai protocol."""
    samples = list(samples)
    return {
        protocol: {name: len(part) for name, part in split_text_samples(samples, protocol).items()}
        for protocol in PROTOCOLS
    }


def check_split_sizes(samples: Iterable[dict[str, Any]]) -> list[str]:
    """Trả về danh sách sai lệch so với dữ liệu đã xử lý của Task 4.0."""
    actual = split_sizes(samples)
    problems = []
    for protocol, expected in EXPECTED_SPLIT_SIZES.items():
        for name, count in expected.items():
            if actual[protocol][name] != count:
                problems.append(
                    f"{protocol}/{name}: có {actual[protocol][name]}, cần {count}"
                )
    return problems

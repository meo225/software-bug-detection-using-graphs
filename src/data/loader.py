"""Dò tìm và load dataset function-level mà không làm mất record."""

from __future__ import annotations

from pathlib import Path
import json
import pickle
from dataclasses import dataclass
from typing import Any, Protocol

import pandas as pd

SUPPORTED_SUFFIXES = {".csv", ".json", ".jsonl", ".ndjson", ".parquet", ".pkl", ".pickle"}
METADATA_MARKERS = ("metadata", "commit_url", "repo_url", "label_noise", "noise")


class DatasetLoader(Protocol):
    """Load một bản phát hành dataset mà không xóa dòng hoặc đổi label."""

    name: str

    def load(self, raw_dir: Path) -> pd.DataFrame:
        """Trả về toàn bộ record thô."""


@dataclass(frozen=True)
class LoadedDataset:
    """Frame đã load và file chính xác được dùng để tạo frame."""

    frame: pd.DataFrame
    source_file: Path


def _is_probable_metadata(path: Path) -> bool:
    name = path.name.lower()
    return any(marker in name for marker in METADATA_MARKERS)


def discover_dataset_file(raw_dir: Path) -> Path:
    """Chọn file dữ liệu chính và từ chối cấu trúc thư mục mơ hồ."""
    raw_dir = Path(raw_dir)
    if not raw_dir.is_dir():
        raise FileNotFoundError(
            f"Thư mục dữ liệu thô DiverseVul không tồn tại: {raw_dir}. "
            "Xem hướng dẫn tại data/raw/README.md."
        )
    candidates = [
        path for path in raw_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
        and not _is_probable_metadata(path)
    ]
    if not candidates:
        raise FileNotFoundError(
            f"Không tìm thấy file dataset thuộc định dạng được hỗ trợ trong {raw_dir}. "
            f"Các định dạng hợp lệ: {', '.join(sorted(SUPPORTED_SUFFIXES))}."
        )
    if len(candidates) == 1:
        return candidates[0]
    named = [path for path in candidates if "diversevul" in path.name.lower()]
    pool = named or candidates
    pool.sort(key=lambda path: path.stat().st_size, reverse=True)
    if len(pool) > 1 and pool[0].stat().st_size == pool[1].stat().st_size:
        joined = "\n- ".join(str(path) for path in pool)
        raise ValueError(f"Có nhiều file dataset không thể phân biệt. Chỉ giữ một file chính hoặc dùng --dataset-file:\n- {joined}")
    return pool[0]


def read_records(path: Path) -> pd.DataFrame:
    """Đọc file dạng bảng được hỗ trợ mà không thay đổi dòng hoặc label."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, low_memory=False)
    if suffix in {".jsonl", ".ndjson"}:
        # Parser JSON nhanh của pandas từ chối integer `hash` 128-bit trong bản
        # phát hành DiverseVul chính thức ("Value is too big"). Parser chuẩn
        # của Python giữ nguyên giá trị đó; chia chunk để giới hạn bộ nhớ tạm.
        chunks: list[pd.DataFrame] = []
        records: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(f"JSON không hợp lệ tại dòng {line_number} của {path}: {error}") from error
                if not isinstance(payload, dict):
                    raise ValueError(f"Record JSONL tại dòng {line_number} không phải object: {path}")
                records.append(payload)
                if len(records) == 50_000:
                    chunks.append(pd.DataFrame.from_records(records))
                    records = []
        if records:
            chunks.append(pd.DataFrame.from_records(records))
        return pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()
    if suffix == ".json":
        try:
            return pd.read_json(path, lines=True)
        except ValueError:
            with path.open(encoding="utf-8") as handle:
                payload = json.load(handle)
            if isinstance(payload, dict):
                for key in ("data", "records", "functions", "samples"):
                    if isinstance(payload.get(key), list):
                        payload = payload[key]
                        break
            return pd.DataFrame(payload)
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix in {".pkl", ".pickle"}:
        # Chỉ load pickle lấy từ nguồn chính thức vì định dạng này có thể thực thi mã.
        with path.open("rb") as handle:
            payload: Any = pickle.load(handle)  # noqa: S301
        return payload if isinstance(payload, pd.DataFrame) else pd.DataFrame(payload)
    raise ValueError(f"Định dạng dataset không được hỗ trợ: {path}")


def load_dataset(name: str, raw_dir: Path, dataset_file: Path | None = None) -> LoadedDataset:
    """Load dataset được hỗ trợ và giữ nguyên các cột cùng số dòng gốc."""
    if name.lower() != "diversevul":
        raise NotImplementedError(f"Chưa triển khai loader cho dataset {name!r}.")
    source_file = Path(dataset_file) if dataset_file else discover_dataset_file(raw_dir)
    if not source_file.is_file():
        raise FileNotFoundError(source_file)
    return LoadedDataset(frame=read_records(source_file), source_file=source_file.resolve())

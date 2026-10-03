"""Dataset discovery and lossless loading for function-level corpora."""

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
    """Load one dataset release without dropping or relabeling rows."""

    name: str

    def load(self, raw_dir: Path) -> pd.DataFrame:
        """Return every raw record."""


@dataclass(frozen=True)
class LoadedDataset:
    """A loaded frame and the exact file used to create it."""

    frame: pd.DataFrame
    source_file: Path


def _is_probable_metadata(path: Path) -> bool:
    name = path.name.lower()
    return any(marker in name for marker in METADATA_MARKERS)


def discover_dataset_file(raw_dir: Path) -> Path:
    """Choose the main data file, rejecting ambiguous directory layouts."""
    raw_dir = Path(raw_dir)
    if not raw_dir.is_dir():
        raise FileNotFoundError(
            f"DiverseVul raw directory does not exist: {raw_dir}. "
            "See data/raw/README.md."
        )
    candidates = [
        path for path in raw_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
        and not _is_probable_metadata(path)
    ]
    if not candidates:
        raise FileNotFoundError(
            f"No supported dataset file found under {raw_dir}. "
            f"Expected one of: {', '.join(sorted(SUPPORTED_SUFFIXES))}."
        )
    if len(candidates) == 1:
        return candidates[0]
    named = [path for path in candidates if "diversevul" in path.name.lower()]
    pool = named or candidates
    pool.sort(key=lambda path: path.stat().st_size, reverse=True)
    if len(pool) > 1 and pool[0].stat().st_size == pool[1].stat().st_size:
        joined = "\n- ".join(str(path) for path in pool)
        raise ValueError(f"Ambiguous dataset files. Keep one main file or pass --dataset-file:\n- {joined}")
    return pool[0]


def read_records(path: Path) -> pd.DataFrame:
    """Read a supported tabular file without changing its rows or labels."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, low_memory=False)
    if suffix in {".jsonl", ".ndjson"}:
        return pd.read_json(path, lines=True)
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
        # Only load pickle obtained from the official source; it can execute code.
        with path.open("rb") as handle:
            payload: Any = pickle.load(handle)  # noqa: S301
        return payload if isinstance(payload, pd.DataFrame) else pd.DataFrame(payload)
    raise ValueError(f"Unsupported dataset format: {path}")


def load_dataset(name: str, raw_dir: Path, dataset_file: Path | None = None) -> LoadedDataset:
    """Load a supported dataset and preserve its original columns and rows."""
    if name.lower() != "diversevul":
        raise NotImplementedError(f"Loader for dataset {name!r} is not implemented.")
    source_file = Path(dataset_file) if dataset_file else discover_dataset_file(raw_dir)
    if not source_file.is_file():
        raise FileNotFoundError(source_file)
    return LoadedDataset(frame=read_records(source_file), source_file=source_file.resolve())

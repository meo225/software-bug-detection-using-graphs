"""Khóa manifest task 2.3: không leakage và đủ class coverage."""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "data" / "splits" / "diversevul_experiment_manifest.csv"
SPLITS = ("train", "validation", "test")


def _read_ids(protocol: str, split: str) -> list[str]:
    path = ROOT / "data" / "splits" / protocol / f"{split}.txt"
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line]


def _crossing(frame: pd.DataFrame, key: str, split_column: str) -> int:
    occupied: dict[str, set[str]] = {}
    for value, split_name in zip(frame[key], frame[split_column], strict=True):
        if value == "":
            continue
        occupied.setdefault(value, set()).add(split_name)
    return sum(len(names) > 1 for names in occupied.values())


def test_experiment_manifest_blocks_leakage() -> None:
    frame = pd.read_csv(MANIFEST, dtype=str, keep_default_na=False)
    assert len(frame) == 9_077
    assert frame["sample_id"].is_unique
    assert set(frame["cwe"]) == {
        "CWE-119", "CWE-120", "CWE-125", "CWE-189", "CWE-190", "CWE-20", "CWE-200",
        "CWE-22", "CWE-264", "CWE-295", "CWE-369", "CWE-399", "CWE-400", "CWE-401",
        "CWE-415", "CWE-416", "CWE-476", "CWE-59", "CWE-617", "CWE-703", "CWE-770",
        "CWE-787", "CWE-835",
    }
    assert _crossing(frame, "group_id", "project_wise_split") == 0
    assert _crossing(frame, "commit", "project_wise_split") == 0
    assert _crossing(frame, "project", "project_wise_split") == 0
    assert _crossing(frame, "group_id", "seen_project_split") == 0
    assert _crossing(frame, "commit", "seen_project_split") == 0
    assert _crossing(frame, "project", "seen_project_split") > 0
    for split_column, floor in (("project_wise_split", 5), ("seen_project_split", 8)):
        counts = frame.groupby(["cwe", split_column]).size()
        assert counts.min() >= floor
    for protocol, column in (
        ("diversevul_project_wise", "project_wise_split"),
        ("diversevul_seen_project", "seen_project_split"),
    ):
        for split in SPLITS:
            assert _read_ids(protocol, split) == sorted(
                frame.loc[frame[column] == split, "sample_id"],
                key=lambda sample_id: int(sample_id.split("-", 1)[1]),
            )

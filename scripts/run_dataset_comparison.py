"""Chạy gate so sánh MegaVul với EDA DiverseVul hiện có.

Script đo mirror nếu shard Parquet có sẵn, và đo ``megavul_simple.json`` khi file
gốc đã được đặt local. Thiếu file gốc không được điền bằng số liệu tác giả.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")

from src.data.loader import load_dataset
from src.data.megavul_audit import (
    AUTHOR_RELEASE,
    audit_huggingface_mirror,
    candidate_matrix,
    canonicalize_official_simple,
    summarize_official_simple,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mirror-dir", type=Path, default=Path("data/raw/megavul_hf_mirror"))
    parser.add_argument("--official-file", type=Path, default=Path("data/raw/megavul") / AUTHOR_RELEASE["simple_filename"])
    parser.add_argument("--diversevul-summary", type=Path, default=Path("reports/dataset/tables/dataset_summary.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports/dataset_comparison"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tables = args.output_dir / "tables"
    tables.mkdir(parents=True, exist_ok=True)

    mirror = None
    mirror_files = sorted(args.mirror_dir.glob("*.parquet")) if args.mirror_dir.is_dir() else []
    if mirror_files:
        mirror = audit_huggingface_mirror(args.mirror_dir)
        mirror.summary.to_csv(tables / "megavul_mirror_summary.csv", index=False)
        mirror.schema.to_csv(tables / "megavul_mirror_schema.csv", index=False)

    official_summary = None
    if args.official_file.is_file():
        loaded = load_dataset("megavul", args.official_file.parent, args.official_file)
        official_tables = summarize_official_simple(canonicalize_official_simple(loaded.frame))
        official_summary = official_tables["summary"]
        for name, frame in official_tables.items():
            frame.to_csv(tables / f"megavul_official_{name}.csv", index=False)

    comparison = candidate_matrix(args.diversevul_summary, mirror, official_summary)
    comparison.to_csv(tables / "dataset_candidate_matrix.csv", index=False)
    status = {
        "decision": "diversevul_remains_temporary_primary",
        "official_release": {
            "name": AUTHOR_RELEASE["name"],
            "repository": AUTHOR_RELEASE["repository"],
            "artifact_url": AUTHOR_RELEASE["artifact_url"],
            "local_file": _display_path(args.official_file),
            "measured": official_summary is not None,
        },
        "huggingface_mirror": _mirror_status(mirror, mirror_files),
        "blocked_until": [
            "Đặt megavul_simple.json chính thức tại data/raw/megavul/.",
            "Đo duplicate, CWE threshold và project support trên file đó.",
            "Đối chiếu graph Joern công bố; tỷ lệ 87% hiện là số liệu tác giả.",
        ],
    }
    (tables / "comparison_status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Đã ghi kết quả vào {args.output_dir}.")
    print(f"File gốc đã đo: {official_summary is not None}.")
    if mirror is not None:
        print(f"Mirror thay được artifact gốc: {mirror.usable_as_official_release}.")


def _mirror_status(mirror, mirror_files: list[Path]) -> dict:
    if mirror is None:
        return {"present": False, "usable_as_official_release": False, "reasons": ["Không có shard Parquet."]}
    return {
        "present": True,
        "usable_as_official_release": mirror.usable_as_official_release,
        "reasons": list(mirror.reasons),
        "files": [
            {"path": _display_path(path), "size_bytes": path.stat().st_size, "sha256": _sha256(path)}
            for path in mirror_files
        ],
    }


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    main()

"""Tạo dữ liệu tensor đã xử lý (Task 4.0 tối thiểu) từ graph JSON của Task 3.3.

Ví dụ:
    python scripts/build_processed_data.py --graph-root /kaggle/input/<dataset>/graphs_subset_9077 \
        --out-dir /kaggle/working/processed
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.graph.processed import build_processed  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph-root", type=Path, required=True,
                        help="Thư mục chứa graph_a/ và graph_b/")
    parser.add_argument("--manifest", type=Path,
                        default=ROOT / "data/splits/diversevul_experiment_manifest.csv")
    parser.add_argument("--schema", type=Path, default=ROOT / "configs/graph/schema_spec.yaml")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--min-token-freq", type=int, default=None,
                        help="Mặc định lấy từ schema_spec.yaml (vocabulary_policy)")
    parser.add_argument("--k-percentile", type=float, default=95.0)
    parser.add_argument("--k-cap", type=int, default=32)
    parser.add_argument("--k", type=int, default=None, help="Ép K cố định (bỏ qua quy tắc phân vị)")
    parser.add_argument("--limit", type=int, default=None, help="Chỉ xử lý N dòng manifest đầu (chạy thử)")
    args = parser.parse_args()

    meta = build_processed(
        args.graph_root, args.manifest, args.schema, args.out_dir,
        min_token_freq=args.min_token_freq, k_percentile=args.k_percentile,
        k_cap=args.k_cap, k_override=args.k, limit=args.limit,
    )
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

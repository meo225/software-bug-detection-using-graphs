"""Trích xuất đồ thị cho các sample ở mức function.

Cách dùng dự kiến từ thư mục gốc repository::

    python scripts/extract_graphs.py --config configs/graph/cpg.yaml

CPG và Joern là các phương án ứng viên. Lệnh này chưa chạy Joern.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.config import load_config  # noqa: E402
from src.utils.logging import get_logger  # noqa: E402

LOGGER = get_logger("extract_graphs")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Trích xuất đồ thị theo representation trong config YAML.")
    parser.add_argument("--config", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    graph = config.get("graph", {})
    LOGGER.info("Representation: %s (%s)", graph.get("name"), graph.get("status"))
    LOGGER.info("Extractor: %s", graph.get("extractor"))
    raise NotImplementedError(
        "Chưa triển khai bước trích xuất đồ thị. "
        "Giữ các lời gọi Joern trong src/graph/joern.py. "
        "Bắt đầu từ manifest 20 đến 50 function do EDA tạo, không chạy trên full dataset."
    )


if __name__ == "__main__":
    main()

"""Đánh giá một thí nghiệm đã hoàn tất.

Cách dùng dự kiến từ thư mục gốc repository::

    python scripts/evaluate.py --run <experiment-id>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.logging import get_logger  # noqa: E402

LOGGER = get_logger("evaluate")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Đánh giá prediction cho một experiment ID.")
    parser.add_argument("--run", required=True, help="Experiment ID được ghi trong experiments/.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    LOGGER.info("Experiment: %s", args.run)
    raise NotImplementedError(
        "Chưa triển khai bước đánh giá. "
        "Cần báo cáo macro-F1, weighted-F1, precision/recall/F1 theo CWE, "
        "confusion matrix và accuracy. Accuracy không phải metric duy nhất."
    )


if __name__ == "__main__":
    main()

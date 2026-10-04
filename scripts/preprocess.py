"""Tiền xử lý một dataset ứng viên.

Cách dùng dự kiến từ thư mục gốc repository::

    python scripts/preprocess.py --config configs/data/diversevul.yaml
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

LOGGER = get_logger("preprocess")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tiền xử lý dataset được chỉ định trong config YAML.")
    parser.add_argument("--config", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    name = config.get("dataset", {}).get("name")
    LOGGER.info("Config: %s", args.config)
    LOGGER.info("Dataset: %s", name)
    raise NotImplementedError(
        "Chưa triển khai bước tiền xử lý. "
        "Triển khai src/data/preprocessing.py mà không xóa duplicate hoặc đổi label CWE."
    )


if __name__ == "__main__":
    main()

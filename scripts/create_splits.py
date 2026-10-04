"""Ghi danh sách ID train, validation và test có thể tái lập.

Cách dùng dự kiến từ thư mục gốc repository::

    python scripts/create_splits.py --config configs/data/diversevul.yaml --strategy project

Bắt buộc chỉ định strategy. Script không tự chọn strategy thay cho nhóm.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.split import SPLIT_STRATEGIES  # noqa: E402
from src.utils.config import load_config  # noqa: E402
from src.utils.logging import get_logger  # noqa: E402
from src.utils.seed import set_seed  # noqa: E402

LOGGER = get_logger("create_splits")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tạo và lưu cách chia dữ liệu theo sample ID.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--strategy", choices=SPLIT_STRATEGIES, required=True)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    set_seed(args.seed)
    LOGGER.info("Dataset: %s", config.get("dataset", {}).get("name"))
    LOGGER.info("Chiến lược: %s", args.strategy)
    LOGGER.info("Seed: %s", args.seed)
    raise NotImplementedError(
        "Chưa triển khai bước tạo split. "
        "Lưu danh sách ID trong data/splits/. Không sao chép mã nguồn thành ba dataset. "
        "Khi chia theo project, mỗi project không được đồng thời xuất hiện trong train và test."
    )


if __name__ == "__main__":
    main()

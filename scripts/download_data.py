"""Hiển thị vị trí cần đặt dataset candidate.

Lệnh này không tự tải archive. Các file dataset không được đưa vào Git.
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
from src.utils.paths import resolve_from_root  # noqa: E402

LOGGER = get_logger("download_data")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="In hướng dẫn tải thủ công cho một config dataset.")
    parser.add_argument("--config", type=Path, required=True, help="File YAML dataset trong configs/data/.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    dataset = config.get("dataset", {})
    raw_dir = resolve_from_root(dataset.get("local_raw_dir", "data/raw"))
    raw_dir.mkdir(parents=True, exist_ok=True)
    LOGGER.info("Dataset: %s (%s)", dataset.get("name"), dataset.get("status"))
    LOGGER.info("Đặt file tại: %s", raw_dir)
    LOGGER.info("Trang nguồn: %s", dataset.get("source_url"))
    LOGGER.info("Trang tải xuống: %s", dataset.get("download_url"))
    if dataset.get("metadata_url"):
        LOGGER.info("Trang metadata tùy chọn: %s", dataset.get("metadata_url"))
    LOGGER.info("Tính năng tải tự động đã bị tắt.")
    LOGGER.info("Sau khi có file local, đặt dataset.version trong %s.", args.config)
    LOGGER.info("Sau đó chạy: python scripts/run_diversevul_eda.py --strict")


if __name__ == "__main__":
    main()

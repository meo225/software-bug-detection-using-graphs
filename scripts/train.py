"""Train GNN từ một config thí nghiệm.

Cách dùng dự kiến từ thư mục gốc repository::

    python scripts/train.py --config configs/experiment/baseline.yaml

Config phải trỏ đến danh sách ID train, validation và test đã lưu.
Script không được tạo random split mà không lưu lại.
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
from src.utils.seed import set_seed  # noqa: E402

LOGGER = get_logger("train")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train model được chỉ định trong config thí nghiệm.")
    parser.add_argument("--config", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    experiment = load_config(args.config)
    body = experiment.get("experiment", {})
    seed = body.get("seed")
    if seed is not None:
        set_seed(int(seed))
    split = body.get("split", {})
    LOGGER.info("Experiment: %s", body.get("id"))
    LOGGER.info("Model config: %s", body.get("model_config"))
    LOGGER.info("Chiến lược chia dữ liệu: %s", split.get("strategy"))
    if not split.get("train_ids") or not split.get("validation_ids") or not split.get("test_ids"):
        raise NotImplementedError(
            "Từ chối train khi chưa có danh sách ID train, validation và test đã lưu. "
            "Tạo chúng bằng scripts/create_splits.py và ghi đường dẫn trong config thí nghiệm."
        )
    raise NotImplementedError("Chưa triển khai Trainer.fit. Xem src/training/trainer.py.")


if __name__ == "__main__":
    main()

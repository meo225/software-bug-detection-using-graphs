"""Chạy một thí nghiệm theo cấu hình từ dữ liệu đến đánh giá.

Cách dùng dự kiến từ thư mục gốc repository::

    python scripts/run_experiment.py --config configs/experiment/baseline.yaml

Các phase chưa được nối với nhau. Entry point này giúp các lần chạy sau dùng chung
một manifest gồm seed, phiên bản dataset, lựa chọn CWE, split ID, config graph,
config model, hyperparameter và metric.
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

LOGGER = get_logger("run_experiment")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chạy pipeline được mô tả bằng một config thí nghiệm.")
    parser.add_argument("--config", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    experiment = load_config(args.config).get("experiment", {})
    LOGGER.info("Experiment id: %s", experiment.get("id"))
    LOGGER.info("Dataset config: %s", experiment.get("dataset_config"))
    LOGGER.info("Graph config: %s", experiment.get("graph_config"))
    LOGGER.info("Model config: %s", experiment.get("model_config"))
    raise NotImplementedError(
        "Chưa triển khai runner cho thí nghiệm. "
        "Không train trước khi có EDA, chính sách label CWE và split đã lưu."
    )


if __name__ == "__main__":
    main()

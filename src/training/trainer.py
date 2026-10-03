"""Trainer được điều khiển bằng config.

Trainer load cách chia dữ liệu đã lưu, không được tạo cách chia ngẫu nhiên mới
rồi bỏ các ID cũ.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class Trainer:
    """Fit :class:`src.models.classifier.CWEClassifier` và ghi artifact trong ``outputs/``."""

    def __init__(self, experiment: dict[str, Any]) -> None:
        self.experiment = experiment

    def fit(self) -> Path:
        """Chạy training và trả về thư mục của experiment ID này.

        TODO: yêu cầu ``split.train_ids``, ``split.validation_ids`` và
        ``split.test_ids``. Từ chối chạy khi thiếu chiến lược hoặc file ID.
        Ghi seed, phiên bản dataset, config và hyperparameter trong ``experiments/``.
        """
        experiment_id = self.experiment.get("experiment", {}).get("id")
        raise NotImplementedError(
            f"Chưa triển khai Trainer.fit (experiment ID={experiment_id!r})."
        )

"""Chạy đánh giá cho một thí nghiệm đã lưu."""

from __future__ import annotations

from pathlib import Path


def evaluate_run(experiment_id: str, prediction_dir: Path) -> dict[str, object]:
    """Load prediction cho ``experiment_id`` và trả về dictionary metric.

    TODO: đọc danh sách test ID từ experiment manifest. Không tạo lại cách chia
    dữ liệu. Ghi metric dạng JSON trong ``outputs/metrics/``.
    """
    raise NotImplementedError(
        f"Chưa triển khai evaluate_run cho {experiment_id!r} trong {prediction_dir}."
    )

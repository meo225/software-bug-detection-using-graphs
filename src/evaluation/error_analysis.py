"""Phân tích lỗi dựa trên prediction đã lưu.

Module này dùng để giải thích lỗi, không được điều chỉnh lại label hoặc xóa dòng.
"""

from __future__ import annotations

from pathlib import Path


def confusion_pairs(metrics: dict[str, object], top_k: int = 10) -> object:
    """Liệt kê các cặp CWE bị nhầm ngoài đường chéo phổ biến nhất. TODO: triển khai."""
    raise NotImplementedError(f"Chưa triển khai confusion_pairs (top_k={top_k}).")


def export_error_samples(prediction_dir: Path, output_path: Path, limit: int = 20) -> Path:
    """Ghi bảng nhỏ gồm các sample bị phân loại sai để review thủ công.

    TODO: giữ file export đủ nhỏ để commit trong ``reports/`` khi nhóm muốn
    chia sẻ. Không dump toàn bộ dataset.
    """
    raise NotImplementedError(
        f"Chưa triển khai export_error_samples ({prediction_dir} -> {output_path}, giới hạn={limit})."
    )

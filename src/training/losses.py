"""Các hàm loss cho bài toán phân loại CWE.

Dữ liệu dự kiến mất cân bằng giữa các class. Loss là lựa chọn trong config,
không phải giá trị mặc định ngầm resample dataset.
"""

from __future__ import annotations

from typing import Any


def build_loss(config: dict[str, Any]) -> object:
    """Trả về training loss được chỉ định trong ``config``.

    TODO: hỗ trợ loss multiclass tiêu chuẩn. Không oversample hoặc undersample tại đây.
    """
    raise NotImplementedError(f"Chưa triển khai build_loss cho các key {sorted(config)}.")

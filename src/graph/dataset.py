"""Chuyển graph đã parse thành object mà batch GNN yêu cầu.

Chủ động không import PyTorch Geometric tại đây. Phase training sẽ chọn kiểu
tensor cụ thể sau khi schema được xác định.
"""

from __future__ import annotations

from pathlib import Path


def graphs_to_dataset(graph_dir: Path, split_ids: dict[str, list[str]]) -> object:
    """Tạo dataset view cho các ID trong ``split_ids``.

    TODO: đọc graph đã parse và gắn label CWE. Không chia lại dữ liệu.
    """
    raise NotImplementedError(
        f"Chưa triển khai graphs_to_dataset cho {graph_dir} "
        f"và các tập {sorted(split_ids)}."
    )

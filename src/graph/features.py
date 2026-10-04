"""Feature của node và edge.

Việc chọn feature phụ thuộc vào graph schema và chưa được chốt.
"""

from __future__ import annotations


def build_node_features(graph: object) -> object:
    """Ánh xạ node của graph thành ma trận feature. TODO: chọn tập feature trong config."""
    raise NotImplementedError("Chưa triển khai build_node_features.")


def build_edge_features(graph: object) -> object:
    """Ánh xạ edge của graph thành ma trận feature. TODO: mã hóa loại edge khi có schema."""
    raise NotImplementedError("Chưa triển khai build_edge_features.")

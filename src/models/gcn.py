"""Encoder graph convolutional. File chỉ chứa kiến trúc; training loop nằm ở nơi khác."""

from __future__ import annotations

from typing import Any


def build_encoder(config: dict[str, Any]) -> object:
    """Tạo GCN encoder từ ``configs/model/gcn.yaml``.

    TODO: triển khai sau khi có feature của node và edge. Không hard-code số
    class hoặc hidden size mà nhóm chưa chọn.
    """
    raise NotImplementedError(f"Chưa triển khai GCN encoder. Tên config={config.get('model', {}).get('name')!r}.")

"""Encoder graph attention. File chỉ chứa kiến trúc; training loop nằm ở nơi khác."""

from __future__ import annotations

from typing import Any


def build_encoder(config: dict[str, Any]) -> object:
    """Tạo GAT encoder từ ``configs/model/gat.yaml``.

    TODO: triển khai sau khi có feature của node và edge.
    """
    raise NotImplementedError(f"Chưa triển khai GAT encoder. Tên config={config.get('model', {}).get('name')!r}.")

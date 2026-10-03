"""Graph convolutional encoder. Architecture only; the training loop lives elsewhere."""

from __future__ import annotations

from typing import Any


def build_encoder(config: dict[str, Any]) -> object:
    """Build a GCN encoder from ``configs/model/gcn.yaml``.

    TODO: implement after node and edge features exist. Do not hard-code a
    class count or a hidden size that the group has not chosen.
    """
    raise NotImplementedError(f"GCN encoder is not implemented. Config name={config.get('model', {}).get('name')!r}.")

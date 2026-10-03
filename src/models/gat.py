"""Graph attention encoder. Architecture only; the training loop lives elsewhere."""

from __future__ import annotations

from typing import Any


def build_encoder(config: dict[str, Any]) -> object:
    """Build a GAT encoder from ``configs/model/gat.yaml``.

    TODO: implement after node and edge features exist.
    """
    raise NotImplementedError(f"GAT encoder is not implemented. Config name={config.get('model', {}).get('name')!r}.")

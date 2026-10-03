"""Gated graph neural network encoder. Architecture only; the training loop lives elsewhere."""

from __future__ import annotations

from typing import Any


def build_encoder(config: dict[str, Any]) -> object:
    """Build a GGNN encoder from ``configs/model/ggnn.yaml``.

    TODO: implement after node and edge features exist.
    """
    raise NotImplementedError(f"GGNN encoder is not implemented. Config name={config.get('model', {}).get('name')!r}.")

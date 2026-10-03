"""Shared CWE classification head.

The trainer should construct one of these and call ``forward``. It should not
contain a separate training loop per architecture.
"""

from __future__ import annotations

from typing import Any


ENCODERS = {
    "gcn": "src.models.gcn",
    "gat": "src.models.gat",
    "ggnn": "src.models.ggnn",
}


class CWEClassifier:
    """graph batch -> encoder -> pooling -> linear classifier -> CWE logits."""

    def __init__(self, encoder: object, num_classes: int | None, pooling: str | None) -> None:
        self.encoder = encoder
        self.num_classes = num_classes
        self.pooling = pooling

    def forward(self, batch: object) -> object:
        """Return CWE logits for a graph batch.

        TODO: pool encoder states and apply the classifier. ``num_classes``
        stays unknown until the group selects the CWE label set.
        """
        raise NotImplementedError(
            "CWEClassifier.forward is not implemented "
            f"(num_classes={self.num_classes!r}, pooling={self.pooling!r})."
        )


def build_classifier(model_config: dict[str, Any], num_classes: int | None) -> CWEClassifier:
    """Assemble a classifier for the encoder named in ``model_config``."""
    model = model_config.get("model", {})
    name = model.get("name")
    if name not in ENCODERS:
        raise ValueError(f"Unknown model {name!r}. Known encoders: {sorted(ENCODERS)}.")
    raise NotImplementedError(
        f"build_classifier cannot construct {name!r} yet. "
        f"Encoder module: {ENCODERS[name]}. num_classes={num_classes!r}."
    )

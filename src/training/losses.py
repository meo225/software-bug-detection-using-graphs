"""Loss functions for CWE classification.

Class imbalance is expected. The loss is a config choice, not a silent default
that resamples the dataset.
"""

from __future__ import annotations

from typing import Any


def build_loss(config: dict[str, Any]) -> object:
    """Return the training loss named by ``config``.

    TODO: support a standard multiclass loss. Do not oversample or undersample here.
    """
    raise NotImplementedError(f"build_loss is not implemented for keys {sorted(config)}.")

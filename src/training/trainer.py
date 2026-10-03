"""Config-driven trainer.

The trainer loads a saved split. It must not draw a fresh random split and
discard the IDs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class Trainer:
    """Fit a :class:`src.models.classifier.CWEClassifier` and write artifacts under ``outputs/``."""

    def __init__(self, experiment: dict[str, Any]) -> None:
        self.experiment = experiment

    def fit(self) -> Path:
        """Run training and return the directory for this experiment id.

        TODO: require ``split.train_ids``, ``split.validation_ids``, and
        ``split.test_ids``. Refuse to start when the strategy or the ID files
        are missing. Record seed, dataset version, configs, and hyperparameters
        in ``experiments/``.
        """
        experiment_id = self.experiment.get("experiment", {}).get("id")
        raise NotImplementedError(
            f"Trainer.fit is not implemented (experiment id={experiment_id!r})."
        )

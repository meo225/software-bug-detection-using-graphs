"""Run evaluation for a saved experiment."""

from __future__ import annotations

from pathlib import Path


def evaluate_run(experiment_id: str, prediction_dir: Path) -> dict[str, object]:
    """Load predictions for ``experiment_id`` and return a metric dictionary.

    TODO: read the test ID list from the experiment manifest. Do not rebuild
    the split. Write the metric JSON under ``outputs/metrics/``.
    """
    raise NotImplementedError(
        f"evaluate_run is not implemented for {experiment_id!r} in {prediction_dir}."
    )

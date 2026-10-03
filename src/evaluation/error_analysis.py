"""Error analysis on top of saved predictions.

This module should explain mistakes. It should not retune labels or drop rows.
"""

from __future__ import annotations

from pathlib import Path


def confusion_pairs(metrics: dict[str, object], top_k: int = 10) -> object:
    """List the most common off-diagonal CWE confusions. TODO: implement."""
    raise NotImplementedError(f"confusion_pairs is not implemented (top_k={top_k}).")


def export_error_samples(prediction_dir: Path, output_path: Path, limit: int = 20) -> Path:
    """Write a small table of misclassified samples for manual review.

    TODO: keep the export small enough to commit under ``reports/`` when the
    group wants to share it. Do not dump the full dataset.
    """
    raise NotImplementedError(
        f"export_error_samples is not implemented ({prediction_dir} -> {output_path}, limit={limit})."
    )

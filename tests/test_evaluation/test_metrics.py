"""Metric coverage to add with the first real predictions."""

import pytest

from src.evaluation.metrics import BINARY_METRICS, MULTICLASS_METRICS


def test_multiclass_metrics_include_more_than_accuracy() -> None:
    assert "macro_f1" in MULTICLASS_METRICS
    assert "weighted_f1" in MULTICLASS_METRICS
    assert "per_class_f1" in MULTICLASS_METRICS
    assert "confusion_matrix" in MULTICLASS_METRICS
    assert "accuracy" in MULTICLASS_METRICS


def test_binary_metrics_stay_available_for_a_later_experiment() -> None:
    assert "pr_auc" in BINARY_METRICS


@pytest.mark.skip(reason="TODO: compute metrics from a fixed prediction fixture.")
def test_classification_report_matches_a_known_table() -> None:
    """Macro-F1 and per-CWE scores should be checked against a hand-computed example."""

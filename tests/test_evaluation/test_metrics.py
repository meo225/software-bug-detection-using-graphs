"""Coverage cho metric sẽ được thêm cùng các prediction thật đầu tiên."""

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


@pytest.mark.skip(reason="TODO: tính metric từ prediction fixture cố định.")
def test_classification_report_matches_a_known_table() -> None:
    """Macro-F1 và score theo từng CWE cần được đối chiếu với ví dụ tính thủ công."""

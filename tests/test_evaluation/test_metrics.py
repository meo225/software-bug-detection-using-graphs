"""Coverage cho metric sẽ được thêm cùng các prediction thật đầu tiên."""

import pytest

from src.evaluation.metrics import BINARY_METRICS, MULTICLASS_METRICS, classification_report


def test_multiclass_metrics_include_more_than_accuracy() -> None:
    assert "macro_f1" in MULTICLASS_METRICS
    assert "weighted_f1" in MULTICLASS_METRICS
    assert "per_class_f1" in MULTICLASS_METRICS
    assert "confusion_matrix" in MULTICLASS_METRICS
    assert "accuracy" in MULTICLASS_METRICS


def test_binary_metrics_stay_available_for_a_later_experiment() -> None:
    assert "pr_auc" in BINARY_METRICS


def test_classification_report_matches_a_known_table() -> None:
    """Đối chiếu với ví dụ tính thủ công: 3 lớp, lớp 2 không có mẫu thật."""
    y_true = [0, 0, 0, 1, 1, 1]
    y_pred = [0, 0, 1, 1, 1, 0]
    report = classification_report(y_true, y_pred, ["A", "B", "C"])

    assert report["accuracy"] == pytest.approx(4 / 6)
    assert report["per_class_precision"] == pytest.approx([2 / 3, 2 / 3, 0.0])
    assert report["per_class_recall"] == pytest.approx([2 / 3, 2 / 3, 0.0])
    assert report["per_class_support"] == [3, 3, 0]
    # Lớp rỗng vẫn tính vào Macro-F1: (2/3 + 2/3 + 0) / 3
    assert report["macro_f1"] == pytest.approx(4 / 9)
    assert report["weighted_f1"] == pytest.approx(2 / 3)
    assert report["confusion_matrix"] == [[2, 1, 0], [1, 2, 0], [0, 0, 0]]
    assert report["mcc"] == pytest.approx(1 / 3)

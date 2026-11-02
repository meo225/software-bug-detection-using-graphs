"""Các metric phân loại.

Accuracy được ghi nhận nhưng không phải metric duy nhất. Macro-F1 là metric
chính cho phân loại CWE multiclass vì phân bố label dự kiến mất cân bằng.
Các metric lỗ hổng binary vẫn là tùy chọn cho đến khi có experiment tương ứng.
"""

from __future__ import annotations

from typing import Sequence

MULTICLASS_METRICS: tuple[str, ...] = (
    "macro_f1",
    "weighted_f1",
    "per_class_precision",
    "per_class_recall",
    "per_class_f1",
    "confusion_matrix",
    "accuracy",
    "mcc",
)

BINARY_METRICS: tuple[str, ...] = (
    "precision",
    "recall",
    "f1",
    "pr_auc",
)


def classification_report(
    y_true: Sequence[int], y_pred: Sequence[int], labels: list[str]
) -> dict[str, object]:
    """Tính mọi metric trong ``MULTICLASS_METRICS``.

    ``labels`` là danh sách tên lớp theo chỉ số 0..K-1. Lớp không có mẫu thật
    (support bằng 0) vẫn xuất hiện trong bảng theo lớp với score bằng 0, và
    được tính vào Macro-F1 để không che lớp hiếm.
    """
    from sklearn.metrics import (
        accuracy_score,
        confusion_matrix,
        f1_score,
        matthews_corrcoef,
        precision_recall_fscore_support,
    )

    index = list(range(len(labels)))
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=index, zero_division=0
    )
    macro_p, macro_r, macro_f1, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=index, average="macro", zero_division=0
    )
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_precision": float(macro_p),
        "macro_recall": float(macro_r),
        "macro_f1": float(macro_f1),
        "weighted_f1": float(
            f1_score(y_true, y_pred, labels=index, average="weighted", zero_division=0)
        ),
        "mcc": float(matthews_corrcoef(y_true, y_pred)),
        "per_class_precision": [float(v) for v in precision],
        "per_class_recall": [float(v) for v in recall],
        "per_class_f1": [float(v) for v in f1],
        "per_class_support": [int(v) for v in support],
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=index).tolist(),
        "labels": list(labels),
    }

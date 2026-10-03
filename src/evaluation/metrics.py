"""Các metric phân loại.

Accuracy được ghi nhận nhưng không phải metric duy nhất. Macro-F1 là metric
chính cho phân loại CWE multiclass vì phân bố label dự kiến mất cân bằng.
Các metric lỗ hổng binary vẫn là tùy chọn cho đến khi có experiment tương ứng.
"""

from __future__ import annotations

MULTICLASS_METRICS: tuple[str, ...] = (
    "macro_f1",
    "weighted_f1",
    "per_class_precision",
    "per_class_recall",
    "per_class_f1",
    "confusion_matrix",
    "accuracy",
)

BINARY_METRICS: tuple[str, ...] = (
    "precision",
    "recall",
    "f1",
    "pr_auc",
)


def classification_report(y_true: object, y_pred: object, labels: list[str]) -> dict[str, object]:
    """Tính mọi metric có tên trong ``MULTICLASS_METRICS``.

    TODO: triển khai bằng scikit-learn khi có prediction. Trả về precision,
    recall và F1 theo từng CWE cùng các score tổng hợp.
    """
    raise NotImplementedError(
        f"Chưa triển khai classification_report cho {len(labels)} label."
    )

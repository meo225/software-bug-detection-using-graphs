"""Classification metrics.

Accuracy is recorded and is not the only metric. Macro-F1 is the headline
metric for multiclass CWE classification because the label distribution is
expected to be imbalanced. Binary vulnerability metrics stay optional until
that experiment exists.
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
    """Compute every name in ``MULTICLASS_METRICS``.

    TODO: implement with scikit-learn once predictions exist. Return per-CWE
    precision, recall, and F1 alongside the aggregate scores.
    """
    raise NotImplementedError(
        f"classification_report is not implemented for {len(labels)} labels."
    )

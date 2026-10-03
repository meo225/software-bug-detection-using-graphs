"""Classification head dùng chung cho CWE.

Trainer nên khởi tạo class này và gọi ``forward``. Không tạo training loop
riêng cho từng kiến trúc.
"""

from __future__ import annotations

from typing import Any


ENCODERS = {
    "gcn": "src.models.gcn",
    "gat": "src.models.gat",
    "ggnn": "src.models.ggnn",
}


class CWEClassifier:
    """graph batch -> encoder -> pooling -> linear classifier -> logit CWE."""

    def __init__(self, encoder: object, num_classes: int | None, pooling: str | None) -> None:
        self.encoder = encoder
        self.num_classes = num_classes
        self.pooling = pooling

    def forward(self, batch: object) -> object:
        """Trả về logit CWE cho một graph batch.

        TODO: pooling các trạng thái encoder và áp dụng classifier. ``num_classes``
        chưa xác định cho đến khi nhóm chọn tập label CWE.
        """
        raise NotImplementedError(
            "Chưa triển khai CWEClassifier.forward "
            f"(num_classes={self.num_classes!r}, pooling={self.pooling!r})."
        )


def build_classifier(model_config: dict[str, Any], num_classes: int | None) -> CWEClassifier:
    """Tạo classifier cho encoder được chỉ định trong ``model_config``."""
    model = model_config.get("model", {})
    name = model.get("name")
    if name not in ENCODERS:
        raise ValueError(f"Model không xác định {name!r}. Các encoder đã biết: {sorted(ENCODERS)}.")
    raise NotImplementedError(
        f"build_classifier chưa thể khởi tạo {name!r}. "
        f"Module encoder: {ENCODERS[name]}. num_classes={num_classes!r}."
    )

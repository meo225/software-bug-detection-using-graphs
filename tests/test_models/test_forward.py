"""Coverage cho forward pass sẽ được thêm khi có encoder."""

import pytest

from src.models.classifier import ENCODERS


def test_encoder_names_are_registered() -> None:
    assert set(ENCODERS) == {"gcn", "gat", "ggnn"}


@pytest.mark.skip(reason="TODO: chạy một forward pass cho mỗi encoder trên synthetic batch nhỏ.")
def test_model_forward_returns_cwe_logits() -> None:
    """graph batch -> encoder -> pooling -> classifier -> logit CWE."""

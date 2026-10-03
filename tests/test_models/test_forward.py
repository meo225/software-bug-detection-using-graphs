"""Forward-pass coverage to add when an encoder exists."""

import pytest

from src.models.classifier import ENCODERS


def test_encoder_names_are_registered() -> None:
    assert set(ENCODERS) == {"gcn", "gat", "ggnn"}


@pytest.mark.skip(reason="TODO: one forward pass per encoder on a tiny synthetic batch.")
def test_model_forward_returns_cwe_logits() -> None:
    """graph batch -> encoder -> pooling -> classifier -> CWE logits."""

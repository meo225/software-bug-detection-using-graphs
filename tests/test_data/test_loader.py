"""Dataset loader coverage to add with the DiverseVul audit."""

import pytest


@pytest.mark.skip(reason="TODO: load a tiny fixture once the DiverseVul schema is confirmed.")
def test_dataset_loader_reads_records() -> None:
    """The loader returns records and does not drop or relabel them."""


@pytest.mark.skip(reason="TODO: cover CWE parsing, including missing and multi-CWE values.")
def test_cwe_preprocessing_keeps_every_label() -> None:
    """Parsing must not keep only the first CWE."""


@pytest.mark.skip(reason="TODO: report duplicates without deleting rows.")
def test_deduplication_does_not_drop_rows() -> None:
    """EDA reports exact and normalized duplicates and leaves the frame unchanged."""

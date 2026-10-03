"""CWE parsing and frequency tables.

Do not drop rare classes, collapse multi-CWE labels, or pick the first CWE.
Those are research decisions. These helpers should only describe the data.
"""

from __future__ import annotations

from typing import Sequence

FREQUENCY_THRESHOLDS: tuple[int, ...] = (20, 50, 100, 200)


def parse_cwe_labels(raw_value: object) -> list[str]:
    """Return every CWE attached to one sample.

    TODO: support the real column type (string, list, or missing) after EDA.
    An empty list means the sample has no CWE, which must stay visible.
    """
    raise NotImplementedError(f"parse_cwe_labels is not implemented for value {raw_value!r}.")


def cwe_distribution(records: object) -> object:
    """Build the CWE table: CWE, sample_count, percentage, project_count.

    TODO: compute this from ``records``. Include only CWE values present in the data.
    """
    raise NotImplementedError("cwe_distribution is not implemented.")


def threshold_summary(distribution: object, thresholds: Sequence[int] = FREQUENCY_THRESHOLDS) -> object:
    """For each threshold, count remaining CWE, vulnerable functions, and retained share.

    TODO: report all thresholds. Do not select one.
    """
    raise NotImplementedError(
        f"threshold_summary is not implemented for thresholds {tuple(thresholds)}."
    )


def multi_cwe_summary(records: object) -> dict[str, object]:
    """Count samples with one CWE and samples with two or more.

    TODO: also return the distribution of CWE-count per sample and a few examples.
    Do not reduce a multi-CWE sample to its first label.
    """
    raise NotImplementedError("multi_cwe_summary is not implemented.")

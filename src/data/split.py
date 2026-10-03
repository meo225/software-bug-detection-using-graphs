"""Reproducible ID splits.

A split is three lists of sample IDs written under ``data/splits/``.
Do not copy source code into separate train, validation, and test datasets.
``train.py`` must load these files instead of drawing a new random split.
"""

from __future__ import annotations

from pathlib import Path

SPLIT_STRATEGIES: tuple[str, ...] = ("random", "project", "chronological")


def create_split(
    sample_ids: list[str],
    strategy: str,
    seed: int,
    group_ids: list[str] | None = None,
    timestamps: list[str] | None = None,
) -> dict[str, list[str]]:
    """Return ``train``, ``validation``, and ``test`` ID lists.

    ``project`` requires ``group_ids`` and must keep each project in only one
    side of the train/test cut. ``chronological`` requires usable timestamps.
    TODO: implement the three strategies. Do not choose a default strategy here.
    """
    if strategy not in SPLIT_STRATEGIES:
        raise ValueError(f"Unknown split strategy: {strategy}")
    raise NotImplementedError(
        f"create_split({strategy!r}, seed={seed}) is not implemented. "
        f"Received {len(sample_ids)} ids, "
        f"groups={'yes' if group_ids is not None else 'no'}, "
        f"timestamps={'yes' if timestamps is not None else 'no'}."
    )


def assert_project_disjoint(
    train_groups: set[str],
    validation_groups: set[str],
    test_groups: set[str],
) -> None:
    """Fail when the same project appears in more than one split.

    Project-wise splits must keep a project out of both train and test.
    The same rule is applied to the validation set.
    """
    overlaps = {
        "train_validation": sorted(train_groups & validation_groups),
        "train_test": sorted(train_groups & test_groups),
        "validation_test": sorted(validation_groups & test_groups),
    }
    found = {name: groups for name, groups in overlaps.items() if groups}
    if found:
        raise ValueError(f"Project IDs overlap across splits: {found}")


def save_split_ids(split: dict[str, list[str]], output_dir: Path) -> None:
    """Write one ID list per split name. TODO: choose a stable text format."""
    raise NotImplementedError(f"save_split_ids is not implemented for {output_dir}.")


def load_split_ids(output_dir: Path) -> dict[str, list[str]]:
    """Read ID lists produced by :func:`save_split_ids`."""
    raise NotImplementedError(f"load_split_ids is not implemented for {output_dir}.")

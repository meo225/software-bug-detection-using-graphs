"""Repository paths. Resolve every location from the repo root, not a machine-specific absolute path."""

from __future__ import annotations

import sys
from pathlib import Path


def repo_root() -> Path:
    """Return the repository root (the directory that contains ``src``)."""
    return Path(__file__).resolve().parents[2]


def ensure_repo_on_path() -> Path:
    """Put the repository root on ``sys.path`` so ``import src`` works from scripts."""
    root = repo_root()
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return root


def resolve_from_root(*parts: str) -> Path:
    """Join ``parts`` onto the repository root."""
    return repo_root().joinpath(*parts)


def data_dir(*parts: str) -> Path:
    """Path under ``data/``."""
    return resolve_from_root("data", *parts)


def output_dir(*parts: str) -> Path:
    """Path under ``outputs/``."""
    return resolve_from_root("outputs", *parts)


def report_dir(*parts: str) -> Path:
    """Path under ``reports/``."""
    return resolve_from_root("reports", *parts)

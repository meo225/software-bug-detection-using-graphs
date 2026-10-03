"""Đường dẫn repository. Phân giải từ repo root, không dùng đường dẫn tuyệt đối riêng của máy."""

from __future__ import annotations

import sys
from pathlib import Path


def repo_root() -> Path:
    """Trả về repository root, tức thư mục chứa ``src``."""
    return Path(__file__).resolve().parents[2]


def ensure_repo_on_path() -> Path:
    """Thêm repository root vào ``sys.path`` để script có thể ``import src``."""
    root = repo_root()
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return root


def resolve_from_root(*parts: str) -> Path:
    """Nối ``parts`` vào repository root."""
    return repo_root().joinpath(*parts)


def data_dir(*parts: str) -> Path:
    """Đường dẫn bên trong ``data/``."""
    return resolve_from_root("data", *parts)


def output_dir(*parts: str) -> Path:
    """Đường dẫn bên trong ``outputs/``."""
    return resolve_from_root("outputs", *parts)


def report_dir(*parts: str) -> Path:
    """Đường dẫn bên trong ``reports/``."""
    return resolve_from_root("reports", *parts)

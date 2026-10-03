"""Load config YAML. Tham số nghiên cứu thuộc về ``configs/``, không đặt trong source code."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_config(path: Path | str) -> dict[str, Any]:
    """Đọc YAML mapping từ ``path``.

    Đường dẫn tương đối trong file được giữ nguyên. Caller phân giải bằng
    :func:`src.utils.paths.resolve_from_root`.
    """
    config_path = Path(path)
    if not config_path.is_file():
        raise FileNotFoundError(config_path)
    with config_path.open(encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Root của config phải là một mapping: {config_path}")
    return loaded

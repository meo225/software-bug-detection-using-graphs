"""Load YAML configs. Research parameters belong in ``configs/``, not in source code."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_config(path: Path | str) -> dict[str, Any]:
    """Read a YAML mapping from ``path``.

    Relative paths inside the file are left unchanged. Callers resolve them
    with :func:`src.utils.paths.resolve_from_root`.
    """
    config_path = Path(path)
    if not config_path.is_file():
        raise FileNotFoundError(config_path)
    with config_path.open(encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Config root must be a mapping: {config_path}")
    return loaded

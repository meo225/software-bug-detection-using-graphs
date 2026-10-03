"""Preprocess a candidate dataset.

Planned usage, from the repository root::

    python scripts/preprocess.py --config configs/data/diversevul.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.config import load_config  # noqa: E402
from src.utils.logging import get_logger  # noqa: E402

LOGGER = get_logger("preprocess")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preprocess the dataset named by a YAML config.")
    parser.add_argument("--config", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    name = config.get("dataset", {}).get("name")
    LOGGER.info("Config: %s", args.config)
    LOGGER.info("Dataset: %s", name)
    raise NotImplementedError(
        "Preprocessing is not implemented. "
        "Implement src/data/preprocessing.py without deleting duplicates or relabeling CWE."
    )


if __name__ == "__main__":
    main()

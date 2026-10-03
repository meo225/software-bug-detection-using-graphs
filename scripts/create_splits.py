"""Write reproducible train, validation, and test ID lists.

Planned usage, from the repository root::

    python scripts/create_splits.py --config configs/data/diversevul.yaml --strategy project

The strategy is required. This script does not pick one for the group.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.split import SPLIT_STRATEGIES  # noqa: E402
from src.utils.config import load_config  # noqa: E402
from src.utils.logging import get_logger  # noqa: E402
from src.utils.seed import set_seed  # noqa: E402

LOGGER = get_logger("create_splits")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a saved sample-ID split.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--strategy", choices=SPLIT_STRATEGIES, required=True)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    set_seed(args.seed)
    LOGGER.info("Dataset: %s", config.get("dataset", {}).get("name"))
    LOGGER.info("Strategy: %s", args.strategy)
    LOGGER.info("Seed: %s", args.seed)
    raise NotImplementedError(
        "Split creation is not implemented. "
        "Persist ID lists under data/splits/. Do not copy source code into three datasets. "
        "A project-wise split must keep each project out of both train and test."
    )


if __name__ == "__main__":
    main()

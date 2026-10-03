"""Train a GNN from an experiment config.

Planned usage, from the repository root::

    python scripts/train.py --config configs/experiment/baseline.yaml

The config must point at saved train, validation, and test ID lists.
This script must not create an unsaved random split.
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
from src.utils.seed import set_seed  # noqa: E402

LOGGER = get_logger("train")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the model named by an experiment config.")
    parser.add_argument("--config", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    experiment = load_config(args.config)
    body = experiment.get("experiment", {})
    seed = body.get("seed")
    if seed is not None:
        set_seed(int(seed))
    split = body.get("split", {})
    LOGGER.info("Experiment: %s", body.get("id"))
    LOGGER.info("Model config: %s", body.get("model_config"))
    LOGGER.info("Split strategy: %s", split.get("strategy"))
    if not split.get("train_ids") or not split.get("validation_ids") or not split.get("test_ids"):
        raise NotImplementedError(
            "Refusing to train without saved train, validation, and test ID lists. "
            "Create them with scripts/create_splits.py and record the paths in the experiment config."
        )
    raise NotImplementedError("Trainer.fit is not implemented. See src/training/trainer.py.")


if __name__ == "__main__":
    main()

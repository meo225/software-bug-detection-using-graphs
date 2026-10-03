"""Evaluate a finished experiment.

Planned usage, from the repository root::

    python scripts/evaluate.py --run <experiment-id>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.logging import get_logger  # noqa: E402

LOGGER = get_logger("evaluate")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate predictions for one experiment id.")
    parser.add_argument("--run", required=True, help="Experiment id recorded under experiments/.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    LOGGER.info("Experiment: %s", args.run)
    raise NotImplementedError(
        "Evaluation is not implemented. "
        "Report macro-F1, weighted-F1, per-CWE precision/recall/F1, "
        "a confusion matrix, and accuracy. Accuracy is not the only metric."
    )


if __name__ == "__main__":
    main()

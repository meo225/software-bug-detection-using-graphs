"""Run one configured experiment from data config through evaluation.

Planned usage, from the repository root::

    python scripts/run_experiment.py --config configs/experiment/baseline.yaml

The stages are not connected yet. This entry point exists so later runs share
one manifest: seed, dataset version, CWE selection, split IDs, graph config,
model config, hyperparameters, and metrics.
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

LOGGER = get_logger("run_experiment")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the pipeline described by an experiment config.")
    parser.add_argument("--config", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    experiment = load_config(args.config).get("experiment", {})
    LOGGER.info("Experiment id: %s", experiment.get("id"))
    LOGGER.info("Dataset config: %s", experiment.get("dataset_config"))
    LOGGER.info("Graph config: %s", experiment.get("graph_config"))
    LOGGER.info("Model config: %s", experiment.get("model_config"))
    raise NotImplementedError(
        "The experiment runner is not implemented. "
        "Do not start training until EDA, the CWE label policy, and a saved split exist."
    )


if __name__ == "__main__":
    main()

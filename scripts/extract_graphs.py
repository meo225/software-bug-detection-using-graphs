"""Extract graphs for function-level samples.

Planned usage, from the repository root::

    python scripts/extract_graphs.py --config configs/graph/cpg.yaml

CPG and Joern are candidates. This command does not run Joern yet.
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

LOGGER = get_logger("extract_graphs")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract graphs using the representation in a YAML config.")
    parser.add_argument("--config", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    graph = config.get("graph", {})
    LOGGER.info("Representation: %s (%s)", graph.get("name"), graph.get("status"))
    LOGGER.info("Extractor: %s", graph.get("extractor"))
    raise NotImplementedError(
        "Graph extraction is not implemented. "
        "Keep Joern calls inside src/graph/joern.py. "
        "Start from a 20 to 50 function manifest produced by EDA, not the full dataset."
    )


if __name__ == "__main__":
    main()

"""Show where a candidate dataset should be placed.

This command does not download archives. Dataset files stay out of Git.
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
from src.utils.paths import resolve_from_root  # noqa: E402

LOGGER = get_logger("download_data")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Print manual download instructions for a dataset config.")
    parser.add_argument("--config", type=Path, required=True, help="Dataset YAML under configs/data/.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    dataset = config.get("dataset", {})
    raw_dir = resolve_from_root(dataset.get("local_raw_dir", "data/raw"))
    raw_dir.mkdir(parents=True, exist_ok=True)
    LOGGER.info("Dataset: %s (%s)", dataset.get("name"), dataset.get("status"))
    LOGGER.info("Place files in: %s", raw_dir)
    LOGGER.info("Source page: %s", dataset.get("source_url"))
    LOGGER.info("Download page: %s", dataset.get("download_url"))
    if dataset.get("metadata_url"):
        LOGGER.info("Optional metadata page: %s", dataset.get("metadata_url"))
    LOGGER.info("Automatic download is disabled.")
    LOGGER.info("After the files are local, set dataset.version in %s.", args.config)
    LOGGER.info("Then run: python scripts/run_diversevul_eda.py --strict")


if __name__ == "__main__":
    main()

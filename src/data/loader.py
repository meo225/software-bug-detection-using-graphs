"""Load function-level vulnerability datasets.

Add a loader per dataset. The rest of the pipeline should depend on the
config name, not on DiverseVul-specific column names.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class DatasetLoader(Protocol):
    """Load one dataset release without dropping or relabeling rows."""

    name: str

    def load(self, raw_dir: Path) -> object:
        """Return the raw records. The concrete frame type is chosen during EDA."""


def load_dataset(name: str, raw_dir: Path) -> object:
    """Dispatch to the loader registered for ``name``.

    TODO: implement a DiverseVul loader after EDA confirms the file schema.
    Register Big-Vul, PrimeVul, or later datasets here instead of branching
    through the training code.
    """
    raise NotImplementedError(
        f"Loader for dataset {name!r} is not implemented. "
        f"Expected raw directory: {raw_dir}. "
        "Add the loader in src/data/loader.py and a YAML file under configs/data/."
    )

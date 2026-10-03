"""Adapt parsed graphs to the object a GNN batch expects.

PyTorch Geometric is intentionally not imported here. The training phase will
choose the concrete tensor type once the schema is known.
"""

from __future__ import annotations

from pathlib import Path


def graphs_to_dataset(graph_dir: Path, split_ids: dict[str, list[str]]) -> object:
    """Build a dataset view for the IDs in ``split_ids``.

    TODO: read parsed graphs and attach CWE labels. Do not resplit the data.
    """
    raise NotImplementedError(
        f"graphs_to_dataset is not implemented for {graph_dir} "
        f"and splits {sorted(split_ids)}."
    )

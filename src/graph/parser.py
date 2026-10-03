"""Parse extractor output into an in-memory graph.

The parsed object should be independent of Joern so later feature code can
consume AST, CFG, PDG, or CPG through one structure.
"""

from __future__ import annotations

from pathlib import Path


def parse_graph(path: Path) -> object:
    """Load one graph artifact.

    TODO: define the node and edge schema after the first Joern trial export.
    """
    raise NotImplementedError(f"parse_graph is not implemented for {path}.")

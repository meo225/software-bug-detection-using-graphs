"""Interface for turning a function into a graph.

Callers should depend on this protocol. Swapping Joern for another extractor
should not require edits outside ``src/graph/``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class GraphExtractor(Protocol):
    """Extract one graph for a single function-level sample."""

    name: str

    def extract(self, source_path: Path, output_path: Path) -> Path:
        """Write a graph artifact and return its path."""


def extract_graph(extractor: GraphExtractor, source_path: Path, output_path: Path) -> Path:
    """Run ``extractor`` on one function file.

    TODO: add batching, failure logs, and a small manifest of 20 to 50
    functions before any full-dataset run.
    """
    raise NotImplementedError(
        f"extract_graph via {extractor.name!r} is not implemented "
        f"({source_path} -> {output_path})."
    )

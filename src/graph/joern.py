"""Joern integration.

This is the only module that should know Joern's executable, export format,
and working directories. CPG is a candidate representation, not a decision.
"""

from __future__ import annotations

from pathlib import Path


class JoernExtractor:
    """Candidate extractor. Not wired to a local Joern install yet."""

    name = "joern"

    def __init__(self, executable: Path | None, representation: str = "cpg") -> None:
        self.executable = executable
        self.representation = representation

    def extract(self, source_path: Path, output_path: Path) -> Path:
        """Export one graph with Joern.

        TODO: invoke the executable from ``JOERN_PATH`` or the graph config.
        Do not shell out until a small sample manifest exists.
        """
        raise NotImplementedError(
            "JoernExtractor.extract is not implemented "
            f"(representation={self.representation!r}, executable={self.executable}, "
            f"{source_path} -> {output_path})."
        )

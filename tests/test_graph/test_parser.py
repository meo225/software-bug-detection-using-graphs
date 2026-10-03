"""Graph parser coverage to add after the first extractor trial."""

import pytest


@pytest.mark.skip(reason="TODO: parse a checked-in tiny graph fixture, not a full CPG export.")
def test_graph_parser_reads_nodes_and_edges() -> None:
    """The parser output must not depend on Joern types leaking into the dataset."""

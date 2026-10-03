"""Node features and edge features.

Feature choices depend on the graph schema and are not fixed yet.
"""

from __future__ import annotations


def build_node_features(graph: object) -> object:
    """Map graph nodes to a feature matrix. TODO: choose the feature set in config."""
    raise NotImplementedError("build_node_features is not implemented.")


def build_edge_features(graph: object) -> object:
    """Map graph edges to a feature matrix. TODO: encode edge types when the schema exists."""
    raise NotImplementedError("build_edge_features is not implemented.")

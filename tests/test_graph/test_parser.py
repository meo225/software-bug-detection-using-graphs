"""Coverage cho graph parser sẽ được thêm sau lần thử extractor đầu tiên."""

import pytest


@pytest.mark.skip(reason="TODO: parse graph fixture nhỏ đã commit, không dùng bản export CPG đầy đủ.")
def test_graph_parser_reads_nodes_and_edges() -> None:
    """Output của parser không được phụ thuộc vào kiểu Joern lọt vào dataset."""

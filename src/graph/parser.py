"""Parse output của extractor thành graph trong bộ nhớ.

Object sau khi parse phải độc lập với Joern để code tạo feature có thể xử lý
AST, CFG, PDG hoặc CPG thông qua cùng một cấu trúc.
"""

from __future__ import annotations

from pathlib import Path


def parse_graph(path: Path) -> object:
    """Load một graph artifact.

    TODO: xác định schema node và edge sau lần export thử đầu tiên bằng Joern.
    """
    raise NotImplementedError(f"Chưa triển khai parse_graph cho {path}.")

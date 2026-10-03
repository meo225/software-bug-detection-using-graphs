"""Interface chuyển một function thành graph.

Code gọi nên phụ thuộc vào protocol này. Việc thay Joern bằng extractor khác
không được yêu cầu chỉnh sửa bên ngoài ``src/graph/``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class GraphExtractor(Protocol):
    """Trích xuất một graph cho một sample ở mức function."""

    name: str

    def extract(self, source_path: Path, output_path: Path) -> Path:
        """Ghi graph artifact và trả về đường dẫn của artifact."""


def extract_graph(extractor: GraphExtractor, source_path: Path, output_path: Path) -> Path:
    """Chạy ``extractor`` trên một file function.

    TODO: thêm xử lý theo batch, log lỗi và manifest nhỏ gồm 20 đến 50
    function trước khi chạy trên toàn bộ dataset.
    """
    raise NotImplementedError(
        f"Chưa triển khai extract_graph qua {extractor.name!r} "
        f"({source_path} -> {output_path})."
    )

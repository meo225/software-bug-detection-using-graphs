"""Tích hợp Joern.

Đây là module duy nhất nên biết executable, định dạng export và thư mục làm việc
của Joern. CPG là representation ứng viên, chưa phải quyết định cuối cùng.
"""

from __future__ import annotations

from pathlib import Path


class JoernExtractor:
    """Extractor ứng viên, chưa kết nối với bản cài Joern local."""

    name = "joern"

    def __init__(self, executable: Path | None, representation: str = "cpg") -> None:
        self.executable = executable
        self.representation = representation

    def extract(self, source_path: Path, output_path: Path) -> Path:
        """Export một graph bằng Joern.

        TODO: gọi executable từ ``JOERN_PATH`` hoặc graph config.
        Không chạy tiến trình ngoài trước khi có sample manifest nhỏ.
        """
        raise NotImplementedError(
            "Chưa triển khai JoernExtractor.extract "
            f"(representation={self.representation!r}, executable={self.executable}, "
            f"{source_path} -> {output_path})."
        )

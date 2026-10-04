"""Các phép làm sạch và normalization để EDA đo lường nhưng chưa áp dụng phá hủy.

Báo cáo duplicate nên đếm các bản đã normalization nhưng không xóa dòng cho đến
khi nhóm chọn policy.
"""

from __future__ import annotations


def normalize_line_endings(source: str) -> str:
    """Chuyển line ending CRLF và CR thành LF.
    """
    return source.replace("\r\n", "\n").replace("\r", "\n")


def normalize_whitespace(source: str) -> str:
    """Chuẩn hóa line ending, trailing whitespace và dòng trống ở biên.

    Whitespace bên trong và comment được giữ nguyên để tránh thay đổi string
    literal, preprocessor directive hoặc ranh giới token trong C/C++.
    """
    lines = [line.rstrip(" \t") for line in normalize_line_endings(source).split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def strip_comments(source: str) -> str:
    """Chủ động không hỗ trợ xóa comment để audit C/C++ an toàn."""
    raise NotImplementedError(
        "Không dùng bước xóa comment vì regex có thể làm hỏng string và macro."
    )

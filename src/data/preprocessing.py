"""Cleaning and normalization that EDA may measure, but must not apply destructively yet.

Duplicate reports should count normalized copies. They should not delete rows
until the group chooses a policy.
"""

from __future__ import annotations


def normalize_line_endings(source: str) -> str:
    """Convert CRLF and CR to LF.
    """
    return source.replace("\r\n", "\n").replace("\r", "\n")


def normalize_whitespace(source: str) -> str:
    """Normalize line endings, trailing whitespace, and boundary blank lines.

    Internal whitespace and comments remain unchanged to avoid modifying C/C++
    string literals, preprocessor directives, or token boundaries.
    """
    lines = [line.rstrip(" \t") for line in normalize_line_endings(source).split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def strip_comments(source: str) -> str:
    """Comment stripping is intentionally unsupported for safe C/C++ audit."""
    raise NotImplementedError(
        "Comment stripping is not used: regex-based removal can corrupt strings and macros."
    )

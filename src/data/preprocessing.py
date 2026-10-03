"""Cleaning and normalization that EDA may measure, but must not apply destructively yet.

Duplicate reports should count normalized copies. They should not delete rows
until the group chooses a policy.
"""

from __future__ import annotations


def normalize_line_endings(source: str) -> str:
    """Convert CRLF and CR to LF.

    TODO: implement and unit test before using the result as a duplicate key.
    """
    raise NotImplementedError("normalize_line_endings is not implemented.")


def normalize_whitespace(source: str) -> str:
    """Normalize line endings and trailing whitespace per line.

    TODO: define the exact rule during EDA and keep the original column.
    """
    raise NotImplementedError("normalize_whitespace is not implemented.")


def strip_comments(source: str) -> str:
    """Remove comments only if the rule is safe for C/C++.

    TODO: do not ship a brittle regex that corrupts strings. Leave this
    unimplemented until the group decides the normalization is worth the risk.
    """
    raise NotImplementedError("strip_comments is not implemented.")

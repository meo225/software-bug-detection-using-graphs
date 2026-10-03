"""Duplicate reports. Detection only; this module must not delete rows."""

from __future__ import annotations


def exact_source_duplicates(records: object, code_field: str) -> object:
    """Group records whose source text matches exactly.

    TODO: implement after the code column name is confirmed.
    """
    raise NotImplementedError(
        f"exact_source_duplicates is not implemented for field {code_field!r}."
    )


def hash_duplicates(records: object, hash_field: str) -> object:
    """Group records by a hash column shipped with the dataset, when one exists."""
    raise NotImplementedError(f"hash_duplicates is not implemented for field {hash_field!r}.")


def conflicting_label_duplicates(records: object, code_field: str, label_field: str) -> object:
    """Find identical source text that carries more than one label."""
    raise NotImplementedError(
        "conflicting_label_duplicates is not implemented "
        f"for code field {code_field!r} and label field {label_field!r}."
    )


def normalized_source_duplicates(records: object, code_field: str) -> object:
    """Hash source after line-ending and whitespace normalization, then find duplicates.

    TODO: call ``src.data.preprocessing`` rather than copying its rules.
    Comment stripping stays optional until it is safe.
    """
    raise NotImplementedError(
        f"normalized_source_duplicates is not implemented for field {code_field!r}."
    )

"""Duplicate reports. Detection only; this module must not delete rows."""

from __future__ import annotations

import hashlib

import pandas as pd

from src.data.preprocessing import normalize_whitespace


def source_hashes(source: pd.Series, normalized: bool = False) -> pd.Series:
    """Hash source exactly or after conservative normalization."""
    def digest(value: object) -> str | None:
        if not isinstance(value, str) or not value.strip():
            return None
        text = normalize_whitespace(value) if normalized else value
        return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()

    return source.map(digest)


def exact_source_duplicates(records: pd.DataFrame, code_field: str) -> pd.Series:
    """Group records whose source text matches exactly.

    Returns a hash key per row and leaves the input unchanged.
    """
    return source_hashes(records[code_field])


def hash_duplicates(records: pd.DataFrame, hash_field: str) -> pd.Series:
    """Group records by a hash column shipped with the dataset, when one exists."""
    return records[hash_field].duplicated(keep=False)


def conflicting_label_duplicates(records: pd.DataFrame, code_field: str, label_field: str) -> pd.DataFrame:
    """Find identical source text that carries more than one label."""
    working = records.copy()
    working["_source_hash"] = source_hashes(working[code_field])
    conflict_keys = working.groupby("_source_hash")[label_field].nunique(dropna=True)
    return working[working["_source_hash"].isin(conflict_keys[conflict_keys > 1].index)]


def normalized_source_duplicates(records: pd.DataFrame, code_field: str) -> pd.Series:
    """Hash source after line-ending and whitespace normalization, then find duplicates.

    Comment stripping and internal whitespace collapsing are intentionally omitted.
    """
    return source_hashes(records[code_field], normalized=True)


def duplicate_summary(records: pd.DataFrame) -> pd.DataFrame:
    """Compare exact and normalized duplicates, including label conflicts."""
    working = records.copy()
    working["raw_source_sha256"] = source_hashes(working["source_code"])
    working["normalized_source_sha256"] = source_hashes(working["source_code"], normalized=True)
    working["cwe_key"] = working["cwe_list"].map(lambda labels: "|".join(sorted(labels)))
    rows = []
    for level, column in (("raw_source", "raw_source_sha256"), ("normalized_source", "normalized_source_sha256")):
        valid = working.dropna(subset=[column])
        sizes = valid.groupby(column).size()
        duplicate_keys = set(sizes[sizes > 1].index)
        duplicated = valid[valid[column].isin(duplicate_keys)]
        vuln_conflicts = duplicated.groupby(column)["is_vulnerable"].nunique(dropna=True)
        cwe_conflicts = duplicated.groupby(column)["cwe_key"].nunique(dropna=False)
        rows.append({
            "level": level,
            "records_with_code": len(valid),
            "unique_code": int(valid[column].nunique()),
            "duplicate_groups": len(duplicate_keys),
            "duplicate_affected_records": len(duplicated),
            "duplicate_excess_records": int((sizes - 1).clip(lower=0).sum()),
            "duplicate_affected_percentage": 100.0 * len(duplicated) / len(valid) if len(valid) else 0.0,
            "vulnerable_label_conflict_groups": int((vuln_conflicts > 1).sum()),
            "cwe_conflict_groups": int((cwe_conflicts > 1).sum()),
        })
    return pd.DataFrame(rows)

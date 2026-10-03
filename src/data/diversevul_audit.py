"""Reproducible DiverseVul dataset audit.

This module describes the supplied release. It never drops records, resolves
multi-CWE samples to one class, or selects a final experiment threshold.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.data.cwe import cwe_distribution, multi_cwe_summary, parse_cwe_labels, threshold_summary
from src.data.deduplication import duplicate_summary

PAPER_STATS = {
    "total_samples": 349_437,
    "vulnerable_samples": 18_945,
    "non_vulnerable_samples": 330_492,
    "unique_projects": 797,
    "unique_commits": 7_514,
    "unique_cwe": 150,
}

FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "sample_id": ("sample_id", "id", "idx", "index"),
    "source_code": ("func", "function", "source_code", "code", "function_code"),
    "is_vulnerable": ("target", "vulnerable", "is_vulnerable", "label", "vul"),
    "cwe": ("cwe", "cwes", "cwe_id", "cwe_ids"),
    "project": ("project", "project_name", "repo_name", "repository_name"),
    "commit": ("commit_id", "commit", "sha", "commit_hash"),
    "provided_hash": ("hash", "md5", "function_hash", "func_hash"),
    "cve": ("cve", "cve_id", "cve_ids"),
    "repository": ("repository", "repo", "repository_url", "repo_url"),
}

REQUIRED_FIELDS = ("source_code", "is_vulnerable", "cwe", "project", "commit")


@dataclass(frozen=True)
class AuditResult:
    """Computed tables plus canonical records used by report and notebook."""

    records: pd.DataFrame
    fields: dict[str, str | None]
    tables: dict[str, pd.DataFrame]
    findings: dict[str, Any]


def _pick_column(columns: list[str], aliases: tuple[str, ...]) -> str | None:
    lookup = {column.lower(): column for column in columns}
    matches = [lookup[alias.lower()] for alias in aliases if alias.lower() in lookup]
    return matches[0] if matches else None


def resolve_fields(frame: pd.DataFrame, configured: dict[str, str | None] | None = None) -> dict[str, str | None]:
    """Resolve actual schema fields, preferring explicit config values."""
    configured = configured or {}
    config_keys = {
        "source_code": "code_field", "is_vulnerable": "label_field", "cwe": "cwe_field",
        "project": "project_field", "commit": "commit_field", "provided_hash": "hash_field",
    }
    resolved: dict[str, str | None] = {}
    for canonical, aliases in FIELD_ALIASES.items():
        explicit = configured.get(config_keys.get(canonical, ""))
        if explicit:
            if explicit not in frame.columns:
                raise KeyError(f"Configured field {explicit!r} is not in dataset columns.")
            resolved[canonical] = explicit
        else:
            resolved[canonical] = _pick_column(list(frame.columns), aliases)
    missing = [field for field in REQUIRED_FIELDS if resolved[field] is None]
    if missing:
        raise ValueError(
            "Could not resolve required fields: " + ", ".join(missing) +
            ". Actual columns: " + ", ".join(map(str, frame.columns))
        )
    return resolved


def parse_vulnerable(value: object) -> bool | None:
    """Parse common binary encodings; return None for unknown values."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)) and value in (0, 1):
        return bool(value)
    if isinstance(value, float) and value in (0.0, 1.0):
        return bool(int(value))
    text = str(value).strip().lower()
    if text in {"1", "true", "vulnerable", "vul", "yes"}:
        return True
    if text in {"0", "false", "non-vulnerable", "non_vulnerable", "safe", "no"}:
        return False
    return None


def canonicalize(frame: pd.DataFrame, fields: dict[str, str | None]) -> pd.DataFrame:
    """Add a canonical audit view while retaining the raw row count."""
    result = pd.DataFrame(index=frame.index)
    result["sample_id"] = (
        frame[fields["sample_id"]].astype(str)
        if fields["sample_id"] else frame.index.map(lambda index: f"row-{index}")
    )
    for name in ("source_code", "project", "commit", "provided_hash", "cve", "repository"):
        source = fields[name]
        result[name] = frame[source] if source else None
    result["is_vulnerable"] = frame[fields["is_vulnerable"]].map(parse_vulnerable)
    result["cwe_raw"] = frame[fields["cwe"]]
    result["cwe_list"] = result["cwe_raw"].map(parse_cwe_labels)
    return result


def schema_table(frame: pd.DataFrame, fields: dict[str, str | None]) -> pd.DataFrame:
    """Describe every raw column and its canonical meaning, when recognized."""
    inverse = {actual: canonical for canonical, actual in fields.items() if actual}
    rows = []
    for column in frame.columns:
        missing = int(frame[column].isna().sum())
        non_missing = frame[column].dropna()
        example = "" if non_missing.empty else str(non_missing.iloc[0]).replace("\n", "\\n")[:160]
        rows.append({
            "field": column,
            "meaning": inverse.get(column, "unmapped raw field"),
            "dtype": str(frame[column].dtype),
            "missing_count": missing,
            "missing_percentage": 100.0 * missing / len(frame) if len(frame) else 0.0,
            "example": example,
        })
    for canonical, actual in fields.items():
        if actual is None:
            rows.append({
                "field": "NOT PRESENT", "meaning": canonical, "dtype": "N/A",
                "missing_count": len(frame), "missing_percentage": 100.0, "example": "",
            })
    return pd.DataFrame(rows)


def _project_tables(records: pd.DataFrame, vulnerable: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    exploded = vulnerable[vulnerable["cwe_list"].map(bool)].explode("cwe_list").rename(columns={"cwe_list": "cwe"})
    total_by_project = records.groupby("project", dropna=False)["sample_id"].nunique().rename("total_samples")
    vulnerable_by_project = vulnerable.groupby("project", dropna=False)["sample_id"].nunique().rename("vulnerable_samples")
    cwe_by_project = exploded.groupby("project", dropna=False)["cwe"].nunique().rename("number_of_cwe")
    all_project = pd.concat([total_by_project, vulnerable_by_project, cwe_by_project], axis=1).fillna(0).reset_index()
    all_project[["total_samples", "vulnerable_samples", "number_of_cwe"]] = all_project[
        ["total_samples", "vulnerable_samples", "number_of_cwe"]
    ].astype(int)
    by_project = exploded.groupby(["cwe", "project"], dropna=False)["sample_id"].nunique().rename("count").reset_index()
    grouped = by_project.groupby("cwe")
    cwe_project = grouped.agg(
        sample_count=("count", "sum"), project_count=("project", lambda values: values.dropna().nunique()),
        largest_project_sample_count=("count", "max"),
    ).reset_index()
    cwe_project["largest_project_share"] = cwe_project["largest_project_sample_count"].div(cwe_project["sample_count"]).mul(100)
    feasibility = []
    for minimum_projects in (2, 3, 5, 10):
        eligible = cwe_project[cwe_project["project_count"] >= minimum_projects]
        feasibility.append({
            "minimum_projects_per_cwe": minimum_projects,
            "number_of_cwe": len(eligible),
            "number_of_cwe_with_at_least_20_samples": int((eligible["sample_count"] >= 20).sum()),
            "number_of_cwe_with_at_least_50_samples": int((eligible["sample_count"] >= 50).sum()),
            "number_of_cwe_with_at_least_100_samples": int((eligible["sample_count"] >= 100).sum()),
            "number_of_cwe_with_at_least_200_samples": int((eligible["sample_count"] >= 200).sum()),
        })
    return (
        all_project.sort_values("total_samples", ascending=False, ignore_index=True),
        cwe_project.sort_values(["sample_count", "cwe"], ascending=[False, True], ignore_index=True),
        pd.DataFrame(feasibility),
    )


def _length_table(records: pd.DataFrame) -> pd.DataFrame:
    source = records["source_code"].fillna("").astype(str)
    chars = source.str.len()
    lines = source.map(lambda text: 0 if not text else text.count("\n") + 1)
    rows = []
    for metric, values in (("characters_per_function", chars), ("lines_per_function", lines)):
        rows.append({
            "metric": metric, "min": values.min(), "median": values.median(), "mean": values.mean(),
            "p90": values.quantile(0.90), "p95": values.quantile(0.95),
            "p99": values.quantile(0.99), "max": values.max(),
        })
    return pd.DataFrame(rows)


def _source_quality_summary(records: pd.DataFrame) -> pd.DataFrame:
    source = records["source_code"]
    text = source.fillna("").astype(str)
    lines = text.map(lambda value: 0 if not value else value.count("\n") + 1)
    return pd.DataFrame([
        {"check": "missing_source", "sample_count": int(source.isna().sum()), "definition": "raw source value is null"},
        {"check": "empty_source", "sample_count": int(text.str.strip().eq("").sum()), "definition": "source is null, empty, or whitespace-only"},
        {"check": "very_short_source", "sample_count": int(((text.str.len() < 20) | (lines < 3)).sum()), "definition": "fewer than 20 characters or 3 lines (screening flag only)"},
        {"check": "very_long_source", "sample_count": int(((text.str.len() > 10_000) | (lines > 500)).sum()), "definition": "more than 10,000 characters or 500 lines (screening flag only)"},
    ])


def _sample_manifest(vulnerable: pd.DataFrame, size: int = 30, seed: int = 105) -> pd.DataFrame:
    candidates = vulnerable[vulnerable["source_code"].fillna("").astype(str).str.strip().ne("")].copy()
    if candidates.empty:
        return pd.DataFrame(columns=["sample_id", "project", "commit", "cwe", "label", "source_reference"])
    candidates["length"] = candidates["source_code"].astype(str).str.len()
    candidates["length_band"] = pd.qcut(candidates["length"].rank(method="first"), 3, labels=["short", "medium", "long"])
    candidates["cwe_count_band"] = candidates["cwe_list"].map(lambda labels: "multi" if len(labels) >= 2 else "single")
    sampled = []
    per_group = max(1, math.ceil(size / 6))
    for _, group in candidates.groupby(["length_band", "cwe_count_band"], observed=True):
        sampled.append(group.sample(min(per_group, len(group)), random_state=seed))
    chosen = pd.concat(sampled).drop_duplicates("sample_id") if sampled else candidates.iloc[0:0]
    if len(chosen) < min(size, len(candidates)):
        remainder = candidates[~candidates["sample_id"].isin(chosen["sample_id"])]
        chosen = pd.concat([chosen, remainder.sample(min(size - len(chosen), len(remainder)), random_state=seed)])
    chosen = chosen.head(size).copy()
    chosen["cwe"] = chosen["cwe_list"].map(lambda labels: "|".join(labels))
    chosen["label"] = "vulnerable"
    chosen["source_reference"] = chosen["sample_id"].map(lambda value: f"dataset row sample_id={value}")
    return chosen[["sample_id", "project", "commit", "cwe", "label", "source_reference"]]


def run_audit(frame: pd.DataFrame, configured: dict[str, str | None] | None = None) -> AuditResult:
    """Compute the complete in-memory audit from actual records."""
    fields = resolve_fields(frame, configured)
    records = canonicalize(frame, fields)
    unknown_labels = int(records["is_vulnerable"].isna().sum())
    if unknown_labels:
        examples = records.loc[records["is_vulnerable"].isna(), "sample_id"].head(5).tolist()
        raise ValueError(f"{unknown_labels} vulnerable labels could not be parsed; sample IDs: {examples}")
    vulnerable = records[records["is_vulnerable"] == True].copy()  # noqa: E712
    labeled = vulnerable[vulnerable["cwe_list"].map(bool)].copy()
    cwe = cwe_distribution(vulnerable)
    project, cwe_project, feasibility = _project_tables(records, vulnerable)
    all_cwe = {label for labels in records["cwe_list"] for label in labels}
    actual = {
        "total_samples": len(records),
        "vulnerable_samples": len(vulnerable),
        "non_vulnerable_samples": int((records["is_vulnerable"] == False).sum()),  # noqa: E712
        "unique_projects": int(records["project"].nunique(dropna=True)),
        "unique_commits": int(records["commit"].nunique(dropna=True)),
        "unique_cwe": len(all_cwe),
    }
    comparison = pd.DataFrame([
        {"metric": metric, "paper": paper, "dataset_actual": actual[metric], "difference": actual[metric] - paper}
        for metric, paper in PAPER_STATS.items()
    ])
    summary = pd.DataFrame([{"metric": key, "value": value} for key, value in actual.items()] + [
        {"metric": "vulnerable_with_cwe", "value": len(labeled)},
        {"metric": "vulnerable_without_cwe", "value": len(vulnerable) - len(labeled)},
        {"metric": "vulnerable_cwe_coverage_percentage", "value": 100.0 * len(labeled) / len(vulnerable) if len(vulnerable) else 0.0},
    ])
    missing = schema_table(frame, fields)
    cwe_count_distribution = vulnerable["cwe_list"].map(len).value_counts().sort_index().rename_axis("number_of_cwe_per_sample").reset_index(name="sample_count")
    multi_examples = vulnerable[vulnerable["cwe_list"].map(len) >= 2].head(20).copy()
    multi_examples["cwe"] = multi_examples["cwe_list"].map(lambda labels: "|".join(labels))
    multi_examples["code_preview"] = multi_examples["source_code"].fillna("").astype(str).str.replace("\n", " ").str.slice(0, 200)
    tables = {
        "dataset_summary": summary,
        "paper_comparison": comparison,
        "missing_values": missing,
        "cwe_distribution": cwe,
        "threshold_analysis": threshold_summary(cwe, labeled),
        "multi_cwe_summary": multi_cwe_summary(vulnerable),
        "cwe_count_distribution": cwe_count_distribution,
        "multi_cwe_examples": multi_examples[["sample_id", "project", "commit", "cwe", "code_preview"]],
        "project_distribution": project,
        "cwe_project_distribution": cwe_project,
        "project_split_feasibility": feasibility,
        "duplicate_summary": duplicate_summary(records),
        "source_quality_summary": _source_quality_summary(records),
        "function_length_summary": _length_table(records),
        "source_inspection_sample": vulnerable.sample(min(30, len(vulnerable)), random_state=105).assign(
            cwe=lambda data: data["cwe_list"].map(lambda labels: "|".join(labels)),
            code_preview=lambda data: data["source_code"].fillna("").astype(str).str.replace("\n", " ").str.slice(0, 240),
        )[["sample_id", "project", "commit", "cwe", "code_preview"]],
        "graph_sample_manifest": _sample_manifest(vulnerable),
    }
    findings = {
        **actual,
        "raw_column_count": len(frame.columns),
        "vulnerable_with_cwe": len(labeled),
        "vulnerable_without_cwe": len(vulnerable) - len(labeled),
        "multi_cwe_samples": int((vulnerable["cwe_list"].map(len) >= 2).sum()),
        "unique_cwe_vulnerable": int(cwe["cwe"].nunique()),
    }
    return AuditResult(records=records, fields=fields, tables=tables, findings=findings)


def read_optional_metadata(raw_dir: Path) -> tuple[pd.DataFrame | None, Path | None]:
    """Load one clearly named metadata table when present."""
    from src.data.loader import read_records

    candidates = [path for path in Path(raw_dir).rglob("*") if path.is_file() and any(marker in path.name.lower() for marker in METADATA_MARKERS)]
    candidates = [path for path in candidates if path.suffix.lower() in {".csv", ".json", ".jsonl", ".ndjson", ".parquet"}]
    if not candidates:
        return None, None
    candidates.sort(key=lambda path: path.stat().st_size, reverse=True)
    return read_records(candidates[0]), candidates[0].resolve()


def metadata_audit(records: pd.DataFrame, metadata: pd.DataFrame | None) -> pd.DataFrame:
    """Measure commit-level join and URL coverage without assuming completeness."""
    columns = ["metric", "value", "note"]
    if metadata is None:
        return pd.DataFrame([["metadata_status", "not_provided", "No separate metadata file was found."]], columns=columns)
    commit_col = _pick_column(list(metadata.columns), FIELD_ALIASES["commit"])
    repo_url_col = _pick_column(list(metadata.columns), ("repository_url", "repo_url", "repository"))
    commit_url_col = _pick_column(list(metadata.columns), ("commit_url", "url"))
    if commit_col is None:
        return pd.DataFrame([["metadata_status", "unjoinable", "No commit ID field was detected in metadata."]], columns=columns)
    record_commits = set(records["commit"].dropna().astype(str))
    meta_commits = set(metadata[commit_col].dropna().astype(str))
    joined = len(record_commits & meta_commits)
    return pd.DataFrame([
        ["dataset_unique_commits", len(record_commits), ""],
        ["metadata_unique_commits", len(meta_commits), ""],
        ["joined_unique_commits", joined, "Commit ID intersection"],
        ["unjoined_dataset_commits", len(record_commits - meta_commits), ""],
        ["missing_commit_url_rows", int(metadata[commit_url_col].isna().sum()) if commit_url_col else len(metadata), "field absent" if not commit_url_col else ""],
        ["missing_repo_url_rows", int(metadata[repo_url_col].isna().sum()) if repo_url_col else len(metadata), "field absent" if not repo_url_col else ""],
    ], columns=columns)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, default=str) + "\n", encoding="utf-8")

"""Kiểm định MegaVul trước khi đổi dataset chính.

Số liệu tác giả, số liệu đo trên ``megavul_simple.json`` và số liệu đo trên mirror
được giữ riêng. Mirror không trở thành release gốc chỉ vì mang tên MegaVul.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import pyarrow.dataset as parquet_dataset

from src.data.cwe import cwe_distribution, parse_cwe_labels, threshold_summary
from src.data.deduplication import duplicate_summary
from src.data.diversevul_audit import parse_vulnerable


AUTHOR_RELEASE = {
    "name": "MegaVul C/C++ 2024-04",
    "repository": "https://github.com/Icyrockton/MegaVul",
    "artifact_url": "https://1drv.ms/f/s!AtzrzuojQf5sgeISZ9zN_4owVnUn9g",
    "simple_filename": "megavul_simple.json",
    "total_samples": 353_873,
    "vulnerable_samples": 17_975,
    "non_vulnerable_samples": 335_898,
    "unique_projects": 1_062,
    "unique_commits": 9_288,
    "unique_cve": 8_476,
    "unique_cwe": 176,
    "graph_success_percentage": 87.0,
}

OFFICIAL_SIMPLE_FIELDS = frozenset({
    "cve_id", "cwe_ids", "repo_name", "commit_hash", "git_url", "file_path",
    "func_name", "func_before", "func", "is_vul",
})
MIRROR_COLUMNS = ("cve_id", "hash", "repo_url", "cwe_id", "language", "file_paths")
AUTHOR_COUNT_FIELDS = (
    "total_samples", "vulnerable_samples", "non_vulnerable_samples",
    "unique_projects", "unique_commits", "unique_cve", "unique_cwe",
)
PROJECT_SUPPORT_LEVELS = (2, 3, 5, 10)


@dataclass(frozen=True)
class MirrorAudit:
    """Kết quả để quyết định mirror có được thay artifact gốc hay không."""

    summary: pd.DataFrame
    schema: pd.DataFrame
    usable_as_official_release: bool
    reasons: tuple[str, ...]


def canonicalize_official_simple(frame: pd.DataFrame) -> pd.DataFrame:
    """Ánh xạ ``megavul_simple.json`` và giữ đúng code trước bản vá."""
    missing = sorted(OFFICIAL_SIMPLE_FIELDS - set(frame.columns))
    if missing:
        raise ValueError("Thiếu field bắt buộc của MegaVul Simple: " + ", ".join(missing))

    result = pd.DataFrame(index=frame.index)
    result["sample_id"] = frame.index.map(lambda index: f"megavul-{index}")
    result["is_vulnerable"] = frame["is_vul"].map(parse_vulnerable)
    unknown = int(result["is_vulnerable"].isna().sum())
    if unknown:
        raise ValueError(f"Có {unknown} giá trị is_vul không parse được.")

    # ``func`` luôn là bản sau vá. Mẫu vulnerable phải dùng ``func_before``.
    source_code = frame["func"].copy()
    vulnerable = result["is_vulnerable"].eq(True)
    source_code.loc[vulnerable] = frame.loc[vulnerable, "func_before"]
    result["source_code"] = source_code
    result["cwe_raw"] = frame["cwe_ids"]
    result["cwe_list"] = result["cwe_raw"].map(parse_cwe_labels)
    result["project"] = frame["repo_name"]
    result["commit"] = frame["commit_hash"]
    result["cve"] = frame["cve_id"]
    result["repository"] = frame["git_url"].map(_repository_from_commit_url)
    result["file_path"] = frame["file_path"]
    result["function_name"] = frame["func_name"]
    if "func_graph_path_before" in frame.columns:
        result["graph_path_before"] = frame["func_graph_path_before"]
    if "func_graph_path" in frame.columns:
        result["graph_path_after"] = frame["func_graph_path"]
    return result


def summarize_official_simple(records: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Tính các chỉ số gate trên frame đã canonicalize. Không xóa dòng."""
    required = {"sample_id", "source_code", "is_vulnerable", "cwe_list", "project", "commit", "cve"}
    missing = sorted(required - set(records.columns))
    if missing:
        raise ValueError("Frame MegaVul chưa canonicalize, thiếu: " + ", ".join(missing))

    vulnerable = records[records["is_vulnerable"].eq(True)].copy()
    labeled = vulnerable[vulnerable["cwe_list"].map(bool)].copy()
    distribution = cwe_distribution(vulnerable)
    all_cwe = {label for labels in records["cwe_list"] for label in labels}
    missing_source = int(vulnerable["source_code"].fillna("").astype(str).str.strip().eq("").sum())
    summary = pd.DataFrame([
        {"metric": "total_samples", "value": len(records)},
        {"metric": "vulnerable_samples", "value": len(vulnerable)},
        {"metric": "non_vulnerable_samples", "value": int(records["is_vulnerable"].eq(False).sum())},
        {"metric": "unique_projects", "value": int(records["project"].nunique(dropna=True))},
        {"metric": "unique_commits", "value": int(records["commit"].nunique(dropna=True))},
        {"metric": "unique_cve", "value": int(records["cve"].nunique(dropna=True))},
        {"metric": "unique_cwe", "value": len(all_cwe)},
        {"metric": "vulnerable_with_cwe", "value": len(labeled)},
        {"metric": "vulnerable_without_cwe", "value": len(vulnerable) - len(labeled)},
        {
            "metric": "vulnerable_cwe_coverage_percentage",
            "value": 100.0 * len(labeled) / len(vulnerable) if len(vulnerable) else 0.0,
        },
        {"metric": "vulnerable_missing_before_code", "value": missing_source},
    ])
    tables = {
        "summary": summary,
        "threshold_analysis": threshold_summary(distribution, labeled),
        "duplicate_summary": duplicate_summary(records),
        "project_support": _project_support(distribution),
        "author_comparison": _author_comparison(summary),
    }
    graph_tables = _graph_tables(records)
    if graph_tables:
        tables.update(graph_tables)
        graph_summary = graph_tables["graph_path_summary"].set_index("metric")["value"]
        summary = pd.concat([
            summary,
            pd.DataFrame([
                {"metric": "vulnerable_before_graph_percentage", "value": graph_summary["vulnerable_before_graph_percentage"]},
                {"metric": "source_with_matching_graph_percentage", "value": graph_summary["source_with_matching_graph_percentage"]},
            ]),
        ], ignore_index=True)
        tables["summary"] = summary
    return tables


def audit_huggingface_mirror(raw_dir: Path) -> MirrorAudit:
    """Đo mirror Parquet. Mỗi dòng không được suy ra là một function gốc."""
    files = sorted(Path(raw_dir).glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"Không có shard Parquet trong {raw_dir}")

    dataset = parquet_dataset.dataset([str(path) for path in files], format="parquet")
    missing_columns = sorted(set(MIRROR_COLUMNS) - set(dataset.schema.names))
    if missing_columns:
        raise ValueError("Mirror Parquet thiếu cột provenance: " + ", ".join(missing_columns))

    metadata = dataset.to_table(columns=list(MIRROR_COLUMNS)).to_pandas()
    hash_counts = metadata["hash"].value_counts(dropna=True)
    summary_values = {
        "rows": len(metadata),
        "unique_hash": int(metadata["hash"].nunique(dropna=True)),
        "duplicate_metadata_rows": int(metadata.duplicated().sum()),
        "rows_in_repeated_hash_groups": int(metadata["hash"].duplicated(keep=False).sum()),
        "maximum_rows_per_hash": int(hash_counts.max()) if len(hash_counts) else 0,
        "unique_cve": int(metadata["cve_id"].nunique(dropna=True)),
        "unique_cwe_raw": int(metadata["cwe_id"].nunique(dropna=True)),
        "unique_commit_urls": int(metadata["repo_url"].nunique(dropna=True)),
    }
    summary = pd.DataFrame([{"metric": key, "value": value} for key, value in summary_values.items()])
    schema = pd.DataFrame([
        {"field": field.name, "dtype": str(field.type), "nullable": field.nullable}
        for field in dataset.schema
    ])

    reasons: list[str] = []
    expected_rows = AUTHOR_RELEASE["total_samples"]
    if summary_values["rows"] != expected_rows:
        reasons.append(
            f"Số dòng mirror {summary_values['rows']:,} khác {expected_rows:,} function tác giả công bố."
        )
    if summary_values["duplicate_metadata_rows"]:
        reasons.append(f"Có {summary_values['duplicate_metadata_rows']:,} dòng metadata lặp hoàn toàn.")
    if summary_values["maximum_rows_per_hash"] > 1:
        reasons.append(f"Một hash xuất hiện tối đa {summary_values['maximum_rows_per_hash']:,} lần.")
    missing_fields = sorted({"is_vul", "func", "func_before", "cwe_ids", "repo_name", "commit_hash"} - set(dataset.schema.names))
    if missing_fields:
        reasons.append("Mirror không giữ schema gốc: thiếu " + ", ".join(missing_fields) + ".")
    return MirrorAudit(summary, schema, not reasons, tuple(reasons))


def candidate_matrix(
    diversevul_summary: Path,
    mirror: MirrorAudit | None = None,
    official_summary: pd.DataFrame | None = None,
    has_commit_date: bool | None = None,
) -> pd.DataFrame:
    """Ma trận quyết định. Cột MegaVul đo local để trống cho đến khi có file gốc."""
    diverse = pd.read_csv(diversevul_summary).set_index("metric")["value"]
    measured = None if official_summary is None else official_summary.set_index("metric")["value"]

    def diverse_count(metric: str) -> int:
        return int(diverse[metric])

    def megavul_count(metric: str) -> str | int:
        if measured is None:
            return "chưa đo"
        return int(measured[metric])

    mirror_decision = "chưa kiểm tra"
    mirror_note = "Chưa có shard Parquet."
    if mirror is not None:
        mirror_decision = "không" if not mirror.usable_as_official_release else "có"
        mirror_rows = int(mirror.summary.set_index("metric").loc["rows", "value"])
        mirror_note = f"Đã đo {mirror_rows:,} dòng mirror."

    rows = [
        {
            "criterion": "artifact dùng để đếm function",
            "diversevul_measured": "diversevul.jsonl đã audit",
            "megavul_measured": "megavul_simple.json" if measured is not None else "chưa có file gốc",
            "megavul_author_reported": AUTHOR_RELEASE["simple_filename"],
            "note": "OneDrive do repository tác giả trỏ tới",
        },
        {
            "criterion": "tổng function",
            "diversevul_measured": diverse_count("total_samples"),
            "megavul_measured": megavul_count("total_samples"),
            "megavul_author_reported": AUTHOR_RELEASE["total_samples"],
            "note": "Số tác giả không thay cho file local",
        },
        {
            "criterion": "vulnerable function",
            "diversevul_measured": diverse_count("vulnerable_samples"),
            "megavul_measured": megavul_count("vulnerable_samples"),
            "megavul_author_reported": AUTHOR_RELEASE["vulnerable_samples"],
            "note": "Số tác giả không thay cho file local",
        },
        {
            "criterion": "CWE unique",
            "diversevul_measured": diverse_count("unique_cwe"),
            "megavul_measured": megavul_count("unique_cwe"),
            "megavul_author_reported": AUTHOR_RELEASE["unique_cwe"],
            "note": "Số local là CWE dạng số; tác giả tính thêm CWE-Other",
        },
        {
            "criterion": "timestamp commit",
            "diversevul_measured": "không có trong artifact đã audit",
            "megavul_measured": _commit_date_status(measured, has_commit_date),
            "megavul_author_reported": "có trong megavul.json; không có trong bản Simple",
            "note": "Chronological split cần bản đầy đủ",
        },
        {
            "criterion": "graph Joern công bố sẵn",
            "diversevul_measured": "không",
            "megavul_measured": _graph_status(measured),
            "megavul_author_reported": f"{AUTHOR_RELEASE['graph_success_percentage']:.0f}% function tạo graph thành công",
            "note": "Path trong JSON chưa được kiểm tra bằng file graph",
        },
        {
            "criterion": "mirror Hugging Face thay được artifact gốc",
            "diversevul_measured": "không áp dụng",
            "megavul_measured": mirror_decision,
            "megavul_author_reported": "không áp dụng",
            "note": mirror_note,
        },
    ]
    return pd.DataFrame(rows)


def _commit_date_status(measured: pd.Series | None, has_commit_date: bool | None) -> str:
    if measured is None:
        return "chưa đo"
    if has_commit_date:
        return "có"
    return "không có commit_date"


def _graph_status(measured: pd.Series | None) -> str:
    if measured is None or "vulnerable_before_graph_percentage" not in measured.index:
        return "chưa đo"
    percentage = float(measured["vulnerable_before_graph_percentage"])
    return f"{percentage:.2f}% vulnerable có path graph trước vá"


def _path_present(values: pd.Series) -> pd.Series:
    text = values.fillna("").astype(str).str.strip()
    return text.ne("") & text.str.lower().ne("none") & text.str.lower().ne("null")


def _graph_tables(records: pd.DataFrame) -> dict[str, pd.DataFrame] | None:
    """Đếm path graph được khai báo. Chưa kiểm tra file graph có tồn tại trên đĩa."""
    if "graph_path_before" not in records.columns and "graph_path_after" not in records.columns:
        return None
    vulnerable = records[records["is_vulnerable"].eq(True)]
    non_vulnerable = records[records["is_vulnerable"].eq(False)]
    before = _path_present(vulnerable["graph_path_before"]) if "graph_path_before" in vulnerable else pd.Series(False, index=vulnerable.index)
    after_vul = _path_present(vulnerable["graph_path_after"]) if "graph_path_after" in vulnerable else pd.Series(False, index=vulnerable.index)
    after_non = _path_present(non_vulnerable["graph_path_after"]) if "graph_path_after" in non_vulnerable else pd.Series(False, index=non_vulnerable.index)
    matching = pd.Series(False, index=records.index)
    if len(vulnerable):
        matching.loc[vulnerable.index] = before.to_numpy()
    if len(non_vulnerable):
        matching.loc[non_vulnerable.index] = after_non.to_numpy()
    summary = pd.DataFrame([
        {"metric": "vulnerable_with_before_graph", "value": int(before.sum())},
        {"metric": "vulnerable_missing_before_graph", "value": int((~before).sum())},
        {"metric": "vulnerable_before_graph_percentage", "value": 100.0 * float(before.mean()) if len(vulnerable) else 0.0},
        {"metric": "vulnerable_with_after_graph", "value": int(after_vul.sum())},
        {"metric": "non_vulnerable_with_after_graph", "value": int(after_non.sum())},
        {"metric": "non_vulnerable_after_graph_percentage", "value": 100.0 * float(after_non.mean()) if len(non_vulnerable) else 0.0},
        {"metric": "source_with_matching_graph", "value": int(matching.sum())},
        {"metric": "source_with_matching_graph_percentage", "value": 100.0 * float(matching.mean()) if len(records) else 0.0},
        {"metric": "author_reported_graph_success_percentage", "value": AUTHOR_RELEASE["graph_success_percentage"]},
    ])
    labeled = vulnerable[vulnerable["cwe_list"].map(bool)].copy()
    labeled["has_before_graph"] = before.reindex(labeled.index).fillna(False).to_numpy()
    exploded = labeled.explode("cwe_list")
    if exploded.empty:
        by_cwe = pd.DataFrame(columns=["cwe", "sample_count", "with_graph", "missing_graph", "missing_percentage"])
    else:
        counts = exploded.groupby("cwe_list")["sample_id"].nunique().rename("sample_count")
        with_graph = exploded[exploded["has_before_graph"]].groupby("cwe_list")["sample_id"].nunique().rename("with_graph")
        by_cwe = pd.concat([counts, with_graph], axis=1).fillna(0).reset_index().rename(columns={"cwe_list": "cwe"})
        by_cwe["with_graph"] = by_cwe["with_graph"].astype(int)
        by_cwe["missing_graph"] = by_cwe["sample_count"] - by_cwe["with_graph"]
        by_cwe["missing_percentage"] = by_cwe["missing_graph"].div(by_cwe["sample_count"]).mul(100)
        by_cwe = by_cwe.sort_values(["sample_count", "cwe"], ascending=[False, True], ignore_index=True)
    return {"graph_path_summary": summary, "graph_path_by_cwe": by_cwe}


def _repository_from_commit_url(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    parsed = urlparse(value)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        return None
    return f"{parsed.netloc}/{parts[0]}/{parts[1]}".lower()


def _project_support(distribution: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for minimum_projects in PROJECT_SUPPORT_LEVELS:
        eligible = distribution[distribution["project_count"] >= minimum_projects]
        rows.append({
            "minimum_projects_per_cwe": minimum_projects,
            "number_of_cwe": len(eligible),
            "cwe_with_at_least_20_samples": int((eligible["sample_count"] >= 20).sum()),
            "cwe_with_at_least_50_samples": int((eligible["sample_count"] >= 50).sum()),
            "cwe_with_at_least_100_samples": int((eligible["sample_count"] >= 100).sum()),
            "cwe_with_at_least_200_samples": int((eligible["sample_count"] >= 200).sum()),
        })
    return pd.DataFrame(rows)


def _author_comparison(summary: pd.DataFrame) -> pd.DataFrame:
    measured = summary.set_index("metric")["value"]
    rows = []
    for metric in AUTHOR_COUNT_FIELDS:
        actual = int(measured[metric]) if metric in measured.index else None
        author = int(AUTHOR_RELEASE[metric])
        rows.append({
            "metric": metric,
            "author_reported": author,
            "measured": actual,
            "difference": None if actual is None else actual - author,
        })
    return pd.DataFrame(rows)

"""Chốt tập CWE task 2.2 và ghi manifest split task 2.3.

Script đọc DiverseVul local, không lấy CWE đầu tiên và không nhân bản
multi-CWE. Hai protocol dùng cùng tập sample và cùng group chống leakage.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.deduplication import source_hashes  # noqa: E402
from src.data.diversevul_audit import (  # noqa: E402
    canonicalize,
    read_optional_metadata,
    resolve_fields,
    _project_tables,
)
from src.data.loader import load_dataset  # noqa: E402

MIN_SAMPLE_COUNT = 100
MIN_PROJECT_COUNT = 10
MAX_LARGEST_PROJECT_SHARE = 50.0
MIN_ELIGIBLE_PER_CLASS = 80
MIN_PER_SPLIT = 5
SPLIT_FRACTIONS = {"train": 0.80, "validation": 0.10, "test": 0.10}
SPLIT_NAMES = ("train", "validation", "test")
CACHE_COLUMNS = (
    "sample_id",
    "is_vulnerable",
    "cwe_labels",
    "project",
    "commit",
    "cve",
    "norm_hash",
)


class UnionFind:
    """Gom sample hoặc project thành một đơn vị split."""

    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def add(self, item: str) -> None:
        self.parent.setdefault(item, item)

    def find(self, item: str) -> str:
        self.add(item)
        root = item
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[item] != root:
            item, self.parent[item] = self.parent[item], root
        return root

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def parse_cve_values(raw_value: object) -> list[str]:
    """Lấy mọi mã CVE-YYYY-N trong một ô metadata, bỏ giá trị trống."""
    import re

    if raw_value is None or (isinstance(raw_value, float) and pd.isna(raw_value)):
        return []
    if isinstance(raw_value, (list, tuple, set)):
        found: list[str] = []
        for item in raw_value:
            for cve in parse_cve_values(item):
                if cve not in found:
                    found.append(cve)
        return found
    pattern = re.compile(r"CVE-\d{4}-\d+", re.IGNORECASE)
    found = []
    for match in pattern.findall(str(raw_value)):
        cve = match.upper()
        if cve not in found:
            found.append(cve)
    return found


def load_commit_cves(raw_dir: Path) -> dict[str, list[str]]:
    """Nối CVE vào commit khi metadata có mã. Commit không có CVE được bỏ qua."""
    metadata, metadata_path = read_optional_metadata(raw_dir)
    if metadata is None:
        raise FileNotFoundError(f"Không thấy metadata DiverseVul trong {raw_dir}.")
    commit_column = "commit_id" if "commit_id" in metadata.columns else None
    cve_column = "CVE" if "CVE" in metadata.columns else None
    if commit_column is None or cve_column is None:
        raise KeyError(
            f"Metadata {metadata_path} thiếu commit_id hoặc CVE. Cột: {list(metadata.columns)}"
        )
    grouped: dict[str, list[str]] = defaultdict(list)
    for commit, raw_cve in zip(metadata[commit_column], metadata[cve_column], strict=True):
        if commit is None or (isinstance(commit, float) and pd.isna(commit)):
            continue
        key = str(commit).strip()
        if not key:
            continue
        for cve in parse_cve_values(raw_cve):
            if cve not in grouped[key]:
                grouped[key].append(cve)
    return dict(grouped)


def build_cache(raw_dir: Path, cache_path: Path) -> None:
    """Ghi bảng nhẹ, bỏ source sau khi đã hash."""
    loaded = load_dataset("diversevul", raw_dir)
    fields = resolve_fields(loaded.frame, {
        "code_field": "func",
        "label_field": "target",
        "cwe_field": "cwe",
        "project_field": "project",
        "commit_field": "commit_id",
        "hash_field": "hash",
    })
    records = canonicalize(loaded.frame, fields)
    hashes = source_hashes(records["source_code"], normalized=True)
    cves_by_commit = load_commit_cves(raw_dir)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CACHE_COLUMNS)
        writer.writeheader()
        for sample_id, is_vulnerable, labels, project, commit, digest in zip(
            records["sample_id"],
            records["is_vulnerable"],
            records["cwe_list"],
            records["project"],
            records["commit"],
            hashes,
            strict=True,
        ):
            commit_text = "" if commit is None or (isinstance(commit, float) and pd.isna(commit)) else str(commit).strip()
            project_text = "" if project is None or (isinstance(project, float) and pd.isna(project)) else str(project).strip()
            if is_vulnerable is True:
                vulnerable_text = "1"
            elif is_vulnerable is False:
                vulnerable_text = "0"
            else:
                vulnerable_text = ""
            writer.writerow({
                "sample_id": sample_id,
                "is_vulnerable": vulnerable_text,
                "cwe_labels": "|".join(labels),
                "project": project_text,
                "commit": commit_text,
                "cve": "|".join(cves_by_commit.get(commit_text, [])),
                "norm_hash": digest or "",
            })
    del loaded


def read_cache(cache_path: Path) -> pd.DataFrame:
    frame = pd.read_csv(cache_path, dtype=str, keep_default_na=False)
    frame["cwe_list"] = frame["cwe_labels"].map(lambda text: [part for part in text.split("|") if part])
    frame["cwe_key"] = frame["cwe_list"].map(lambda labels: "|".join(sorted(labels)))
    frame["is_vulnerable_bool"] = frame["is_vulnerable"].map({"1": True, "0": False}).astype("boolean")
    frame["project_value"] = frame["project"].map(lambda text: text if text else pd.NA)
    return frame


def published_distribution_matches(measured: pd.DataFrame) -> None:
    """Dừng nếu bảng CWE vừa tính lệch khỏi EDA đã công bố."""
    published_path = ROOT / "reports" / "dataset" / "tables" / "cwe_project_distribution.csv"
    published = pd.read_csv(published_path)
    merged = measured.merge(published, on="cwe", suffixes=("_measured", "_published"))
    if len(merged) != len(published) or len(merged) != len(measured):
        raise SystemExit(
            f"Số CWE không khớp EDA: đo được {len(measured)}, công bố {len(published)}, giao {len(merged)}."
        )
    sample_gap = (merged["sample_count_measured"] - merged["sample_count_published"]).abs().max()
    project_gap = (merged["project_count_measured"] - merged["project_count_published"]).abs().max()
    share_gap = (merged["largest_project_share_measured"] - merged["largest_project_share_published"]).abs().max()
    if sample_gap or project_gap or share_gap > 1e-6:
        raise SystemExit(
            "Bảng CWE lệch khỏi reports/dataset/tables/cwe_project_distribution.csv: "
            f"sample={sample_gap}, project={project_gap}, share={share_gap}."
        )


def conflict_hashes(frame: pd.DataFrame) -> set[str]:
    """Hash normalized có nhãn vulnerable hoặc tập CWE không thống nhất."""
    hashed = frame[frame["norm_hash"] != ""]
    grouped = hashed.groupby("norm_hash", sort=False)
    vulnerable_conflict = grouped["is_vulnerable"].nunique()
    cwe_conflict = grouped["cwe_key"].nunique()
    keys = set(vulnerable_conflict[vulnerable_conflict > 1].index)
    keys.update(cwe_conflict[cwe_conflict > 1].index)
    return keys


def select_candidates(distribution: pd.DataFrame, eligible_counts: dict[str, int]) -> pd.DataFrame:
    """Áp tiêu chí sample, project, concentration và số mẫu single-label còn lại."""
    table = distribution.copy()
    table["single_label_eligible"] = table["cwe"].map(lambda cwe: eligible_counts.get(cwe, 0))
    reasons = []
    for row in table.itertuples(index=False):
        failed = []
        if row.sample_count < MIN_SAMPLE_COUNT:
            failed.append(f"sample_count<{MIN_SAMPLE_COUNT}")
        if row.project_count < MIN_PROJECT_COUNT:
            failed.append(f"project_count<{MIN_PROJECT_COUNT}")
        if row.largest_project_share > MAX_LARGEST_PROJECT_SHARE:
            failed.append(f"largest_project_share>{MAX_LARGEST_PROJECT_SHARE}")
        if not failed and row.single_label_eligible < MIN_ELIGIBLE_PER_CLASS:
            failed.append(f"single_label_eligible<{MIN_ELIGIBLE_PER_CLASS}")
        reasons.append("" if not failed else "; ".join(failed))
    table["exclude_reason"] = reasons
    table["selected"] = table["exclude_reason"].eq("")
    return table.sort_values(["selected", "sample_count", "cwe"], ascending=[False, False, True], ignore_index=True)


def link_groups(eligible: pd.DataFrame) -> tuple[pd.Series, dict[str, int]]:
    """Gom duplicate, commit và CVE. Ô trống không được gom thành một nhóm."""
    groups = UnionFind()
    for sample_id in eligible["sample_id"].tolist():
        groups.add(sample_id)
    hash_groups = connect_on(groups, eligible[eligible["norm_hash"] != ""], "norm_hash")
    commit_groups = connect_on(groups, eligible[eligible["commit"] != ""], "commit")
    cve_rows = []
    for sample_id, cve_text in zip(eligible["sample_id"], eligible["cve"], strict=True):
        for cve in [part for part in str(cve_text).split("|") if part]:
            cve_rows.append((cve, sample_id))
    cve_groups = 0
    if cve_rows:
        cve_frame = pd.DataFrame(cve_rows, columns=["cve_id", "sample_id"])
        cve_groups = connect_on(groups, cve_frame, "cve_id")
    roots = eligible["sample_id"].map(groups.find)
    return roots, {
        "normalized_duplicate_groups": hash_groups,
        "commit_groups": commit_groups,
        "cve_groups": cve_groups,
    }


def connect_on(groups: UnionFind, frame: pd.DataFrame, column: str) -> int:
    linked = 0
    for _, members in frame.groupby(column, sort=False)["sample_id"]:
        member_ids = members.tolist()
        if len(member_ids) < 2:
            continue
        linked += 1
        head = member_ids[0]
        for sample_id in member_ids[1:]:
            groups.union(head, sample_id)
    return linked


def assign_units(units: list[dict[str, object]]) -> dict[str, str]:
    """Gán từng đơn vị vào một split.

    Class hiếm được chia trước. Mỗi đơn vị đi vào split đang thấp nhất so với
    chỉ tiêu của class đang xét, và tránh split đã vượt ngân sách mẫu.
    """
    class_total: dict[str, int] = defaultdict(int)
    for unit in units:
        for label, count in unit["counts"].items():
            class_total[label] += int(count)
    total_samples = sum(int(unit["n"]) for unit in units)
    assigned_n = {name: 0 for name in SPLIT_NAMES}
    assigned_c = {name: defaultdict(int) for name in SPLIT_NAMES}
    assignment: dict[str, str] = {}

    def place(unit: dict[str, object], focus_label: str | None) -> None:
        counts: dict[str, int] = unit["counts"]
        unit_n = int(unit["n"])
        best_name = ""
        best_key: tuple[float, float, float, str] | None = None
        for name in SPLIT_NAMES:
            sample_target = SPLIT_FRACTIONS[name] * total_samples
            sample_fill = (assigned_n[name] + unit_n) / sample_target
            if focus_label is None:
                fills = [
                    (assigned_c[name][label] + count) / (SPLIT_FRACTIONS[name] * class_total[label])
                    for label, count in counts.items()
                ]
                focus_fill = max(fills) if fills else sample_fill
            else:
                focus_fill = (
                    assigned_c[name][focus_label] + counts.get(focus_label, 0)
                ) / (SPLIT_FRACTIONS[name] * class_total[focus_label])
            key = (max(0.0, sample_fill - 1.15), focus_fill, sample_fill, name)
            if best_key is None or key < best_key:
                best_key = key
                best_name = name
        assignment[str(unit["id"])] = best_name
        assigned_n[best_name] += unit_n
        for label, count in counts.items():
            assigned_c[best_name][label] += int(count)

    remaining = {str(unit["id"]): unit for unit in units}
    for label in sorted(class_total, key=lambda item: (class_total[item], item)):
        pool = [unit for unit in remaining.values() if label in unit["counts"]]
        pool.sort(key=lambda unit: (-int(unit["counts"][label]), -int(unit["n"]), str(unit["id"])))
        for unit in pool:
            place(unit, label)
            del remaining[str(unit["id"])]
    leftovers = sorted(remaining.values(), key=lambda unit: (-int(unit["n"]), str(unit["id"])))
    for unit in leftovers:
        place(unit, None)
    return repair_missing_classes(units, assignment)


def repair_missing_classes(units: list[dict[str, object]], assignment: dict[str, str]) -> dict[str, str]:
    """Chuyển đơn vị nhỏ nhất còn dư sang split đang thiếu một CWE."""
    by_id = {str(unit["id"]): unit for unit in units}
    labels = sorted({label for unit in units for label in unit["counts"]})

    def snapshot() -> dict[str, tuple[int, dict[str, int]]]:
        result = {name: (0, defaultdict(int)) for name in SPLIT_NAMES}
        for unit_id, split_name in assignment.items():
            unit = by_id[unit_id]
            count_n, count_c = result[split_name]
            count_n += int(unit["n"])
            for label, count in unit["counts"].items():
                count_c[label] += int(count)
            result[split_name] = (count_n, count_c)
        return result

    for _ in range(len(labels) * len(SPLIT_NAMES)):
        current = snapshot()
        moved = False
        for label in labels:
            for split_name in SPLIT_NAMES:
                if current[split_name][1][label] >= MIN_PER_SPLIT:
                    continue
                candidates = []
                for unit_id, donor in assignment.items():
                    if donor == split_name or label not in by_id[unit_id]["counts"]:
                        continue
                    donor_counts = current[donor][1]
                    unit = by_id[unit_id]
                    safe = True
                    for other, count in unit["counts"].items():
                        left = donor_counts[other] - int(count)
                        if left <= 0 or (donor_counts[other] >= MIN_PER_SPLIT and left < MIN_PER_SPLIT):
                            safe = False
                            break
                    if safe:
                        candidates.append(unit)
                if not candidates:
                    continue
                chosen = min(candidates, key=lambda unit: (int(unit["n"]), str(unit["id"])))
                assignment[str(chosen["id"])] = split_name
                moved = True
                current = snapshot()
        if not moved:
            break
    return assignment


def units_from_groups(eligible: pd.DataFrame, group_column: str) -> list[dict[str, object]]:
    units = []
    for group_id, members in eligible.groupby(group_column, sort=False):
        counts = members["cwe"].value_counts().to_dict()
        units.append({"id": str(group_id), "n": int(len(members)), "counts": counts})
    return units


def coverage_table(eligible: pd.DataFrame, split_column: str) -> list[dict[str, object]]:
    rows = []
    for cwe, members in eligible.groupby("cwe", sort=True):
        counts = members[split_column].value_counts().to_dict()
        row: dict[str, object] = {"cwe": cwe, "total": int(len(members))}
        for name in SPLIT_NAMES:
            row[name] = int(counts.get(name, 0))
        rows.append(row)
    return rows


def leakage_report(eligible: pd.DataFrame, split_column: str, project_disjoint: bool) -> dict[str, int]:
    def overlapping(column: str) -> int:
        occupied: dict[str, set[str]] = defaultdict(set)
        for key, split_name in zip(eligible[column], eligible[split_column], strict=True):
            if key == "" or pd.isna(key):
                continue
            occupied[str(key)].add(str(split_name))
        return sum(len(splits) > 1 for splits in occupied.values())

    report = {
        "samples": int(len(eligible)),
        "duplicate_groups_crossing_splits": overlapping("norm_hash") if "norm_hash" in eligible else 0,
        "commit_groups_crossing_splits": overlapping("commit"),
        "group_ids_crossing_splits": overlapping("group_id"),
        "projects_crossing_splits": overlapping("project"),
    }
    if project_disjoint and report["projects_crossing_splits"]:
        raise SystemExit(f"{split_column} để project xuất hiện ở nhiều split.")
    if report["group_ids_crossing_splits"] or report["commit_groups_crossing_splits"]:
        raise SystemExit(f"{split_column} cắt group hoặc commit qua nhiều split: {report}")
    hashed = eligible[eligible["norm_hash"] != ""]
    if leakage_report_hashes(hashed, split_column):
        raise SystemExit(f"{split_column} cắt duplicate normalized qua nhiều split.")
    return report


def leakage_report_hashes(hashed: pd.DataFrame, split_column: str) -> int:
    occupied: dict[str, set[str]] = defaultdict(set)
    for digest, split_name in zip(hashed["norm_hash"], hashed[split_column], strict=True):
        occupied[digest].add(split_name)
    return sum(len(splits) > 1 for splits in occupied.values())


def write_id_lists(eligible: pd.DataFrame, split_column: str, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in SPLIT_NAMES:
        ids = eligible.loc[eligible[split_column] == name, "sample_id"].map(sample_sort_key).sort_values()
        ordered = eligible.loc[ids.index, "sample_id"]
        path = output_dir / f"{name}.txt"
        path.write_text("\n".join(ordered.tolist()) + "\n", encoding="utf-8")


def sample_sort_key(sample_id: str) -> int:
    return int(str(sample_id).split("-", 1)[1])


def main() -> None:
    parser = argparse.ArgumentParser(description="Tạo manifest DiverseVul cho task 2.2 và 2.3.")
    parser.add_argument("--reuse-cache", action="store_true")
    args = parser.parse_args()
    raw_dir = ROOT / "data" / "raw" / "diversevul"
    cache_path = ROOT / "data" / "interim" / "diversevul_split_rows.csv"
    if not args.reuse_cache or not cache_path.is_file():
        print("Building cache from DiverseVul jsonl...", flush=True)
        build_cache(raw_dir, cache_path)
    frame = read_cache(cache_path)
    audit_records = pd.DataFrame({
        "sample_id": frame["sample_id"],
        "project": frame["project_value"],
        "cwe_list": frame["cwe_list"],
        "is_vulnerable": frame["is_vulnerable_bool"],
    })
    vulnerable = audit_records[audit_records["is_vulnerable"].fillna(False)].copy()
    _, distribution, _ = _project_tables(audit_records, vulnerable)
    published_distribution_matches(distribution)

    conflicts = conflict_hashes(frame)
    duplicate_check = frame[frame["norm_hash"] != ""].groupby("norm_hash")
    vuln_conflict_groups = int((duplicate_check["is_vulnerable"].nunique() > 1).sum())
    cwe_conflict_groups = int((duplicate_check["cwe_key"].nunique() > 1).sum())
    if vuln_conflict_groups != 459 or cwe_conflict_groups != 299:
        raise SystemExit(
            "Conflict không khớp EDA: "
            f"vulnerable={vuln_conflict_groups} (kỳ vọng 459), "
            f"cwe={cwe_conflict_groups} (kỳ vọng 299)."
        )

    single = frame[(frame["is_vulnerable"] == "1") & (frame["cwe_list"].map(len) == 1)].copy()
    single["cwe"] = single["cwe_list"].map(lambda labels: labels[0])
    single = single[~single["norm_hash"].isin(conflicts)].copy()
    eligible_counts = single["cwe"].value_counts().to_dict()
    decisions = select_candidates(distribution, eligible_counts)
    selected = set(decisions.loc[decisions["selected"], "cwe"])
    eligible = single[single["cwe"].isin(selected)].copy()
    group_ids, group_stats = link_groups(eligible)
    eligible["group_id"] = group_ids.map(lambda root: f"group-{root}")

    eligible["project_key"] = [
        project if project else f"missing-project:{sample_id}"
        for project, sample_id in zip(eligible["project"], eligible["sample_id"], strict=True)
    ]
    project_union = UnionFind()
    for project_key in eligible["project_key"].tolist():
        project_union.add(project_key)
    for _, members in eligible.groupby("group_id", sort=False):
        keys = members["project_key"].tolist()
        for other in keys[1:]:
            project_union.union(keys[0], other)
    eligible["super_project"] = eligible["project_key"].map(lambda key: f"super-{project_union.find(key)}")
    project_assignment = assign_units(units_from_groups(eligible, "super_project"))
    seen_assignment = assign_units(units_from_groups(eligible, "group_id"))
    eligible["project_wise_split"] = eligible["super_project"].map(project_assignment)
    eligible["seen_project_split"] = eligible["group_id"].map(seen_assignment)

    project_leakage = leakage_report(eligible, "project_wise_split", project_disjoint=True)
    seen_leakage = leakage_report(eligible, "seen_project_split", project_disjoint=False)
    for column in ("project_wise_split", "seen_project_split"):
        missing = [row["cwe"] for row in coverage_table(eligible, column) if any(row[name] == 0 for name in SPLIT_NAMES)]
        if missing:
            raise SystemExit(f"{column} thiếu class ở một split: {missing}")

    split_root = ROOT / "data" / "splits"
    write_id_lists(eligible, "project_wise_split", split_root / "diversevul_project_wise")
    write_id_lists(eligible, "seen_project_split", split_root / "diversevul_seen_project")
    manifest = eligible.sort_values("sample_id", key=lambda series: series.map(sample_sort_key))
    manifest_path = split_root / "diversevul_experiment_manifest.csv"
    manifest[[
        "sample_id", "cwe", "project", "commit", "cve", "group_id", "project_wise_split", "seen_project_split",
    ]].to_csv(manifest_path, index=False)

    labeled = int(vulnerable["cwe_list"].map(bool).sum())
    report = {
        "criteria": {
            "min_sample_count": MIN_SAMPLE_COUNT,
            "min_project_count": MIN_PROJECT_COUNT,
            "max_largest_project_share": MAX_LARGEST_PROJECT_SHARE,
            "min_single_label_after_conflict_removal": MIN_ELIGIBLE_PER_CLASS,
            "min_samples_per_class_per_split": MIN_PER_SPLIT,
            "split_fractions": SPLIT_FRACTIONS,
            "label_policy": "single_label_subset",
        },
        "funnel": {
            "records": int(len(frame)),
            "vulnerable": int((frame["is_vulnerable"] == "1").sum()),
            "labeled_vulnerable": labeled,
            "missing_cwe": int(((frame["is_vulnerable"] == "1") & frame["cwe_list"].map(lambda labels: not labels)).sum()),
            "exactly_one_cwe": int(((frame["is_vulnerable"] == "1") & (frame["cwe_list"].map(len) == 1)).sum()),
            "two_or_more_cwe": int(((frame["is_vulnerable"] == "1") & (frame["cwe_list"].map(len) >= 2)).sum()),
            "conflict_hashes": len(conflicts),
            "vulnerable_label_conflict_groups": vuln_conflict_groups,
            "cwe_conflict_groups": cwe_conflict_groups,
            "eligible": int(len(eligible)),
        },
        "group_stats": group_stats,
        "candidates": decisions.loc[decisions["selected"], [
            "cwe", "sample_count", "project_count", "largest_project_share", "single_label_eligible",
        ]].to_dict(orient="records"),
        "excluded_at_least_100_samples": decisions.loc[
            (~decisions["selected"]) & (decisions["sample_count"] >= MIN_SAMPLE_COUNT),
            ["cwe", "sample_count", "project_count", "largest_project_share", "single_label_eligible", "exclude_reason"],
        ].to_dict(orient="records"),
        "project_wise": {
            "leakage": project_leakage,
            "split_counts": eligible["project_wise_split"].value_counts().to_dict(),
            "projects": {name: int(eligible.loc[eligible["project_wise_split"] == name, "project"].nunique()) for name in SPLIT_NAMES},
            "super_projects": int(eligible["super_project"].nunique()),
            "projects_total": int(eligible["project"].replace("", pd.NA).nunique()),
            "coverage": coverage_table(eligible, "project_wise_split"),
        },
        "seen_project": {
            "leakage": seen_leakage,
            "split_counts": eligible["seen_project_split"].value_counts().to_dict(),
            "projects_crossing_splits": seen_leakage["projects_crossing_splits"],
            "coverage": coverage_table(eligible, "seen_project_split"),
        },
    }
    report_path = split_root / "diversevul_split_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"eligible": report["funnel"]["eligible"], "candidates": len(report["candidates"]), "report": str(report_path)}, indent=2))


if __name__ == "__main__":
    main()

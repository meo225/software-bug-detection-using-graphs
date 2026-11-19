"""Read-only function audit; never changes source data, splits or legacy helpers."""
from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

from src.data.preprocessing import normalize_whitespace

PROTOCOLS = ("project_wise", "seen_project")
SPLITS = ("train", "validation", "test")
METHODS = ("raw", "legacy", "primevul")


def normalize_primevul(source: str) -> str:
    """Remove only ASCII space, tab, LF and CR, including inside literals."""
    return source.translate(str.maketrans("", "", " \t\n\r"))


def fingerprint(path: Path) -> dict:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def validate_inputs(manifest: list[dict], failed: list[dict], expected: tuple[int, int, int] = (9077, 1278, 7799)) -> tuple[list[dict], dict]:
    for name, rows in (("manifest", manifest), ("failed", failed)):
        ids = [r.get("sample_id", "") for r in rows]
        if len(set(ids)) != len(ids) or any(not re.fullmatch(r"row-(0|[1-9][0-9]*)", i) for i in ids):
            raise ValueError(f"{name}: duplicate or invalid sample_id")
        for r in rows:
            if any(r.get(p + "_split") not in SPLITS for p in PROTOCOLS):
                raise ValueError(f"{name}: invalid split for {r['sample_id']}")
    index = {r["sample_id"]: r for r in manifest}
    for r in failed:
        if r["sample_id"] not in index:
            raise ValueError("failed ID outside manifest")
        if any(r.get(k) != index[r["sample_id"]].get(k) for k in ("project", "cwe", "project_wise_split", "seen_project_split")):
            raise ValueError(f"failed metadata mismatch: {r['sample_id']}")
    excluded = {r["sample_id"] for r in failed}
    valid = [r for r in manifest if r["sample_id"] not in excluded]
    if (len(manifest), len(failed), len(valid)) != expected:
        raise ValueError(f"unexpected cohort counts: {(len(manifest), len(failed), len(valid))}")
    counts = {p: dict(Counter(r[p + "_split"] for r in valid)) for p in PROTOCOLS}
    if expected == (9077, 1278, 7799) and counts != {
        "project_wise": {"train": 6101, "validation": 762, "test": 936},
        "seen_project": {"train": 6272, "validation": 764, "test": 763},
    }:
        raise ValueError("unexpected valid split counts")
    return valid, {"manifest": len(manifest), "failed": len(failed), "valid": len(valid),
                   "missing_failed_ids": 0, "metadata_mismatches": 0, "split_counts": counts}


def join_sources(path: Path, manifest: list[dict], expected_records: int) -> tuple[list[dict], dict]:
    """Match the legacy loader: row-N indexes nonblank JSON objects from zero."""
    wanted = {int(r["sample_id"][4:]): r for r in manifest}
    joined = []
    count = blank = 0
    with path.open(encoding="utf-8") as handle:
        for physical_line, line in enumerate(handle, 1):
            if not line.strip():
                blank += 1
                continue
            obj = json.loads(line)
            if not isinstance(obj, dict):
                raise ValueError(f"JSON object required at line {physical_line}")
            record_index = count
            count += 1
            if record_index not in wanted:
                continue
            row = wanted[record_index]
            if (obj.get("project") != row.get("project") or obj.get("commit_id") != row.get("commit")
                    or obj.get("target") != 1 or obj.get("cwe") != [row.get("cwe")]):
                raise ValueError(f"raw metadata mismatch: {row['sample_id']} line {physical_line}")
            source = obj.get("func")
            if not isinstance(source, str) or not normalize_primevul(source).strip():
                raise ValueError(f"invalid source: {row['sample_id']}")
            source.encode("utf-8")  # strict: never silently replace invalid characters
            joined.append({**row, "source": source, "record_index": record_index, "physical_line": physical_line})
    if count != expected_records or len(joined) != len(manifest):
        raise ValueError(f"raw join incomplete: records={count}, joined={len(joined)}")
    return sorted(joined, key=lambda r: r["record_index"]), {
        "raw_records": count, "blank_lines": blank, "joined": len(joined), "missing_source_ids": 0}


def hash_samples(rows: list[dict], failed_ids: set[str]) -> list[dict]:
    result = []
    for r in rows:
        item = {k: v for k, v in r.items() if k != "source"}
        item["included"] = r["sample_id"] not in failed_ids
        source = r["source"]
        for method, text in (("raw", source), ("legacy", normalize_whitespace(source)), ("primevul", normalize_primevul(source))):
            # All methods use strict UTF-8; only source normalization differs.
            item[method + "_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
        item["primevul_md5"] = hashlib.md5(normalize_primevul(source).encode("utf-8"), usedforsecurity=False).hexdigest()
        result.append(item)
    return result


def analyze(rows: list[dict], method: str, cohort: str) -> dict[str, list[dict]]:
    groups = defaultdict(list)
    normalize = {"raw": lambda s: s, "legacy": normalize_whitespace, "primevul": normalize_primevul}[method]
    for r in rows:
        text = normalize(r["source"])
        groups[hashlib.sha256(text.encode("utf-8")).hexdigest()].append(r)
    duplicates = {h: rs for h, rs in groups.items() if len(rs) > 1}
    summaries, cross, members, details, review = [], [], [], [], []
    for h, rs in sorted(duplicates.items()):
        if len({normalize(r["source"]) for r in rs}) != 1:
            raise ValueError("SHA256 collision: unequal normalized sources")
        details.append(dict(cohort=cohort, method=method, group_hash=h, size=len(rs), pairs=len(rs)*(len(rs)-1)//2,
                            legacy_subgroups=len({normalize_whitespace(r['source']) for r in rs}),
                            cwe_conflict=len({r['cwe'] for r in rs}) > 1))
        for r in rs:
            members.append(dict(cohort=cohort, method=method, group_hash=h, sample_id=r['sample_id'],
                                cwe=r['cwe'], **{p+'_split': r[p+'_split'] for p in PROTOCOLS}))
    for p in PROTOCOLS:
        column = p + "_split"
        for split in ("all", *SPLITS):
            sizes = [len(rs) if split == 'all' else sum(r[column] == split for r in rs) for rs in duplicates.values()]
            sizes = [n for n in sizes if n > 1]
            summaries.append(dict(cohort=cohort, method=method, protocol=p, split=split,
                                  duplicate_groups=len(sizes), affected_samples=sum(sizes), excess_samples=sum(n-1 for n in sizes),
                                  duplicate_pairs=sum(n*(n-1)//2 for n in sizes)))
        crossing = [rs for rs in duplicates.values() if len({r[column] for r in rs}) > 1]
        total_cross_pairs = 0
        for a, b in combinations(SPLITS, 2):
            matched = [rs for rs in crossing if any(r[column] == a for r in rs) and any(r[column] == b for r in rs)]
            pairs = sum(sum(r[column] == a for r in rs)*sum(r[column] == b for r in rs) for rs in matched)
            total_cross_pairs += pairs
            ids = {r['sample_id'] for rs in matched for r in rs if r[column] in (a,b)}
            held = {r['sample_id'] for rs in matched for r in rs if r[column] == b}
            denominator = sum(r[column] == b for r in rows)
            cross.append(dict(cohort=cohort, method=method, protocol=p, split_pair=a+'--'+b,
                              duplicate_groups=len(matched), affected_samples=len(ids), duplicate_pairs=pairs,
                              held_out_samples=len(held), held_out_total=denominator,
                              held_out_percentage=100*len(held)/denominator if denominator else 0))
        cross.append(dict(cohort=cohort, method=method, protocol=p, split_pair='all_cross_split',
                          duplicate_groups=len(crossing), affected_samples=len({r['sample_id'] for rs in crossing for r in rs}),
                          duplicate_pairs=total_cross_pairs, held_out_samples='', held_out_total='', held_out_percentage=''))
        within = sum(sum(r[column] == s for r in rs)*(sum(r[column] == s for r in rs)-1)//2 for rs in duplicates.values() for s in SPLITS)
        assert within + total_cross_pairs == sum(len(rs)*(len(rs)-1)//2 for rs in duplicates.values())
        if method == 'primevul' and cohort == 'valid':
            for rs in crossing:
                h = hashlib.sha256(normalize(rs[0]['source']).encode('utf-8')).hexdigest()
                review.append(dict(protocol=p, group_hash=h, sample_ids='|'.join(r['sample_id'] for r in rs),
                                   classification='pending', reason='Review original literals, tokens, comments and macros locally'))
    return dict(duplicate_summary=summaries, cross_split_leakage=cross, duplicate_members=members,
                duplicate_groups=details, cross_split_review=review)


TABLE_COLUMNS = {
    'duplicate_summary': 'cohort method protocol split duplicate_groups affected_samples excess_samples duplicate_pairs',
    'cross_split_leakage': 'cohort method protocol split_pair duplicate_groups affected_samples duplicate_pairs held_out_samples held_out_total held_out_percentage',
    'duplicate_groups': 'cohort method group_hash size pairs legacy_subgroups cwe_conflict',
    'duplicate_members': 'cohort method group_hash sample_id cwe project_wise_split seen_project_split',
    'cross_split_review': 'protocol group_hash sample_ids classification reason',
}


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

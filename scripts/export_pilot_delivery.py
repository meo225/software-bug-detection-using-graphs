"""Extraction-free Task 3.2 delivery. No parsing, extraction or source repair.

The CLI reconciles retained receipts; it cannot select a new cohort or execute
Joern. Publication is a no-replace directory rename on the destination volume.
"""
from __future__ import annotations

import argparse
import copy
import csv
import ctypes
import hashlib
import io
import json
import os
import subprocess
import sys
import uuid
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_graph_extraction as driver  # noqa: E402
from src.graph import joern  # noqa: E402

IDS = tuple("row-" + n for n in (
    "17543 13809 12897 4824 8688 12023 8932 16198 567 13727 15771 5087 "
    "15766 4243 5662 12672 12144 832 8975 18735 4225 16083 4718 3732 "
    "16513 145 6038 1601 11455 11987").split())
FAILED = frozenset({"row-832", "row-6038", "row-1601"})
UNSUPPORTED = frozenset({"row-8932", "row-16198"})
QUERY_SHA256 = "5130aa0cef583e99e6ef7f64f13e51473a05f8ebc1a454addb4139f741a22bb5"
HISTORICAL_SHA256 = "52c9f5f5a673ff854a0f54982ab1e3a0acf332a9cde9b4f64775e63fc98f757c"
FINAL_SHA256 = "c26d2e9b151b16706b05453b65345cdf9e72d51bcc273d880114f26f54dfb55b"
HISTORICAL_REPORT = "reports/graph/3_2_joern_pilot_historical.md"
FINAL_REPORT = "reports/graph/3_2_joern_pilot.md"
LEGACY_FINAL_REPORT = "reports/graph/3_2_joern_pilot_final_v2.md"
FIELDS = ("source_reference", "record_kind")
KINDS = ("graph_a", "graph_b")
UNSUPPORTED_REASON = (
    "Original source is a switch fragment without a unique explicit function "
    "definition; extraction was not attempted under the exact-function contract.")
COLUMNS = (
    "manifest_order", "sample_id", "dataset_index", "cwe", "source_reference",
    "source_sha256", "project_wise_split", "seen_project_split", "record_kind",
    "cohort_status", "status", "graph_type", "num_nodes", "num_edges", "ddg_status",
    "error_message", "json_file", "json_sha256", "json_bytes",
    "original_artifact_reference", "original_artifact_sha256", "attempt_references")


class DeliveryError(ValueError):
    """A mandatory delivery check failed; no automatic retry is permitted."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DeliveryError(message)


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read(path: Path) -> Any:
    def invalid(value):
        raise DeliveryError(f"Non-finite JSON value: {value}")
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs,
                      parse_constant=invalid)


def encode(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def equal_typed(a: Any, b: Any) -> bool:
    """Unlike Python ==, do not equate True, 1 and 1.0; retain object key order."""
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return list(a) == list(b) and all(equal_typed(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(equal_typed(x, y) for x, y in zip(a, b))
    return a == b


def within(root: Path, path: Path) -> Path:
    path = path.resolve()
    require(path.is_relative_to(root.resolve()), f"Path outside repository: {path}")
    return path


def reference(root: Path, path: Path) -> str:
    return within(root, path).relative_to(root.resolve()).as_posix()


def inventory(root: Path) -> dict[str, str]:
    """Hash project files and ignored evidence, excluding Git/venv internals."""
    require(root.is_dir(), f"Missing protected inventory root: {root}")
    def traversal_error(error: OSError) -> None:
        raise error
    result = {}
    for directory, dirs, files in os.walk(root, onerror=traversal_error):
        dirs[:] = sorted(d for d in dirs if d not in {".git", ".venv", "venv"})
        require(not any((Path(directory) / d).is_symlink() for d in dirs),
                f"Symlink directory in protected inventory: {directory}")
        for name in sorted(files):
            path = Path(directory) / name
            require(not path.is_symlink(), f"Symlink in protected inventory: {path}")
            result[reference(root, path)] = sha(path)
    return result


def verify_hashes(root: Path, hashes: dict[str, str]) -> None:
    for name, digest in hashes.items():
        path = within(root, root / name)
        require(path.is_file() and sha(path) == digest, f"Checksum mismatch: {name}")


def reconcile_report_paths(root: Path, *inventories: dict[str, str]) -> dict[str, str]:
    """Translate only approved full-path/hash identities; retain frozen inputs."""
    aliases = {
        (FINAL_REPORT, HISTORICAL_SHA256): HISTORICAL_REPORT,
        (LEGACY_FINAL_REPORT, FINAL_SHA256): FINAL_REPORT,
        (HISTORICAL_REPORT, HISTORICAL_SHA256): HISTORICAL_REPORT,
        (FINAL_REPORT, FINAL_SHA256): FINAL_REPORT,
    }
    report_paths = {HISTORICAL_REPORT, FINAL_REPORT, LEGACY_FINAL_REPORT}
    result = {}
    report_sources = set()
    for hashes in inventories:
        require(type(hashes) is dict, "Invalid protected inventory")
        seen = set()
        for name, digest in hashes.items():
            require(type(name) is str and type(digest) is str and len(digest) == 64 and
                    all(c in "0123456789abcdef" for c in digest), "Invalid protected checksum entry")
            source = reference(root, root / name)
            require(source not in seen, f"Duplicate protected path: {source}")
            seen.add(source)
            target = source
            if source in report_paths:
                require(source not in report_sources,
                        f"Duplicate or conflicting report source: {source}")
                report_sources.add(source)
                require((source, digest) in aliases, f"Unknown report path/checksum identity: {source}")
                target = aliases[source, digest]
                require(target not in result, f"Duplicate or conflicting report mapping: {target}")
            else:
                # Independent receipts may repeat an unchanged input, never override it.
                require(target not in result or result[target] == digest,
                        f"Conflicting protected checksum: {target}")
            result[target] = digest
    return result


def verify_protected(root: Path, baseline: dict[str, str], allowed: tuple[Path, ...]) -> None:
    """Detect unrelated new files as well as byte changes/removals."""
    verify_hashes(root, baseline)
    for name in inventory(root).keys() - baseline.keys():
        path = (root / name).resolve()
        require(any(path.is_relative_to(p.resolve()) for p in allowed),
                f"Unexpected new file outside export scope: {name}")


@dataclass(frozen=True)
class Entry:
    row: dict
    record: dict
    status: str
    publication: Path | None
    staging: Path | None
    attempts: tuple[str, ...]
    hashes: dict[str, str]


@dataclass(frozen=True)
class Plan:
    entries: tuple[Entry, ...]
    config: joern.JoernConfig
    controls: dict[str, str]


def events(directory: Path) -> list[dict]:
    return [json.loads(line, object_pairs_hook=_pairs)
            for line in (directory / "stages.jsonl").read_text(encoding="utf-8").splitlines()]


def validate_pair(a: dict, b: dict, row: dict, *, failure: bool) -> None:
    """Delivery structural checks supplement, never replace, the original gate."""
    for kind, graph in zip(KINDS, (a, b)):
        require(not any(k in graph for k in FIELDS), "Conflicting delivery metadata")
        for key, expected in {"sample_id": row["sample_id"], "cwe": row["cwe"],
                              "graph_type": kind, "project_wise_split": None,
                              "seen_project_split": None}.items():
            require(key in graph and equal_typed(graph[key], expected), f"Metadata mismatch: {key}")
        nodes, edges = graph.get("nodes"), graph.get("edges")
        require(type(nodes) is list and type(edges) is list, "Missing flat graph arrays")
        require(type(graph.get("num_nodes")) is int and graph["num_nodes"] == len(nodes), "Node count mismatch")
        require(type(graph.get("num_edges")) is int and graph["num_edges"] == len(edges), "Edge count mismatch")
        require([n.get("id") for n in nodes] == list(range(len(nodes))), "Node IDs mismatch")
        for node in nodes:
            require(set(node) == {"id", "node_type", "code_token", "line_number", "rel_line_number"}, "Node fields mismatch")
            require(type(node["id"]) is int, "Non-integer node ID")
        edge_keys = []
        for edge in edges:
            require(set(edge) == {"src", "dst", "type"} and
                    all(type(v) is int for v in edge.values()), "Invalid typed edge")
            require(edge["type"] in ({0} if kind == "graph_a" else {0, 1, 2}), "Relation type mismatch")
            require(0 <= edge["src"] < len(nodes) and 0 <= edge["dst"] < len(nodes), "Invalid endpoint")
            require(edge["src"] != edge["dst"], "Unexpected self-loop")
            edge_keys.append((edge["src"], edge["dst"], edge["type"]))
        require(len(edge_keys) == len(set(edge_keys)), "Duplicate edge")
        require(graph.get("status") in (driver.FAILURE_STATUSES if failure else driver.SUCCESS_STATUSES), "Wrong record status")
        if failure:
            require(not nodes and not edges and graph.get("ddg_status") == "NOT_COMPUTED", "Not a failure payload")
            require(type(graph.get("error_message")) is str and bool(graph["error_message"]), "Missing failure reason")
    require(equal_typed(a["nodes"], b["nodes"]), "Shared node domain mismatch")
    require({(e["src"], e["dst"], e["type"]) for e in a["edges"]} ==
            {(e["src"], e["dst"], e["type"]) for e in b["edges"] if e["type"] == 0}, "Shared AST mismatch")


def originals(root: Path, entry: Entry, config: joern.JoernConfig) -> dict[str, dict]:
    row, record = entry.row, entry.record
    sid = row["sample_id"]
    if entry.status == "UNSUPPORTED":
        try:
            driver.resolve_function_name(record["func"])
        except driver.ManifestValidationError:
            return {}
        raise DeliveryError("Unsupported source unexpectedly has a resolvable function")
    require(entry.publication is not None and entry.staging is not None, "Missing artifact mapping")
    pub, stage = within(root, entry.publication), within(root, entry.staging)
    require(bool(entry.hashes) and bool(entry.attempts), "Missing artifact checksum/history receipt")
    for name, digest in entry.hashes.items():
        require(Path(name).name == name, "Unsafe artifact filename")
        require(sha(pub / name) == digest, f"Artifact checksum mismatch: {sid}/{name}")
    require((stage / "source.c").read_bytes() == record["func"].encode("utf-8"), "Wrong original source bytes")
    name = driver.resolve_function_name(record["func"])
    identity = read(stage / "identity.json")
    require(equal_typed(identity, {"manifest_entry": row,
            "dataset_index": driver.parse_sample_id(sid), "source_sha256": driver.source_sha256(record),
            "function_name": name, "configuration": vars(config)}), "Identity receipt mismatch")
    pair = {k: read(pub / f"{sid}.{k}.json") for k in KINDS}
    validate_pair(pair["graph_a"], pair["graph_b"], row, failure=entry.status == "FAILED")
    if entry.status == "SUCCESS":
        driver.validate_artifacts(stage, row, record, name, config)
        for filename in ("identity.json", "stages.jsonl", f"{sid}.metrics.json",
                         f"{sid}.graph_a.json", f"{sid}.graph_b.json"):
            require(filename in entry.hashes, "Incomplete publication checksum receipt")
            require(sha(pub / filename) == sha(stage / filename), "Publication/staging mismatch")
    else:
        # Quarantine relocation preserves metrics.source's old path. Verify the
        # relocation explicitly, without editing metrics or weakening the gate.
        require(pub == stage and stage.parent.name == "quarantine", "Wrong failure quarantine mapping")
        require({"source.c", "identity.json", "stages.jsonl", f"{sid}.metrics.json",
                 f"{sid}.graph_a.json", f"{sid}.graph_b.json"} <= entry.hashes.keys(),
                "Incomplete failure checksum receipt")
        metrics = read(stage / f"{sid}.metrics.json")
        expected_old = stage.parent.parent / stage.name / "source.c"
        require(metrics.get("source") == str(expected_old), "Failure original staging path mismatch")
        require(metrics.get("sample_id") == sid and metrics.get("function_name") == name and
                metrics.get("parse_succeeded") is True and metrics.get("error_stage") == "extract" and
                metrics.get("ddg_status") == "NOT_COMPUTED", "Failure metrics mismatch")
        reason = f"Expected exactly one method named {name}, found 0"
        log = events(stage)
        require(sum(e.get("stage") == "parse" and e.get("status") == "SUCCESS" and
                    e.get("exit_code") == 0 for e in log) == 1, "Missing failure parse evidence")
        require(sum(e.get("stage") == "extract" and e.get("status") == "FAILED" and
                    e.get("exit_code") == 1 and reason in e.get("stderr", "") for e in log) == 1,
                "Missing exact-method failure evidence")
        for graph in pair.values():
            require(graph["status"] == metrics.get("status") and
                    graph["error_message"] == metrics.get("error_message"), "Failure reason/status mismatch")
    return pair


def validate_plan(root: Path, plan: Plan) -> None:
    rows = [e.row for e in plan.entries]
    require(tuple(row["sample_id"] for row in rows) == IDS, "Wrong cohort/order or duplicate IDs")
    require(Counter(e.status for e in plan.entries) == {"SUCCESS": 25, "FAILED": 3, "UNSUPPORTED": 2}, "Wrong cohort accounting")
    records = {driver.parse_sample_id(e.row["sample_id"]): e.record for e in plan.entries}
    require(all(x.ok for x in driver.validate_samples(rows, records, None, True)), "Source/metadata validation failed")
    verify_hashes(root, plan.controls)
    for entry in plan.entries:
        sid = entry.row["sample_id"]
        require(entry.status == ("FAILED" if sid in FAILED else "UNSUPPORTED" if sid in UNSUPPORTED else "SUCCESS"), "Wrong terminal mapping")
        require(all(entry.row.get(k) is None for k in ("project_wise_split", "seen_project_split")), "Pilot split must be null")
        for ref in entry.attempts:
            require(within(root, root / ref).is_file(), "Missing attempt reference")
        originals(root, entry, plan.config)


def load_plan(root: Path) -> Plan:
    """Reconcile fixed checkpoint receipts. No discovery/resampling of sources."""
    root = root.resolve()
    base = root / "data/graphs"
    controls = read(base / "v2_pilot_7b9_final_two_evidence/baseline.json")["protected_sha256"]
    freeze_path = base / "v2_baseline_7a_evidence/freeze.json"
    freeze = read(freeze_path)
    controls = reconcile_report_paths(root, controls, freeze["protected_fingerprints"])
    controls.setdefault(HISTORICAL_REPORT, HISTORICAL_SHA256)
    controls.setdefault(FINAL_REPORT, FINAL_SHA256)
    require(freeze["query_sha256_utf8_lf"] == QUERY_SHA256 ==
            hashlib.sha256(joern._joern_script().encode("utf-8")).hexdigest(), "Frozen query mismatch")
    config = joern.JoernConfig(**freeze["configuration"])
    require(vars(config) == vars(joern.JoernConfig()), "Frozen configuration mismatch")
    verify_hashes(root, controls)
    manifest = root / "data/sample_manifests/diversevul_graph_sample.csv"
    dataset = root / "data/raw/diversevul/diversevul_20230702.json"
    rows = driver.read_manifest(manifest)
    require(tuple(x["sample_id"] for x in rows) == IDS, "Wrong manifest/order")
    records = driver.load_records_at_indices(dataset, {driver.parse_sample_id(x) for x in IDS})
    ledger_path = base / "v2_pilot_7b3_evidence/cohort_ledger.json"
    ledger = read(ledger_path)
    require(equal_typed(rows, [e["manifest_entry"] for e in ledger["records"]]), "Ledger/manifest mismatch")
    outcome_path = base / "v2_pilot_7b9_final_two_evidence/outcome.json"
    outcome = read(outcome_path)
    retained_path = base / "v2_pilot_7b9_final_two_evidence/retained_run_summary.json"
    retained = read(retained_path)
    summary_path = within(root, Path(retained["path"]))
    require(sha(summary_path) == retained["sha256"] and
            equal_typed(read(summary_path), retained["summary"]) and
            equal_typed(outcome["summary"], retained["summary"]), "Final-two summary mismatch")
    fresh = outcome["summary"]["samples"]
    require(outcome["status"] == outcome["summary"]["status"] == "SUCCESS" and
            [x["sample_id"] for x in fresh] == ["row-11455", "row-11987"] and
            all(x["status"] == "SUCCESS" for x in fresh), "Final-two scope/outcome mismatch")
    fresh = {x["sample_id"]: x for x in fresh}
    summaries = sorted(base.glob(".*-run-*/run_summary.json"))
    histories = {sid: [] for sid in IDS}
    failed_locations = {}
    for path in summaries:
        for attempt in read(path)["samples"]:
            sid = attempt["sample_id"]
            if sid in histories and attempt["status"] != "NOT_RUN":
                histories[sid].append(reference(root, path))
            if sid in FAILED and attempt["status"] == "FAILED":
                marker = "7b8_row1601-run-" if sid == "row-1601" else "7b2-run-" if sid == "row-6038" else "7b-run-"
                if marker in path.parent.name:
                    require(sid not in failed_locations, "Ambiguous latest failure mapping")
                    failed_locations[sid] = within(root, Path(attempt["quarantine"]))
    require(set(failed_locations) == FAILED, "Missing latest failure attempt")
    for n in (1, 2):
        path = base / f"v2_repeatability_v1_evidence/attempt-{n}/result.json"
        require(path.is_file(), "Missing retained-CPG repetition receipt")
        histories["row-12897"].append(reference(root, path))
    entries = []
    for row, old in zip(rows, ledger["records"]):
        sid = row["sample_id"]
        status = "FAILED" if sid in FAILED else "UNSUPPORTED" if sid in UNSUPPORTED else "SUCCESS"
        require(old["cohort_status"] == ("NOT_RUN" if sid in fresh else status), "Stale/unexpected ledger state")
        pub = stage = None
        hashes = {}
        if status == "SUCCESS":
            pub = within(root, Path(fresh[sid]["artifacts"] if sid in fresh else old["latest_accepted_v2"]))
            stage = within(root, Path(read(pub / f"{sid}.metrics.json")["source"]).parent)
            if sid in fresh:
                accepted = [x for x in outcome["accepted"] if x["sample_id"] == sid]
                require(len(accepted) == 1, "Missing/duplicate final-two checksum receipt")
                hashes = accepted[0]["published_sha256"]
            else:
                hashes = {p.name: controls[reference(root, p)] for p in pub.iterdir() if p.is_file()}
        elif status == "FAILED":
            pub = stage = failed_locations[sid]
            hashes = {p.name: controls[reference(root, p)] for p in pub.iterdir() if p.is_file()}
        else:
            require(not histories[sid], "Unsupported source has runtime history")
        entries.append(Entry(row, records[driver.parse_sample_id(sid)], status,
                             pub, stage, tuple(sorted(set(histories[sid]))), hashes))
    for path in [manifest, freeze_path, ledger_path, outcome_path, retained_path,
                 summary_path, *summaries]:
        controls[reference(root, path)] = sha(path)
    plan = Plan(tuple(entries), config, controls)
    validate_plan(root, plan)
    return plan


def delivery_object(original: dict, row: dict, record_kind: str) -> dict:
    require(not any(k in original for k in FIELDS), "Conflicting delivery metadata")
    result = copy.deepcopy(original)
    result.update(source_reference=row["source_reference"], record_kind=record_kind)
    projection = {k: v for k, v in result.items() if k not in FIELDS}
    require(equal_typed(projection, original), "Original-object projection mismatch")
    return result


def unsupported(row: dict, kind: str) -> dict:
    require(row["sample_id"] in UNSUPPORTED and kind in KINDS, "Wrong unsupported record")
    return dict(sample_id=row["sample_id"], cwe=row["cwe"], project_wise_split=None,
                seen_project_split=None, graph_type=kind, status="UNSUPPORTED_SOURCE_REPRESENTATION",
                ddg_status="NOT_COMPUTED", num_nodes=0, num_edges=0, nodes=[], edges=[],
                error_message=UNSUPPORTED_REASON, source_reference=row["source_reference"],
                record_kind="unsupported_source_record")


def write_new(path: Path, data: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def build_package(root: Path, stage: Path, plan: Plan) -> None:
    for kind in KINDS:
        directory = stage / kind
        directory.mkdir()
        manifest = []
        for order, entry in enumerate(plan.entries, 1):
            row, sid = entry.row, entry.row["sample_id"]
            source = None
            if entry.status == "UNSUPPORTED":
                payload = unsupported(row, kind)
            else:
                original = originals(root, entry, plan.config)[kind]
                payload = delivery_object(original, row, "extracted_graph" if entry.status == "SUCCESS" else "failure_record")
                source = entry.publication / f"{sid}.{kind}.json"
            path = directory / f"{sid}.json"
            write_new(path, encode(payload))
            manifest.append(dict(manifest_order=order, sample_id=sid,
                dataset_index=driver.parse_sample_id(sid), cwe=row["cwe"],
                source_reference=row["source_reference"], source_sha256=row["source_sha256"],
                project_wise_split="", seen_project_split="", record_kind=payload["record_kind"],
                cohort_status=entry.status, status=payload["status"], graph_type=kind,
                num_nodes=payload["num_nodes"], num_edges=payload["num_edges"],
                ddg_status=payload["ddg_status"], error_message=payload.get("error_message", ""),
                json_file=path.name, json_sha256=sha(path), json_bytes=path.stat().st_size,
                original_artifact_reference=reference(root, source) if source else "",
                original_artifact_sha256=sha(source) if source else "",
                attempt_references=json.dumps(entry.attempts, ensure_ascii=True, separators=(",", ":"))))
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(manifest)
        write_new(directory / "manifest.csv", stream.getvalue().encode("utf-8"))


def validate_package(root: Path, directory: Path, plan: Plan) -> None:
    require({p.name for p in directory.iterdir()} == set(KINDS), "Unexpected package contents")
    for kind in KINDS:
        folder = directory / kind
        require({p.name for p in folder.iterdir()} == {f"{sid}.json" for sid in IDS} | {"manifest.csv"}, "Expected exactly 30 JSONs and one manifest")
        with (folder / "manifest.csv").open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            require(tuple(reader.fieldnames or ()) == COLUMNS, "Manifest columns mismatch")
            rows = list(reader)
        require([x["sample_id"] for x in rows] == list(IDS), "Manifest order/count mismatch")
        for order, (row, entry) in enumerate(zip(rows, plan.entries), 1):
            sid = entry.row["sample_id"]
            path = folder / f"{sid}.json"
            payload = read(path)
            expected = unsupported(entry.row, kind) if entry.status == "UNSUPPORTED" else delivery_object(
                originals(root, entry, plan.config)[kind], entry.row,
                "extracted_graph" if entry.status == "SUCCESS" else "failure_record")
            require(equal_typed(payload, expected), "Delivery original-object projection/payload mismatch")
            expected_row = dict(manifest_order=str(order), sample_id=sid,
                dataset_index=str(driver.parse_sample_id(sid)), cwe=entry.row["cwe"],
                source_reference=entry.row["source_reference"], source_sha256=entry.row["source_sha256"],
                project_wise_split="", seen_project_split="", record_kind=expected["record_kind"],
                cohort_status=entry.status, status=expected["status"], graph_type=kind,
                num_nodes=str(expected["num_nodes"]), num_edges=str(expected["num_edges"]),
                ddg_status=expected["ddg_status"], error_message=expected.get("error_message", ""),
                json_file=path.name, json_sha256=sha(path), json_bytes=str(path.stat().st_size),
                original_artifact_reference="", original_artifact_sha256="",
                attempt_references=json.dumps(entry.attempts, ensure_ascii=True, separators=(",", ":")))
            if entry.publication:
                source = entry.publication / f"{sid}.{kind}.json"
                expected_row.update(original_artifact_reference=reference(root, source), original_artifact_sha256=sha(source))
            require(row == expected_row, "Manifest identity/count/checksum/provenance mismatch")


def publish_no_replace(stage: Path, destination: Path) -> None:
    """Fail closed on unsupported platforms; never replace an empty directory."""
    require(not os.path.lexists(destination), "Destination collision")
    if os.name == "nt":
        os.rename(stage, destination)  # Windows rename refuses any existing target.
    elif sys.platform.startswith("linux"):
        libc = ctypes.CDLL(None, use_errno=True)
        rename = getattr(libc, "renameat2", None)
        require(rename is not None, "Atomic no-replace rename unavailable")
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        if rename(-100, os.fsencode(stage), -100, os.fsencode(destination), 1) != 0:
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error), str(destination))
    else:
        raise DeliveryError("Atomic no-replace publication unsupported on this platform")


def git_diff_check(root: Path) -> None:
    # Only this fixed Git read operation is allowed; no shell or runtime launch.
    result = subprocess.run(["git", "-C", str(root), "diff", "--check"],
                            capture_output=True, timeout=30, check=False)
    require(result.returncode == 0, "git diff --check failed: " + result.stdout.decode("utf-8", errors="replace"))


def check_completion(evidence: Path, expected: dict | None = None) -> dict:
    """Failure receipts always take precedence, including over a finalized PASS.

    This checks receipt state, not the process exit status or package bytes.
    Acceptance also requires an observed successful invocation and independent
    package/checksum verification; a file alone cannot prove process completion.
    """
    require(not os.path.lexists(evidence / "failure.json"), "Failure receipt takes precedence")
    receipt = read(evidence / "final_integrity.json")
    require(receipt.get("V7_V8") == "PASS" and receipt.get("published") is True and
            type(receipt.get("protected_files_checked")) is int and
            receipt["protected_files_checked"] > 0 and receipt.get("mismatches") == [] and
            isinstance(receipt.get("files"), dict) and len(receipt["files"]) == 62,
            "Invalid completion receipt")
    if expected is not None:
        require(equal_typed(receipt, expected), "Completion receipt differs from verified result")
    require(not os.path.lexists(evidence / "failure.json"), "Failure receipt takes precedence")
    return receipt


def finalize_completion(evidence: Path, receipt: dict) -> None:
    """Publish only a fully written, flushed, fsynced and verified receipt."""
    require(not os.path.lexists(evidence / "failure.json"), "Failure receipt takes precedence")
    pending = evidence / f".final_integrity-{uuid.uuid4().hex}.pending"
    write_new(pending, encode(receipt))
    require(equal_typed(read(pending), receipt), "Pending completion receipt mismatch")
    require(not os.path.lexists(evidence / "failure.json"), "Failure receipt takes precedence")
    publish_no_replace(pending, evidence / "final_integrity.json")
    check_completion(evidence, receipt)


def retain_failure(evidence: Path, error: BaseException, *, published: bool,
                   staging: str, destination: str, owned: bool = True) -> None:
    """Best effort evidence; never hide the original exception on I/O failure."""
    try:
        require(owned, "Evidence directory was not created by this run; existing evidence is untouched")
        write_new(evidence / "failure.json", encode({"error_type": type(error).__name__,
                  "error": str(error), "published": published,
                  "staging": staging, "destination": destination}))
    except Exception as receipt_error:
        try:
            print(f"INCOMPLETE: original error: {error}; failure receipt could not be "
                  f"persisted at {evidence}: {receipt_error}. Do not accept this run.",
                  file=sys.stderr)
        except Exception:
            # A broken stderr and unwritable filesystem cannot provide durable
            # diagnostics. The original exception still propagates to caller.
            pass


def export(root: Path, plan: Plan) -> Path:
    """Explicit write entry point. Merely importing this module writes nothing."""
    root = root.resolve()
    destination = root / "reports/graph/3_2_pilot"
    require(not os.path.lexists(destination), "Destination already exists")
    require(destination.parent.is_dir(), "Destination parent must already exist")
    validate_plan(root, plan)
    baseline = inventory(root)
    run_id = uuid.uuid4().hex
    stage = destination.parent / f".3_2_pilot-export-{run_id}"
    evidence_parent = root / "data/graphs/pilot_delivery_export_evidence"
    require(evidence_parent.parent.is_dir(), "Evidence parent must already exist")
    within(root, destination.parent)
    within(root, evidence_parent)
    require(not evidence_parent.is_symlink(), "Evidence directory must not be a symlink")
    evidence = evidence_parent / run_id
    published = False
    evidence_owned = False
    try:
        evidence_parent.mkdir(exist_ok=True)
        evidence.mkdir()
        evidence_owned = True
        write_new(evidence / "baseline.json", encode({"protected_sha256": baseline,
                  "query_sha256": QUERY_SHA256, "configuration": vars(plan.config),
                  "destination": reference(root, destination), "staging": reference(root, stage),
                  "cohort": {"SUCCESS": 25, "FAILED": 3, "NOT_RUN": 0, "UNSUPPORTED": 2}}))
        stage.mkdir()
        build_package(root, stage, plan)
        validate_plan(root, plan)
        validate_package(root, stage, plan)
        verify_protected(root, baseline, (stage, evidence))
        git_diff_check(root)
        hashes = {p.relative_to(stage).as_posix(): sha(p) for p in stage.rglob("*") if p.is_file()}
        require(len(hashes) == 62, "Wrong publication file count")
        write_new(evidence / "validation.json", encode({"V1_V6": "PASS", "files": hashes,
                  "mappings": [{"sample_id": e.row["sample_id"], "status": e.status,
                  "publication": reference(root, e.publication) if e.publication else None,
                  "staging": reference(root, e.staging) if e.staging else None,
                  "attempts": e.attempts} for e in plan.entries]}))
        publish_no_replace(stage, destination)
        published = True
        validate_package(root, destination, plan)
        require(all(sha(destination / p) == h for p, h in hashes.items()), "Published checksum mismatch")
        verify_protected(root, baseline, (destination, evidence))
        git_diff_check(root)
        # All package, protected-file and Git checks precede completion evidence.
        # There is no further mandatory filesystem work after finalization.
        finalize_completion(evidence, {"V7_V8": "PASS", "published": True,
                            "protected_files_checked": len(baseline), "mismatches": [], "files": hashes})
        return evidence
    except BaseException as error:
        # Never delete/repair outputs, staging or prior evidence after failure.
        retain_failure(evidence, error, published=published,
                       staging=stage.relative_to(root).as_posix(),
                       destination=destination.relative_to(root).as_posix(), owned=evidence_owned)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-only", action="store_true", help="Read-only receipt/gate verification")
    mode.add_argument("--export", action="store_true", help="Requires separate production-export approval")
    args = parser.parse_args(argv)
    try:
        plan = load_plan(args.root)
        if args.check_only:
            print("PASS: 30 identities; 25 accepted, 3 failed, 2 unsupported. No export.")
        else:
            print(f"STOP: delivery complete; evidence: {export(args.root, plan)}")
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"STOP: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Batch driver Task 3.2/3.3: đọc manifest pilot, resolve record theo index 0-based, validate fail-closed.

Quy ước bắt buộc (Strategy A, đã duyệt): ``sample_id`` dạng ``row-N`` với N là
**dataset record index 0-based** — tức dòng vật lý N+1 trong file JSONL không
có dòng trống. Quy ước này khớp generator ``src/data/diversevul_audit.py``
(``canonicalize`` sinh ``row-{index}`` từ RangeIndex 0-based của pandas) và với
manifest thí nghiệm 9.077 mẫu; đọc theo dòng vật lý N là SAI và từng gây lỗi
off-by-one cho cả 30 mẫu pilot (xem reports/graph/3_2_manifest_consistency_audit.md).

Bản sắc source — ``source_sha256``: SHA-256 (hex 64) của **chuỗi nguyên vẹn**
trường ``func`` — lấy bằng ``json.loads`` toàn bộ dòng record (chuẩn JSON, text
UTF-8) rồi ``.encode("utf-8")``. Không chuẩn hóa whitespace, không đổi line
ending, không thêm/xóa ký tự. Cùng một thủ tục được dùng ở cả hai phía:
``--enrich-manifest`` (tính cột khi enrich) và reader validation, nên hai phía
luôn đồng nhất tuyệt đối. Hàm rỗng/thiếu ``func`` là lỗi fail-closed, không
được hash chuỗi rỗng.

Fail-closed: parse id sai / index vượt tầm / thiếu record / metadata mismatch /
hash mismatch → mẫu bị loại với lỗi tường minh, **không gọi Joern** cho mẫu
đó. Full run dừng ở lỗi đầu tiên, giữ staging/quarantine và các mẫu đã hoàn
tất; chỉ publish atomic từng mẫu sau khi pass acceptance. --preflight chỉ
kiểm bản sắc, resolve declaration và bind signature, không chạy Joern.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import inspect
import json
import math
import os
import re
import shutil
import sys
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_MANIFEST = ROOT / "data" / "sample_manifests" / "diversevul_graph_sample.csv"
DEFAULT_DATASET = ROOT / "data" / "raw" / "diversevul" / "diversevul_20230702.json"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "graphs" / "validated_v2"

BASE_COLUMNS = ["sample_id", "project", "commit", "cwe", "label", "source_reference"]
HASH_COLUMN = "source_sha256"
ROW_ID = re.compile(r"row-(0|[1-9][0-9]*)")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class ManifestValidationError(ValueError):
    """Lỗi fail-closed ở lớp đọc manifest/đối chiếu dataset."""


def parse_sample_id(sample_id: object) -> int:
    """``row-N`` → N (int không âm, không leading zero); mọi dạng khác báo lỗi."""
    if not isinstance(sample_id, str):
        raise ManifestValidationError(f"sample_id phải là chuỗi, nhận {type(sample_id).__name__}")
    match = ROW_ID.fullmatch(sample_id)
    if not match:
        raise ManifestValidationError(f"sample_id {sample_id!r} không đúng dạng row-<so nguyen khong am>")
    digits = match.group(1)
    try:
        value = int(digits)
    except ValueError as error:
        raise ManifestValidationError("sample_id index is too large") from error
    if str(value) != digits:
        raise ManifestValidationError(f"sample_id {sample_id!r} có chữ số 0 đứng đầu không hợp lệ")
    return value


def iter_dataset_records(dataset_path: Path) -> Any:
    """Read JSONL without shifting indices; blank/malformed records fail closed."""
    with Path(dataset_path).open(encoding="utf-8") as handle:
        for index, line in enumerate(handle):
            if not line.strip():
                raise ManifestValidationError(f"Blank dataset line {index + 1}")
            try:
                record = json.loads(line)
            except ValueError as error:
                raise ManifestValidationError(f"Invalid JSON at dataset index {index}") from error
            if not isinstance(record, dict):
                raise ManifestValidationError(f"Non-object dataset record at index {index}")
            yield index, record


def load_records_at_indices(dataset_path: Path, indices: set[int]) -> dict[int, dict]:
    """Một lượt duyệt file, gom record tại các index cần; thiếu index nào ném lỗi."""
    found: dict[int, dict] = {}
    if not indices:
        return found
    if any(type(index) is not int or index < 0 for index in indices):
        raise ManifestValidationError("Dataset indices must be nonnegative integers")
    total = 0
    for index, record in iter_dataset_records(dataset_path):
        total = index + 1
        if index in indices:
            found[index] = record
        if len(found) == len(indices):
            break
    missing = indices - found.keys()
    if missing:
        raise ManifestValidationError(
            f"Index vượt tầm dataset: {sorted(missing)} (tổng số record đã duyệt: {total})"
        )
    return found


def normalize_cwe(value: object) -> str:
    if isinstance(value, list):
        if not all(isinstance(item, str) for item in value):
            raise ManifestValidationError("CWE list must contain strings")
        return "|".join(value)
    if isinstance(value, str):
        return value
    raise ManifestValidationError("Missing or invalid CWE field")


def normalize_label(value: object) -> str:
    if type(value) is int and value == 1:
        return "vulnerable"
    if type(value) is int and value == 0:
        return "non-vulnerable"
    raise ManifestValidationError(f"target không hợp lệ: {value!r} (chỉ chấp nhận 0/1)")


def source_sha256(record: dict) -> str:
    """SHA-256 của trường ``func`` nguyên vẹn (json.loads rồi encode UTF-8)."""
    func = record.get("func")
    if not isinstance(func, str) or not func.strip():
        raise ManifestValidationError("record thiếu trường 'func' hoặc func rỗng — không tính hash")
    try:
        return hashlib.sha256(func.encode("utf-8")).hexdigest()
    except UnicodeError as error:
        raise ManifestValidationError("Source cannot be encoded as strict UTF-8") from error


def metadata_mismatches(row: dict, record: dict) -> list[str]:
    """So 4 trường manifest với record; trả về danh sách khác biệt (rỗng = khớp)."""
    problems: list[str] = []
    for field in ("project", "commit_id"):
        if not isinstance(record.get(field), str) or not record[field]:
            raise ManifestValidationError(f"Missing or invalid dataset {field}")
    manifest_project = row.get("project")
    record_project = record["project"]
    if manifest_project != record_project:
        problems.append(f"project: manifest={manifest_project!r} dataset={record_project!r}")
    manifest_commit = row.get("commit")
    record_commit = record["commit_id"]
    if manifest_commit != record_commit:
        problems.append(f"commit: manifest={manifest_commit!r} dataset={record_commit!r}")
    manifest_cwe = row.get("cwe")
    record_cwe = normalize_cwe(record.get("cwe"))
    if manifest_cwe != record_cwe:
        problems.append(f"cwe: manifest={manifest_cwe!r} dataset={record_cwe!r}")
    manifest_label = row.get("label")
    record_label = normalize_label(record.get("target"))
    if manifest_label != record_label:
        problems.append(f"label: manifest={manifest_label!r} dataset={record_label!r}")
    return problems


@dataclass(frozen=True)
class SampleResult:
    sample_id: str
    index: int | None
    metadata_status: str
    hash_status: str
    ok: bool
    errors: tuple[str, ...]

    def as_row(self) -> dict[str, str]:
        return {
            "sample_id": self.sample_id,
            "dataset_index": "-" if self.index is None else str(self.index),
            "metadata": self.metadata_status,
            "source_hash": self.hash_status,
            "result": "PASS" if self.ok else "FAIL",
            "errors": "; ".join(self.errors),
        }


def validate_samples(
    rows: list[dict],
    records_by_index: dict[int, dict],
    total_records: int | None,
    require_hash: bool,
) -> list[SampleResult]:
    """Validate từng mẫu fail-closed; không ném ngoại lệ ra ngoài batch.

    ``load_records_at_indices`` đã bảo đảm mọi index có record (thiếu = lỗi
    tầm vực đã ném); ``total_records`` chỉ dùng thêm cho thông báo khi caller
    muốn kiểm chứng độc lập.
    """
    results: list[SampleResult] = []
    ids = [row.get("sample_id") for row in rows]
    for row in rows:
        sample_id = row.get("sample_id", "")
        errors: list[str] = []
        index: int | None = None
        metadata_status = "NOT_CHECKED"
        hash_status = "NOT_CHECKED"
        try:
            index = parse_sample_id(sample_id)
            if ids.count(sample_id) != 1:
                raise ManifestValidationError(f"Duplicate sample_id: {sample_id}")
            if row.get("source_reference") != f"dataset row sample_id={sample_id}":
                raise ManifestValidationError("source_reference does not match sample_id")
            if total_records is not None and index >= total_records:
                raise ManifestValidationError(
                    f"index {index} vượt tầm dataset ({total_records} record)"
                )
            if index not in records_by_index:
                raise ManifestValidationError(f"Missing dataset record at index {index}")
            record = records_by_index[index]
            problems = metadata_mismatches(row, record)
            metadata_status = "MATCH" if not problems else "MISMATCH"
            errors.extend(problems)
            if require_hash:
                expected = row.get(HASH_COLUMN) or ""
                if not expected:
                    raise ManifestValidationError(f"manifest thiếu cột {HASH_COLUMN}")
                if not HEX64.fullmatch(expected):
                    raise ManifestValidationError(f"{HASH_COLUMN} không phải hex 64: {expected!r}")
                actual = source_sha256(record)
                hash_status = "MATCH" if actual == expected else "MISMATCH"
                if actual != expected:
                    errors.append(f"{HASH_COLUMN}: manifest={expected} dataset={actual}")
        except ManifestValidationError as error:
            errors.append(str(error))
        results.append(
            SampleResult(
                sample_id=str(sample_id),
                index=index,
                metadata_status=metadata_status,
                hash_status=hash_status,
                ok=not errors,
                errors=tuple(errors),
            )
        )
    return results


def read_manifest(manifest_path: Path) -> list[dict]:
    with Path(manifest_path).open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        if len(columns) != len(set(columns)):
            raise ManifestValidationError("Duplicate manifest columns")
        rows = list(reader)
    if not rows:
        raise ManifestValidationError(f"manifest rỗng: {manifest_path}")
    for column in BASE_COLUMNS:
        if column not in rows[0]:
            raise ManifestValidationError(f"manifest thiếu cột bắt buộc {column!r}: {manifest_path}")
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ManifestValidationError("Malformed CSV row")
    return rows


def count_records(dataset_path: Path) -> int:
    """Đếm tổng record; chỉ dùng khi caller cần kiểm chứng tầm vực độc lập."""
    return sum(1 for _ in iter_dataset_records(dataset_path))


def write_manifest(rows: list[dict], manifest_path: Path) -> None:
    """Ghi CSV deterministic: cột gốc giữ nguyên thứ tự + source_sha256 ở cuối, LF."""
    columns = list(rows[0].keys())
    if HASH_COLUMN not in columns:
        columns.append(HASH_COLUMN)
    with Path(manifest_path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def enrich_manifest(manifest_path: Path, dataset_path: Path, backup_path: Path | None = None) -> None:
    """Thêm cột source_sha256 vào manifest, tại chỗ, deterministic + idempotent.

    Tính hash từ record đúng (index N) của từng sample_id; không re-sample,
    không đổi thứ tự dòng, không đổi giá trị cột hiện có. Cột đã tồn tại sẽ
    được kiểm chứng, không tự động thay hash sai. Backup + checksum được giữ
    trước khi ghi atomic; chạy lại cho cùng dữ liệu cho cùng byte.
    """
    rows = read_manifest(manifest_path)
    indices = {parse_sample_id(row["sample_id"]) for row in rows}
    records = load_records_at_indices(dataset_path, indices)
    results = validate_samples(rows, records, None, require_hash=HASH_COLUMN in rows[0])
    if any(not result.ok for result in results):
        raise ManifestValidationError("Enrichment rejected: metadata, ID or existing source hash mismatch")
    original = Path(manifest_path).read_bytes()
    backup = Path(backup_path) if backup_path else Path(str(manifest_path) + ".baseline.csv")
    if backup.resolve() == Path(manifest_path).resolve():
        raise ManifestValidationError("Backup must be separate from manifest")
    if backup.exists() and backup.read_bytes() != original:
        # An original backup remains valid after enrichment; never overwrite it.
        saved_rows = read_manifest(backup)
        original_fields = [key for key in rows[0] if key != HASH_COLUMN]
        if [{k: row.get(k) for k in original_fields} for row in saved_rows] != [
            {k: row[k] for k in original_fields} for row in rows
        ]:
            raise ManifestValidationError("Existing backup belongs to a different manifest")
    elif not backup.exists():
        backup.parent.mkdir(parents=True, exist_ok=True)
        with backup.open("xb") as handle:
            handle.write(original)
    checksum_path = Path(str(backup) + ".sha256")
    checksum = hashlib.sha256(backup.read_bytes()).hexdigest() + "\n"
    if checksum_path.exists():
        if checksum_path.read_text(encoding="ascii") != checksum:
            raise ManifestValidationError("Backup checksum mismatch")
    else:
        with checksum_path.open("x", encoding="ascii") as handle:
            handle.write(checksum)
    for row in rows:
        index = parse_sample_id(row["sample_id"])
        row[HASH_COLUMN] = source_sha256(records[index])
    with tempfile.TemporaryDirectory(prefix=".manifest-", dir=Path(manifest_path).parent) as directory:
        staged = Path(directory) / "manifest.csv"
        write_manifest(rows, staged)
        if staged.read_bytes() != original:
            os.replace(staged, manifest_path)


def render_evidence_markdown(results: list[SampleResult]) -> str:
    lines = [
        "| sample_id | resolved dataset index | metadata validation | source hash validation | overall |",
        "|---|---|---|---|---|",
    ]
    for result in results:
        row = result.as_row()
        lines.append(
            f"| {row['sample_id']} | {row['dataset_index']} | {row['metadata']} "
            f"| {row['source_hash']} | {row['result']} |"
        )
    passed = sum(1 for result in results if result.ok)
    lines.append("")
    lines.append(f"PASS: {passed}/{len(results)}; FAIL: {len(results) - passed}/{len(results)}")
    return "\n".join(lines) + "\n"


def resolve_function_name(source: str) -> str:
    """Resolve one explicit C/C++ definition, never a macro-expanded/guessed name.

    Uses the extractor's literal/comment-aware lexer. Only a single balanced
    top-level definition and a unique declarator are accepted. Unsupported
    declarators, preprocessor-dependent signatures and multiple definitions fail
    closed. Joern subsequently requires exactly one nameExact match as well.
    This is declaration recognition, not a substitute for a C/C++ parser.
    """
    from src.graph.joern import _lexical_tokens

    # Directives can select competing definitions or rename a declaration.
    # Do not interpret them or silently pick a preprocessor branch.
    header = source.split("{", 1)[0]
    if re.search(r"(?m)^\s*#", header):
        raise ManifestValidationError("Preprocessor-dependent function declaration")
    tokens = [token for token, _ in _lexical_tokens(source)]
    try:
        body = tokens.index("{")
    except ValueError as error:
        raise ManifestValidationError("No function body found") from error
    depth = 0
    end = None
    for position in range(body, len(tokens)):
        if tokens[position] == "{":
            depth += 1
        elif tokens[position] == "}":
            depth -= 1
            if depth == 0:
                end = position
                break
    if end is None or any(token != ";" for token in tokens[end + 1:]):
        raise ManifestValidationError("Unbalanced or multiple function definitions")
    prefix = tokens[:body]
    if prefix and prefix[0] in {"return", "switch", "if", "while", "for", "case", "else",
                                "do", "try", "catch", "throw", "break", "continue", "typedef", "using"}:
        raise ManifestValidationError("Source is a statement/declaration fragment, not a function definition")
    if any(token in {";", "=", "operator", "#"} for token in prefix):
        raise ManifestValidationError("Unsupported or ambiguous function declarator")
    candidates = []
    parentheses = 0
    annotations = {"__attribute__", "__declspec", "noexcept", "alignas", "_Alignas", "decltype"}
    for position, token in enumerate(prefix):
        if token == "(":
            if parentheses == 0 and position and prefix[position - 1].isidentifier():
                name = prefix[position - 1]
                if name not in annotations:
                    if position >= 2 and prefix[position - 2] == "~":
                        name = "~" + name
                    candidates.append(name)
            parentheses += 1
        elif token == ")":
            parentheses -= 1
            if parentheses < 0:
                raise ManifestValidationError("Unbalanced function declarator")
    if parentheses or len(candidates) != 1:
        raise ManifestValidationError("Function name is missing or ambiguous")
    name = candidates[0]
    if prefix[0] == name:
        # DiverseVul includes definitions with omitted return types. Accept the
        # explicit name only when every parameter has declaration evidence;
        # identifier-only macro arguments / K&R declarations remain ambiguous.
        groups, group, depth = [], [], 0
        for token in prefix[2:]:
            if token == ")" and depth == 0:
                groups.append(group)
                break
            if token == "," and depth == 0:
                groups.append(group)
                group = []
                continue
            if token in {"(", "["}:
                depth += 1
            elif token in {")", "]"}:
                depth -= 1
            group.append(token)
        if not groups or not all(group == ["void"] or
                len([token for token in group if token.isidentifier()]) >= 2 for group in groups):
            raise ManifestValidationError("Untyped or macro-like declaration is ambiguous")
    if name.lstrip("~") in {"int", "char", "void", "float", "double", "long", "short",
                             "bool", "unsigned", "signed", "auto", "if", "while", "switch", "for"}:
        raise ManifestValidationError("Unsupported function-pointer or non-function declarator")
    # Uppercase declaration macros are not a reliable Joern method name.
    if name.isupper():
        raise ManifestValidationError("Macro-like declarator needs explicit resolution")
    return name


def extraction_arguments(row: dict, record: dict, function_name: str) -> dict:
    """Exact extractor contract; project/commit are redaction context only."""
    return dict(sample_id=row["sample_id"], function_name=function_name, cwe=row["cwe"],
                project_wise_split=row.get("project_wise_split") or None,
                seen_project_split=row.get("seen_project_split") or None,
                project_name=record["project"], commit_id=record["commit_id"])


def preflight_samples(rows: list[dict], records: dict[int, dict]) -> list[dict]:
    """Pure input/method/interface checks; no extractor instance or subprocess."""
    results = validate_samples(rows, records, None, True)
    evidence = []
    for row, result in zip(rows, results):
        entry = result.as_row()
        entry.update(method="NOT_CHECKED", contract="NOT_CHECKED")
        if result.ok:
            try:
                from src.graph.joern import JoernExtractor
                name = resolve_function_name(records[result.index]["func"])
                entry["method"] = name
                arguments = extraction_arguments(row, records[result.index], name)
                inspect.signature(JoernExtractor.extract).bind(None, Path("source.c"), Path("staging"), **arguments)
                entry["contract"] = "MATCH"
            except (ManifestValidationError, TypeError) as error:
                entry.update(result="FAIL", errors=str(error))
        evidence.append(entry)
    return evidence


def _event(path: Path, **entry: Any) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(entry, ensure_ascii=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _make_extractor(config: Any, log_path: Path) -> Any:
    """Audit subprocess stages without modifying the shared production extractor."""
    from src.graph.joern import JoernExtractor, JoernExecutionError

    class AuditedExtractor(JoernExtractor):
        def _run_stage(self, stage, command, working_dir):
            _event(log_path, stage=stage, status="STARTED", command=command,
                   working_dir=str(working_dir), timeout_sec=self.config.timeout_sec)
            try:
                if os.name == "nt":
                    completed = self._run_wsl(stage, command, working_dir)
                else:
                    env = os.environ.copy()
                    if self.config.java_home:
                        env["JAVA_HOME"] = self.config.java_home
                        env["PATH"] = str(Path(self.config.java_home) / "bin") + os.pathsep + env.get("PATH", "")
                    if stage == "extract":
                        env["SL_LOGGING_LEVEL"] = "INFO"
                    completed = subprocess.run(command, cwd=working_dir, env=env,
                        check=False, capture_output=True, text=True, timeout=self.config.timeout_sec)
            except Exception as error:
                def decoded(value):
                    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value or ""
                _event(log_path, stage=stage, status="TIMEOUT" if isinstance(error, subprocess.TimeoutExpired) else "ERROR",
                       command=command, executed_command=getattr(error, "cmd", None),
                       exit_code=getattr(error, "returncode", None), stdout=decoded(getattr(error, "stdout", None)),
                       stderr=decoded(getattr(error, "stderr", None)), error=str(error))
                if isinstance(error, subprocess.TimeoutExpired):
                    raise
                raise JoernExecutionError(stage, str(error)) from error
            _event(log_path, stage=stage, status="SUCCESS" if completed.returncode == 0 else "FAILED",
                   command=command, executed_command=completed.args, exit_code=completed.returncode,
                   stdout=completed.stdout or "", stderr=completed.stderr or "")
            if completed.returncode:
                raise JoernExecutionError(stage, f"Command failed (exit {completed.returncode}); see {log_path}")
            return completed

    extractor = AuditedExtractor(config)
    extractor.audit_log_path = log_path
    return extractor


SUCCESS_STATUSES = {"SUCCESS", "OVERSIZED_GRAPH", "EMPTY_FUNCTION_BODY",
                    "COMMENT_ONLY_FUNCTION", "BODY_CLASSIFICATION_UNKNOWN"}
FAILURE_STATUSES = {"PARSE_ERROR", "AST_EXTRACTION_ERROR", "TIMEOUT_ERROR"}


def validate_artifacts(directory: Path, row: dict, record: dict, function_name: str,
                       config: Any, *, failure: bool = False) -> list[Path]:
    """Acceptance gate for actual files, not process exit codes. Never repairs data."""
    from src.graph.joern import _ddg_method_log_evidence, _normalize_ddg_status
    from src.graph.schema_policy import classify_extraction_status

    def require(condition: bool, message: str) -> None:
        if not condition:
            raise ManifestValidationError(message)

    sid = row["sample_id"]
    require(source_sha256(record) == row[HASH_COLUMN], "Source identity changed before acceptance")
    require(not metadata_mismatches(row, record), "Source metadata changed before acceptance")
    paths = [directory / f"{sid}.{suffix}.json" for suffix in ("graph_a", "graph_b", "metrics")]
    try:
        a, b, metrics = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    except (OSError, ValueError) as error:
        raise ManifestValidationError("Missing or unreadable artifact triplet") from error
    require(all(isinstance(item, dict) for item in (a, b, metrics)), "Artifact root must be an object")
    require(metrics.get("sample_id") == sid, "Metrics sample_id mismatch")
    require(metrics.get("function_name") == function_name, "Metrics function_name mismatch")
    require(metrics.get("source") == str(directory / "source.c"), "Metrics source path mismatch")
    require((directory / "source.c").read_bytes() == record["func"].encode("utf-8"), "Extracted source bytes changed")
    identity = json.loads((directory / "identity.json").read_text(encoding="utf-8"))
    require(identity == {"manifest_entry": row, "dataset_index": parse_sample_id(sid),
                        "source_sha256": source_sha256(record), "function_name": function_name,
                        "configuration": vars(config)}, "Source identity audit mismatch")
    total_lines = max(1, len(record["func"].splitlines()))
    for kind, graph in (("graph_a", a), ("graph_b", b)):
        for key, value in {"sample_id": sid, "cwe": row["cwe"],
                           "project_wise_split": row.get("project_wise_split") or None,
                           "seen_project_split": row.get("seen_project_split") or None,
                           "graph_type": kind}.items():
            require(key in graph and graph[key] == value, f"Graph metadata mismatch: {key}")
        require(graph.get("status") in (FAILURE_STATUSES if failure else SUCCESS_STATUSES), "Invalid graph status")
        nodes, edges = graph.get("nodes"), graph.get("edges")
        require(isinstance(nodes, list) and isinstance(edges, list), "Missing node/edge arrays")
        require(type(graph.get("num_nodes")) is int and graph["num_nodes"] == len(nodes), "Node count mismatch")
        require(type(graph.get("num_edges")) is int and graph["num_edges"] == len(edges), "Edge count mismatch")
        require(all(isinstance(node, dict) for node in nodes), "Invalid node object")
        require([node.get("id") for node in nodes] == list(range(len(nodes))) and
                all(type(node.get("id")) is int for node in nodes), "Node IDs must be consecutive integers")
        for node in nodes:
            require(set(node) == {"id", "node_type", "code_token", "line_number", "rel_line_number"}, "Invalid node fields")
            require(isinstance(node["node_type"], str) and bool(node["node_type"]) and
                    isinstance(node["code_token"], str) and bool(node["code_token"]), "Invalid node features")
            require(node["node_type"].casefold() != "comment", "Comment nodes must be excluded")
            line, rel = node["line_number"], node["rel_line_number"]
            require(type(line) is int and 1 <= line <= total_lines, "Node line outside intended source")
            require(type(rel) in (int, float) and math.isfinite(rel) and 0 <= rel <= 1 and
                    math.isclose(rel, line / total_lines, rel_tol=0, abs_tol=1e-12), "Invalid rel_line_number")
        keys = []
        for edge in edges:
            require(isinstance(edge, dict) and set(edge) == {"src", "dst", "type"}, "Invalid edge fields")
            require(all(type(edge[key]) is int for key in edge), "Edge values must be integers")
            require(0 <= edge["src"] < len(nodes) and 0 <= edge["dst"] < len(nodes), "Edge endpoint outside node domain")
            require(edge["type"] in ({0} if kind == "graph_a" else {0, 1, 2}), "Forbidden edge type")
            require(edge["src"] != edge["dst"], "Self-loop was not removed")
            keys.append((edge["src"], edge["dst"], edge["type"]))
        require(len(keys) == len(set(keys)), "Duplicate edge was not removed")
        if failure:
            require(not nodes and not edges and graph.get("ddg_status") == "NOT_COMPUTED" and
                    isinstance(graph.get("error_message"), str) and bool(graph["error_message"]), "Invalid failure payload")
        else:
            require(bool(nodes), "Successful-looking graph is empty")
            # Apply existing classification rather than changing schema policy.
            status = classify_extraction_status(parse_succeeded=True, ast_available=True, function_body_available=True,
                statement_count=metrics.get("statement_count"), comment_count=metrics.get("comment_count"),
                num_nodes=len(nodes), num_edges=len(edges), max_nodes=config.max_nodes, max_edges=config.max_edges)
            require(graph["status"] == status, "Graph status disagrees with schema classification")
    require(a["nodes"] == b["nodes"], "Graph A/B node domains differ")
    require({(e["src"], e["dst"], e["type"]) for e in a["edges"]} ==
            {(e["src"], e["dst"], e["type"]) for e in b["edges"] if e["type"] == 0}, "Graph B AST differs from Graph A")
    require(metrics.get("status") == b["status"], "Metrics/graph status mismatch")
    if failure:
        require(metrics.get("ddg_status") == "NOT_COMPUTED" and
                isinstance(metrics.get("error_stage"), str) and bool(metrics["error_stage"]) and
                isinstance(metrics.get("error_message"), str) and bool(metrics["error_message"]), "Invalid failure metrics")
        require(a["status"] == b["status"] and a["error_message"] == b["error_message"] == metrics["error_message"],
                "Failure artifact statuses/messages disagree")
        return paths
    require(metrics.get("parse_succeeded") is True and metrics.get("error_stage") is None and
            metrics.get("error_message") is None, "Extraction metrics indicate failure")
    require(metrics.get("node_counts") == {"graph_a": len(a["nodes"]), "graph_b": len(b["nodes"])}, "Metrics node counts disagree")
    oversized = metrics.get("oversized", {})
    require(oversized.get("truncated") is False and oversized.get("limits_are_warning_only") is True,
            "Graphs must be preserved without truncation")
    for kind, graph in (("graph_a", a), ("graph_b", b)):
        require(metrics.get("edge_counts", {}).get(kind) == len(graph["edges"]), "Metrics edge counts disagree")
        require(oversized.get(kind) is (graph["status"] == "OVERSIZED_GRAPH"), "Oversized flag mismatch")
    for name, edge_type in (("AST", 0), ("CFG", 1), ("DATA_DEP", 2)):
        statistics = metrics.get("edge_statistics", {}).get(name, {})
        counters = [statistics.get(key) for key in ("raw_count", "unmappable_count", "duplicate_edges_dropped", "self_loop_edges_dropped", "kept_count")]
        require(all(type(value) is int and value >= 0 for value in counters), "Missing edge handling statistics")
        require(counters[0] == sum(counters[1:]) and counters[-1] == sum(edge["type"] == edge_type for edge in b["edges"]),
                "Edge handling statistics disagree")
        require(metrics.get("edge_counts", {}).get("graph_b_by_type", {}).get(name) == counters[-1], "Typed edge counts disagree")
    log_path = directory / "stages.jsonl"
    try:
        events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    except (OSError, ValueError) as error:
        raise ManifestValidationError("Missing stage audit logs") from error
    for stage in ("parse", "extract"):
        finished = [event for event in events if event.get("stage") == stage and event.get("status") != "STARTED"]
        require(len(finished) == 1 and finished[0].get("status") == "SUCCESS" and
                finished[0].get("exit_code") == 0 and isinstance(finished[0].get("command"), list) and
                bool(finished[0]["command"]) and isinstance(finished[0].get("stdout"), str) and
                isinstance(finished[0].get("stderr"), str), "Stage did not finish successfully with audit evidence")
    extraction = next(event for event in events if event.get("stage") == "extract" and event.get("status") == "SUCCESS")
    logs = extraction["stdout"] + "\n" + extraction["stderr"]
    method = metrics.get("joern_method_full_name")
    require(isinstance(method, str) and bool(method), "Missing Joern method identity")
    require(re.search(r"(?:^|[.:])" + re.escape(function_name) + r"(?=$|[:(])", method) is not None,
            "Joern method identity disagrees with resolved function")
    for field in ("dataflow_pass_attempted", "dataflow_pass_completed", "dataflow_applied_after", "dataflow_applied_before"):
        require(type(metrics.get(field)) is bool, f"Missing dataflow evidence: {field}")
    require(not metrics["dataflow_pass_completed"] or metrics["dataflow_applied_after"], "Contradictory overlay evidence")
    expected = _normalize_ddg_status(dataflow_pass_attempted=metrics["dataflow_pass_attempted"],
        dataflow_pass_completed=metrics["dataflow_pass_completed"], method_full_name=method,
        ddg_edge_count=sum(edge["type"] == 2 for edge in b["edges"]), joern_logs=logs)
    require(a.get("ddg_status") == "NOT_COMPUTED" and b.get("ddg_status") == expected and
            metrics.get("ddg_status") == expected, "DDG status contradicts evidence")
    require(metrics.get("ddg_completion_evidence") == _ddg_method_log_evidence(method, logs), "DDG log evidence mismatch")
    return paths


class DriverRunError(ManifestValidationError):
    """Run stopped; summary and all staging remain available for diagnosis."""

    def __init__(self, message: str, summary_path: Path):
        super().__init__(f"{message}; audit summary: {summary_path}")
        self.summary_path = summary_path


def _publish_sample(staging: Path, output_dir: Path, sample_id: str) -> None:
    """Publish one accepted sample atomically; originals always remain in staging."""
    pending = staging.parent / (sample_id + ".publication")
    pending.mkdir()
    for name in (f"{sample_id}.graph_a.json", f"{sample_id}.graph_b.json",
                 f"{sample_id}.metrics.json", "identity.json", "stages.jsonl"):
        shutil.copyfile(staging / name, pending / name)
    output_dir.mkdir(exist_ok=True)
    destination = output_dir / sample_id
    if destination.exists():
        raise ManifestValidationError(f"Refusing to overwrite sample output: {destination}")
    pending.rename(destination)


def run_full_extraction(
    rows: list[dict],
    records_by_index: dict[int, dict],
    results: list[SampleResult],
    output_dir: Path,
    schema_config: Path,
) -> Path:
    """Controlled extraction: stop on first failure, retain staging, publish per sample.

    Only an explicitly authorized extraction run may call this entry point.
    The results argument is retained for compatibility; validation is repeated.
    """
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise ManifestValidationError(f"Refusing to overwrite existing output: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    run_dir = output_dir.parent / f".{output_dir.name}-run-{uuid.uuid4().hex}"
    run_dir.mkdir()
    summary_path = run_dir / "run_summary.json"
    entries = [{"sample_id": row.get("sample_id"), "status": "NOT_RUN"} for row in rows]
    summary = {"status": "RUNNING", "output_dir": str(output_dir), "samples": entries}

    def save_summary():
        staged = summary_path.with_suffix(".pending")
        staged.write_text(json.dumps(summary, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        os.replace(staged, summary_path)

    save_summary()
    config = None
    for position, row in enumerate(rows):
        entry = entries[position]
        # Untrusted IDs are never used as staging directory names.
        staging = run_dir / f"sample-{position:03d}"
        staging.mkdir()
        log_path = staging / "stages.jsonl"
        phase = "validation"
        try:
            result = validate_samples([row], records_by_index, None, True)[0]
            if sum(other.get("sample_id") == row.get("sample_id") for other in rows) != 1:
                raise ManifestValidationError("Duplicate sample_id")
            entry["validation"] = result.as_row()
            if not result.ok:
                raise ManifestValidationError("; ".join(result.errors))
            record = records_by_index[result.index]
            phase = "method_resolution"
            function_name = resolve_function_name(record["func"])
            from src.graph.joern import JoernConfig, JoernExtractor
            from src.utils.config import load_config
            if config is None:
                limits = load_config(schema_config).get("size_limits", {})
                config = JoernConfig(max_nodes=int(limits.get("max_nodes", 1000)),
                    max_edges=int(limits.get("max_edges", 3000)), timeout_sec=int(limits.get("timeout_sec", 120)))
            arguments = extraction_arguments(row, record, function_name)
            source_path = staging / "source.c"
            source_path.write_bytes(record["func"].encode("utf-8"))
            inspect.signature(JoernExtractor.extract).bind(None, source_path, staging, **arguments)
            identity = {"manifest_entry": row, "dataset_index": result.index,
                        "source_sha256": source_sha256(record), "function_name": function_name,
                        "configuration": vars(config)}
            (staging / "identity.json").write_text(json.dumps(identity, ensure_ascii=True, indent=2), encoding="utf-8")
            _event(log_path, stage=phase, status="SUCCESS", function_name=function_name,
                   dataset_index=result.index, source_sha256=identity["source_sha256"])
            phase = "extraction"
            extractor = _make_extractor(config, log_path)
            extracted = extractor.extract(source_path, staging, **arguments)
            phase = "acceptance"
            validate_artifacts(staging, row, record, function_name, config)
            if extracted.report.get("status") not in SUCCESS_STATUSES:
                raise ManifestValidationError("Extractor result reports failure")
            entry["extraction_status"] = extracted.report["status"]
            _event(log_path, stage="acceptance", status="SUCCESS")
            phase = "publication"
            _publish_sample(staging, output_dir, row["sample_id"])
            entry.update(status="SUCCESS", artifacts=str(output_dir / row["sample_id"]), staging=str(staging))
            save_summary()
        except Exception as error:
            # No later sample runs; successful prior publications and all staging survive.
            entry.update(status="FAILED", failed_stage=phase, error=str(error), staging=str(staging))
            try:
                _event(log_path, stage=phase, status="FAILED", error=str(error))
            except OSError as log_error:
                entry["log_error"] = str(log_error)
            try:
                if phase in {"extraction", "acceptance"} and config is not None:
                    try:
                        validate_artifacts(staging, row, record, function_name, config, failure=True)
                        entry["failure_artifacts"] = "VALID_FAILURE_SCHEMA"
                    except Exception as failure_error:
                        entry["failure_artifacts"] = "INCOMPLETE_OR_INVALID"
                        entry["failure_artifact_error"] = str(failure_error)
                quarantine = run_dir / "quarantine"
                quarantine.mkdir(exist_ok=True)
                destination = quarantine / staging.name
                staging.rename(destination)
                entry["quarantine"] = str(destination)
                entry["staging"] = str(destination)
                if phase == "publication":
                    partial = run_dir / (row["sample_id"] + ".publication")
                    if partial.exists():
                        retained_partial = destination / "publication_partial"
                        partial.rename(retained_partial)
                        entry["publication_partial"] = str(retained_partial)
            except Exception as retention_error:
                # The original staging is persistent, even if a rename/log write fails.
                entry["retention_error"] = str(retention_error)
            summary["status"] = "FAILED"
            try:
                save_summary()
            except OSError as summary_error:
                # A full disk cannot be made auditable by deleting completed work.
                entry["summary_error"] = str(summary_error)
            raise DriverRunError(f"Stopped at sample {position}: {phase}: {error}", summary_path) from error
    summary["status"] = "SUCCESS"
    save_summary()
    return summary_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--schema-config", type=Path, default=ROOT / "configs" / "graph" / "schema_spec.yaml")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--enrich-manifest", action="store_true", help="Thêm cột source_sha256 rồi dừng")
    parser.add_argument("--backup", type=Path, help="Trước khi enrich, copy manifest gốc tới đây")
    mode.add_argument("--validate-only", action="store_true", help="Validate samples without importing Joern")
    mode.add_argument("--preflight", action="store_true", help="Check input identity, method resolution and real signature; no Joern execution")
    mode.add_argument("--extract", action="store_true", help="Full extraction; requires separate Checkpoint 5 approval")
    parser.add_argument("--evidence-out", type=Path, help="Ghi evidence table (markdown) ra file UTF-8")
    return parser.parse_args()


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    try:
        if args.enrich_manifest:
            enrich_manifest(args.manifest, args.dataset, args.backup)
            print(f"Enriched manifest: {args.manifest}")
            return 0
        rows = read_manifest(args.manifest)
        indices = set()
        for row in rows:
            indices.add(parse_sample_id(row["sample_id"]))
        records = load_records_at_indices(args.dataset, indices)
        results = validate_samples(rows, records, total_records=None, require_hash=True)
        if args.preflight:
            checks = preflight_samples(rows, records)
            evidence = json.dumps(checks, ensure_ascii=True, indent=2) + "\n"
            if args.evidence_out:
                args.evidence_out.write_text(evidence, encoding="utf-8")
            print(evidence)
            return 0 if all(entry["result"] == "PASS" for entry in checks) else 1
        evidence = render_evidence_markdown(results)
        if args.evidence_out:
            args.evidence_out.parent.mkdir(parents=True, exist_ok=True)
            args.evidence_out.write_text(evidence, encoding="utf-8")
        print(evidence)
        failed = [result for result in results if not result.ok]
        if args.validate_only:
            print("--validate-only: không gọi Joern.")
            return 0 if not failed else 1
        if failed:
            print(f"{len(failed)} mẫu lỗi validation — full run yêu cầu 30/30 pass. Dừng.", file=sys.stderr)
            return 1
        summary = run_full_extraction(rows, records, results, args.output_dir, args.schema_config)
        print(f"Batch summary: {summary}")
        return 0
    except (ManifestValidationError, OSError, UnicodeError) as error:
        print(f"FAIL-CLOSED: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

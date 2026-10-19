"""Joern integration and Tier-1 graph serialization.

Joern owns parsing and CPG relation extraction. This module maps its structured
payload into the project schema without truncating nodes or edges.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.graph.schema_policy import normalize_code_token

DDG_STATUSES = {
    "NOT_COMPUTED",
    "EDGES_PRESENT",
    "INCOMPLETE",
}
_SAFE_SAMPLE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_COMMENT_NODE_LABELS = {"COMMENT"}


@dataclass(frozen=True)
class JoernConfig:
    """Process-local Joern runtime settings."""

    executable: str = "joern"
    parse_executable: str = "joern-parse"
    java_home: str | None = None
    wsl_distro: str = "Ubuntu"
    timeout_sec: int = 120
    max_nodes: int = 1000
    max_edges: int = 3000


@dataclass(frozen=True)
class ExtractionResult:
    """Output graph paths and the measured run report."""

    graph_a_path: Path
    graph_b_path: Path
    report_path: Path
    report: dict[str, Any]


class JoernExecutionError(RuntimeError):
    """A Joern command failed at a named extraction stage."""

    def __init__(self, stage: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage


def _joern_script() -> str:
    return r'''import io.shiftleft.codepropertygraph.generated.EdgeTypes
import io.shiftleft.semanticcpg.language.*
import io.joern.dataflowengineoss.language.*
import java.nio.file.{Files, Paths}
import org.apache.logging.log4j.core.config.Configurator
import org.apache.logging.log4j.Level

@main def exec(cpgFile: String, outFile: String, functionName: String) = {
  Configurator.setRootLevel(Level.INFO)
  importCpg(cpgFile, enhance = false)
  def prepareLayer(name: String)(applyLayer: => Any): Unit = {
    val alreadyPresent = cpg.metaData.overlays.contains(name)
    println("JOERN_LAYER " + ujson.write(ujson.Obj(
      "layer" -> name, "status" -> "STARTED", "already_present" -> alreadyPresent,
      "overlays" -> ujson.Arr.from(cpg.metaData.overlays))))
    if (!alreadyPresent) applyLayer
    require(cpg.metaData.overlays.contains(name), s"Required overlay missing: $name")
    println("JOERN_LAYER " + ujson.write(ujson.Obj(
      "layer" -> name, "status" -> "SUCCESS",
      "overlays" -> ujson.Arr.from(cpg.metaData.overlays))))
  }
  prepareLayer("base") { run.base }
  prepareLayer("typerel") { run.typerelations }
  prepareLayer("callgraph") { run.callgraph }
  prepareLayer("controlflow") { run.controlflow }

  val methods = cpg.method.nameExact(functionName).l
  if (methods.size != 1) {
    throw new RuntimeException(s"Expected exactly one method named $functionName, found ${methods.size}")
  }
  val method = methods.head
  println("JOERN_SELECTED_METHOD " + ujson.write(ujson.Obj(
    "name" -> method.name, "full_name" -> method.fullName, "id" -> method.id.toString)))
  // ossdataflow traverses the whole CPG, including captured parameters in lambdas.
  // Inspect built-in linking results; never fabricate or silently discard REF edges.
  val unresolvedMethodRefs = cpg.methodRef.l.filter { ref =>
    val targets = ref.outE(EdgeTypes.REF).l.map(_.dst).filter(_.label == "METHOD")
    val targetName = if (targets.size == 1) Some(ref.referencedMethod.fullName) else None
    val resolved = targetName.contains(ref.methodFullName)
    println("JOERN_METHOD_REF " + ujson.write(ujson.Obj(
      "id" -> ref.id.toString, "method_full_name" -> ref.methodFullName,
      "method_target_count" -> targets.size, "resolved" -> resolved,
      "target_full_name" -> targetName.map(ujson.Str(_)).getOrElse(ujson.Null))))
    !resolved
  }
  println("JOERN_METHOD_REF_SUMMARY " + ujson.write(ujson.Obj(
    "scope" -> "whole_cpg", "total" -> cpg.methodRef.l.size,
    "unresolved" -> unresolvedMethodRefs.size)))
  require(unresolvedMethodRefs.isEmpty,
    s"Unresolved mandatory METHOD_REF targets: ${unresolvedMethodRefs.map(_.id).mkString(",")}")
  val beforeDataflow = cpg.metaData.overlays.contains("dataflowOss")
  val beforeDdgCount = method.ast.l.flatMap(_.outE(EdgeTypes.REACHING_DEF).l).size
  val dataflowPassAttempted = !beforeDataflow
  var dataflowPassCompleted = false
  if (dataflowPassAttempted) {
    prepareLayer("dataflowOss") { run.ossdataflow }
    dataflowPassCompleted = cpg.metaData.overlays.contains("dataflowOss")
  }
  val dataflowApplied = cpg.metaData.overlays.contains("dataflowOss")

  val astNodes = method.ast.l
  def edgePairs(edgeType: String) = astNodes.flatMap { node =>
    node.outE(edgeType).l.map(edge => (edge.src.id, edge.dst.id))
  }
  def edgeJson(edges: Seq[(Long, Long)]) = ujson.Arr.from(edges.map { case (src, dst) =>
    ujson.Obj("src" -> ujson.Str(src.toString), "dst" -> ujson.Str(dst.toString))
  })
  def optionalNumber(value: Option[Int]) = value.map(x => ujson.Num(x.toDouble)).getOrElse(ujson.Null)

  val astEdges = edgePairs(EdgeTypes.AST)
  val cfgEdges = edgePairs(EdgeTypes.CFG)
  val ddgEdges = edgePairs(EdgeTypes.REACHING_DEF)
  val nodes = ujson.Arr.from(astNodes.map { node =>
    ujson.Obj(
      "joern_id" -> ujson.Str(node.id.toString),
      "label" -> ujson.Str(node.label),
      "code" -> ujson.Str(node.code),
      "line_number" -> optionalNumber(node.lineNumber),
      "column_number" -> optionalNumber(node.columnNumber)
    )
  })
  val result = ujson.Obj(
    "function_name" -> ujson.Str(functionName),
    "method_full_name" -> ujson.Str(method.fullName),
    "method_code" -> ujson.Str(method.code),
    "dataflow_applied_before" -> ujson.Bool(beforeDataflow),
    "ddg_edge_count_before" -> ujson.Num(beforeDdgCount.toDouble),
    "dataflow_applied_after" -> ujson.Bool(dataflowApplied),
    "dataflow_pass_attempted" -> ujson.Bool(dataflowPassAttempted),
    "dataflow_pass_completed" -> ujson.Bool(dataflowPassCompleted),
    "nodes" -> nodes,
    "ast_edges" -> edgeJson(astEdges),
    "cfg_edges" -> edgeJson(cfgEdges),
    "ddg_edges" -> edgeJson(ddgEdges)
  )
  Files.writeString(Paths.get(outFile), ujson.write(result))
}'''


def _lexical_tokens(code: str) -> list[tuple[str, bool]]:
    """Split C/C++ source snippets while retaining literals and dropping comments."""
    tokens: list[tuple[str, bool]] = []

    def consume_quoted(quote_index: int) -> int:
        quote = code[quote_index]
        i = quote_index + 1
        escaped = False
        while i < len(code):
            current = code[i]
            if escaped:
                escaped = False
            elif current == "\\":
                escaped = True
            elif current == quote:
                return i + 1
            i += 1
        return len(code)

    i = 0
    while i < len(code):
        ch = code[i]
        if ch.isspace():
            i += 1
            continue
        if ch == "/" and i + 1 < len(code) and code[i + 1] == "/":
            i += 2
            while i < len(code) and code[i] not in "\r\n":
                i += 1
            continue
        if ch == "/" and i + 1 < len(code) and code[i + 1] == "*":
            i += 2
            while i + 1 < len(code):
                if code[i] == "*" and code[i + 1] == "/":
                    i += 2
                    break
                i += 1
            else:
                i = len(code)
            continue

        raw_prefix = next(
            (
                prefix
                for prefix in ("u8R", "uR", "UR", "LR", "R")
                if code.startswith(prefix, i)
                and code.startswith('"', i + len(prefix))
            ),
            None,
        )
        if raw_prefix is not None:
            start = i
            quote_index = i + len(raw_prefix)
            delimiter_end = code.find("(", quote_index + 1)
            if delimiter_end < 0:
                i = len(code)
            else:
                delimiter = code[quote_index + 1 : delimiter_end]
                closing = ")" + delimiter + '"'
                closing_start = code.find(closing, delimiter_end + 1)
                i = len(code) if closing_start < 0 else closing_start + len(closing)
            tokens.append((code[start:i], False))
            continue
        string_prefix = next(
            (
                prefix
                for prefix in ("u8", "u", "U", "L")
                if code.startswith(prefix, i)
                and i + len(prefix) < len(code)
                and code[i + len(prefix)] in {'"', "'"}
            ),
            None,
        )
        if ch in {'"', "'"} or string_prefix is not None:
            start = i
            quote_index = i if string_prefix is None else i + len(string_prefix)
            i = consume_quoted(quote_index)
            tokens.append((code[start:i], False))
            continue
        if ch.isalpha() or ch == "_":
            start = i
            i += 1
            while i < len(code) and (code[i].isalnum() or code[i] == "_"):
                i += 1
            tokens.append((code[start:i], False))
            continue
        if ch.isdigit() or (ch == "." and i + 1 < len(code) and code[i + 1].isdigit()):
            start = i
            i += 1
            while i < len(code):
                current = code[i]
                if current.isalnum() or current in {"_", "."}:
                    i += 1
                elif current in {"+", "-"} and code[i - 1] in "eEpP":
                    i += 1
                else:
                    break
            tokens.append((code[start:i], False))
            continue
        match = None
        for operator in sorted(
            (
                "<<=",
                ">>=",
                "->*",
                "<<",
                ">>",
                "<=",
                ">=",
                "==",
                "!=",
                "&&",
                "||",
                "++",
                "--",
                "->",
                "+=",
                "-=",
                "*=",
                "/=",
                "%=",
                "&=",
                "|=",
                "^=",
                "::",
                ".*",
                "##",
                "...",
                "<",
                ">",
                "!",
                "~",
                "+",
                "-",
                "*",
                "/",
                "%",
                "^",
                "&",
                "|",
                "=",
                ";",
                "(",
                ")",
                "{",
                "}",
                "[",
                "]",
                ":",
                "?",
                ".",
                ",",
                "#",
            ),
            key=len,
            reverse=True,
        ):
            if code.startswith(operator, i):
                match = operator
                break
        if match is not None:
            tokens.append((match, False))
            i += len(match)
            continue
        tokens.append((ch, False))
        i += 1
    return tokens


def _normalized_code(
    code: str,
    *,
    project_name: str | None,
    commit_id: str | None,
) -> str:
    normalized = [
        part
        for token, is_comment in _lexical_tokens(code)
        for part in normalize_code_token(
            token,
            is_comment=is_comment,
            project_name=project_name,
            commit_id=commit_id,
        )
    ]
    return " ".join(normalized) or "<UNK>"


def _camel_label(label: str) -> str:
    return "".join(part.capitalize() for part in label.split("_") if part)


def _is_literal_token(token: str) -> bool:
    """Return True when a lexer token is a C/C++ string or char literal."""
    prefix = 0
    while prefix < len(token) and token[prefix] in "uULR8":
        prefix += 1
    return prefix < len(token) and token[prefix] in {'"', "'"}


# Joern 4.0.654 c2cpg exposes only ``--language c`` (verified via
# ``joern-parse --list-languages``); C vs C++ is selected by file extension.
_LANGUAGE_EXTENSIONS = {"c": ".c", "cpp": ".cpp"}

# C++-only keywords that are also rarely used as C identifiers. Deliberately
# excludes ``new``/``delete``/``try``/``throw``/``operator``, which are legal
# and reasonably common C identifiers, and ``struct``, which plain C uses.
_CPP_ONLY_KEYWORDS = frozenset(
    {
        "catch",
        "class",
        "constexpr",
        "explicit",
        "friend",
        "mutable",
        "namespace",
        "noexcept",
        "this",
        "typename",
        "virtual",
    }
)


def _detect_language(source_text: str) -> str:
    """Classify a function source as "c" or "cpp" from lexical evidence.

    The scan runs on the token stream with comments and string/char literals
    already removed, so C++-looking text inside literals cannot flip the
    result. Raises ``ValueError`` when no code tokens exist, because parsing a
    source of unknown language would silently force C.
    """
    tokens = [
        token
        for token, _ in _lexical_tokens(source_text)
        if not _is_literal_token(token)
    ]
    if not tokens:
        raise ValueError(
            "Cannot determine source language: no code tokens "
            "(source is empty or comment-only)"
        )
    if "::" in tokens:
        return "cpp"
    for index, token in enumerate(tokens):
        if (
            token == "template"
            and index + 1 < len(tokens)
            and tokens[index + 1] == "<"
        ):
            return "cpp"
        if token in _CPP_ONLY_KEYWORDS:
            return "cpp"
    return "c"


def _ddg_method_log_evidence(
    method_full_name: str | None,
    joern_logs: str,
) -> dict[str, bool]:
    if not method_full_name:
        return {
            "method_start_logged": False,
            "method_definition_count_logged": False,
            "method_skip_logged": False,
        }
    method_log = re.escape(method_full_name)
    return {
        "method_start_logged": bool(
            re.search(
                rf"Calculating reaching definitions for:\s*{method_log}\s+in\s",
                joern_logs,
            )
        ),
        "method_definition_count_logged": bool(
            re.search(
                rf"Number of definitions for {method_log}:\s*\d+",
                joern_logs,
            )
        ),
        "method_skip_logged": bool(
            re.search(
                rf"{method_log} has more than \d+ definitions",
                joern_logs,
            )
        ),
    }


def _normalize_ddg_status(
    *,
    dataflow_pass_attempted: bool,
    dataflow_pass_completed: bool,
    method_full_name: str | None,
    ddg_edge_count: int,
    joern_logs: str,
) -> str:
    """Classify DDG reliability fail-safely against Joern 4.0.654 runtime facts.

    Verified against Joern 4.0.654: ReachingDefPass emits no per-method
    completion log, so no status below can claim a method was fully analyzed.
    ``EDGES_PRESENT`` only records that at least one valid DDG edge was
    observed under the strongest log evidence currently available; it does
    not prove the whole method was processed. Zero observed edges is never
    read as "no data dependence" and maps to ``INCOMPLETE``.
    """
    if not dataflow_pass_attempted:
        return "NOT_COMPUTED"
    if not dataflow_pass_completed or not method_full_name:
        return "INCOMPLETE"
    evidence = _ddg_method_log_evidence(method_full_name, joern_logs)
    if (
        not evidence["method_start_logged"]
        or not evidence["method_definition_count_logged"]
        or evidence["method_skip_logged"]
    ):
        return "INCOMPLETE"
    if ddg_edge_count:
        return "EDGES_PRESENT"
    return "INCOMPLETE"


def _graph_status(node_count: int, edge_count: int, config: JoernConfig) -> str:
    if node_count > config.max_nodes or edge_count > config.max_edges:
        return "OVERSIZED_GRAPH"
    return "SUCCESS"


def _map_payload(
    payload: dict[str, Any],
    *,
    sample_id: str,
    cwe: str | None,
    project_wise_split: str | None,
    seen_project_split: str | None,
    project_name: str | None,
    commit_id: str | None,
    source_text: str,
    config: JoernConfig,
    joern_logs: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    raw_nodes = payload.get("nodes")
    if not isinstance(raw_nodes, list):
        raise ValueError("Joern payload has no node array")
    ids = [str(node["joern_id"]) for node in raw_nodes]
    if len(set(ids)) != len(ids):
        raise ValueError("Joern payload contains duplicate Joern node IDs")

    id_to_node = {str(node["joern_id"]): node for node in raw_nodes}
    raw_ast_edges = payload.get("ast_edges", [])
    if not isinstance(raw_ast_edges, list):
        raise ValueError("Joern AST edges are not an array")
    parents: dict[str, list[str]] = defaultdict(list)
    for edge in raw_ast_edges:
        parents[str(edge["dst"])].append(str(edge["src"]))

    excluded_comment_ids = {
        str(node["joern_id"])
        for node in raw_nodes
        if str(node.get("label", "")).upper() in _COMMENT_NODE_LABELS
    }
    selected_nodes = [
        node for node in raw_nodes if str(node["joern_id"]) not in excluded_comment_ids
    ]
    joern_to_local = {
        str(node["joern_id"]): node_id for node_id, node in enumerate(selected_nodes)
    }
    resolved_lines: dict[str, int] = {}
    for node in raw_nodes:
        node_id = str(node["joern_id"])
        line = node.get("line_number")
        visited = {node_id}
        ancestors = list(parents.get(node_id, []))
        while line is None and ancestors:
            ancestor_id = ancestors.pop(0)
            if ancestor_id in visited:
                continue
            visited.add(ancestor_id)
            ancestor = id_to_node.get(ancestor_id)
            if ancestor is None:
                continue
            line = ancestor.get("line_number")
            if line is None:
                ancestors[0:0] = parents.get(ancestor_id, [])
        resolved_lines[node_id] = int(line) if line is not None else 1

    # The schema denominator is the function source string used as extraction
    # input, never Joern's method.code, which c2cpg can truncate (observed at
    # #ifdef regions) and which would then push rel_line_number past 1.0.
    total_lines = max(1, len(source_text.splitlines()))
    nodes: list[dict[str, Any]] = []
    for node in selected_nodes:
        joern_id = str(node["joern_id"])
        line_number = resolved_lines[joern_id]
        if not 1 <= line_number <= total_lines:
            raise ValueError(
                f"Node line_number {line_number} is outside the function "
                f"source range 1..{total_lines}"
            )
        nodes.append(
            {
                "id": joern_to_local[joern_id],
                "node_type": _camel_label(str(node.get("label", "UNKNOWN"))),
                "code_token": _normalized_code(
                    str(node.get("code", "")),
                    project_name=project_name,
                    commit_id=commit_id,
                ),
                "line_number": line_number,
                "rel_line_number": line_number / total_lines,
            }
        )

    edge_stats: dict[str, dict[str, Any]] = {}

    def map_edges(name: str, raw_edges: Any, edge_type: int) -> list[dict[str, int]]:
        if not isinstance(raw_edges, list):
            raise ValueError(f"Joern {name} edges are not an array")
        raw_mapped: list[tuple[int, int, int]] = []
        unmappable: Counter[str] = Counter()
        for edge in raw_edges:
            source = str(edge.get("src"))
            target = str(edge.get("dst"))
            if source not in joern_to_local or target not in joern_to_local:
                reasons = []
                if source not in joern_to_local:
                    reasons.append(
                        "comment_node_excluded"
                        if source in excluded_comment_ids
                        else "source_not_in_ast_domain"
                    )
                if target not in joern_to_local:
                    reasons.append(
                        "comment_node_excluded"
                        if target in excluded_comment_ids
                        else "target_not_in_ast_domain"
                    )
                unmappable[";".join(reasons)] += 1
                continue
            raw_mapped.append(
                (joern_to_local[source], joern_to_local[target], edge_type)
            )

        self_loops = sum(source == target for source, target, _ in raw_mapped)
        candidates = [
            edge for edge in raw_mapped if edge[0] != edge[1]
        ]
        counts = Counter(candidates)
        duplicates = sum(count - 1 for count in counts.values())
        unique = sorted(counts)
        edge_stats[name] = {
            "raw_count": len(raw_edges),
            "unmappable_count": sum(unmappable.values()),
            "unmappable_reasons": dict(sorted(unmappable.items())),
            "duplicate_edges_dropped": duplicates,
            "self_loop_edges_dropped": self_loops,
            "kept_count": len(unique),
        }
        return [
            {"src": source, "dst": target, "type": relation}
            for source, target, relation in unique
        ]

    ast_edges = map_edges("AST", raw_ast_edges, 0)
    cfg_edges = map_edges("CFG", payload.get("cfg_edges", []), 1)
    ddg_edges = map_edges("DATA_DEP", payload.get("ddg_edges", []), 2)
    method_full_name = payload.get("method_full_name")
    if not isinstance(method_full_name, str):
        method_full_name = None
    dataflow_pass_attempted = payload.get("dataflow_pass_attempted") is True
    dataflow_pass_completed = payload.get("dataflow_pass_completed") is True
    ddg_status = _normalize_ddg_status(
        dataflow_pass_attempted=dataflow_pass_attempted,
        dataflow_pass_completed=dataflow_pass_completed,
        method_full_name=method_full_name,
        ddg_edge_count=len(ddg_edges),
        joern_logs=joern_logs,
    )
    ddg_completion_evidence = _ddg_method_log_evidence(method_full_name, joern_logs)
    metadata = {
        "sample_id": sample_id,
        "cwe": cwe,
        "project_wise_split": project_wise_split,
        "seen_project_split": seen_project_split,
    }

    def make_record(graph_type: str, edges: list[dict[str, int]]) -> dict[str, Any]:
        return {
            **metadata,
            "graph_type": graph_type,
            "status": _graph_status(len(nodes), len(edges), config),
            "ddg_status": "NOT_COMPUTED" if graph_type == "graph_a" else ddg_status,
            "num_nodes": len(nodes),
            "num_edges": len(edges),
            "nodes": nodes,
            "edges": edges,
        }

    graph_a = make_record("graph_a", ast_edges)
    graph_b_edges = sorted(
        ast_edges + cfg_edges + ddg_edges,
        key=lambda edge: (edge["src"], edge["dst"], edge["type"]),
    )
    graph_b = make_record("graph_b", graph_b_edges)
    if graph_a["nodes"] != graph_b["nodes"]:
        raise ValueError("Graph A and Graph B node domains differ")
    if any(
        edge["src"] >= len(nodes) or edge["dst"] >= len(nodes)
        for record in (graph_a, graph_b)
        for edge in record["edges"]
    ):
        raise ValueError("Mapped graph edge endpoint is outside the node domain")
    metrics = {
        "ddg_status": ddg_status,
        "dataflow_applied_before": bool(payload.get("dataflow_applied_before")),
        "dataflow_applied_after": bool(payload.get("dataflow_applied_after")),
        "dataflow_pass_attempted": dataflow_pass_attempted,
        "dataflow_pass_completed": dataflow_pass_completed,
        "ddg_completion_evidence": ddg_completion_evidence,
        "edge_statistics": edge_stats,
        "excluded_comment_nodes": len(excluded_comment_ids),
        "oversized": {
            "graph_a": graph_a["status"] == "OVERSIZED_GRAPH",
            "graph_b": graph_b["status"] == "OVERSIZED_GRAPH",
            "limits_are_warning_only": True,
            "truncated": False,
        },
        "node_counts": {"graph_a": len(nodes), "graph_b": len(nodes)},
        "edge_counts": {
            "graph_a": len(graph_a["edges"]),
            "graph_b": len(graph_b["edges"]),
            "graph_b_by_type": {
                "AST": len(ast_edges),
                "CFG": len(cfg_edges),
                "DATA_DEP": len(ddg_edges),
            },
        },
    }
    return graph_a, graph_b, metrics


class JoernExtractor:
    """Extract one function to Graph A and Graph B using Joern."""

    name = "joern"

    def __init__(self, config: JoernConfig | None = None) -> None:
        self.config = config or JoernConfig()
        if self.config.timeout_sec <= 0:
            raise ValueError("timeout_sec must be positive")
        if self.config.max_nodes < 0 or self.config.max_edges < 0:
            raise ValueError("Graph warning limits must be non-negative")

    def extract(
        self,
        source_path: Path,
        output_dir: Path,
        *,
        sample_id: str,
        function_name: str,
        cwe: str | None = None,
        project_wise_split: str | None = None,
        seen_project_split: str | None = None,
        project_name: str | None = None,
        commit_id: str | None = None,
    ) -> ExtractionResult:
        """Extract one source function and write both Tier-1 graph records.

        Metadata values are only copied from explicit arguments. Missing values
        remain JSON null; no labels or splits are inferred.
        """
        source_path = Path(source_path)
        output_dir = Path(output_dir)
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        if not _SAFE_SAMPLE_ID.fullmatch(sample_id) or sample_id in {".", ".."}:
            raise ValueError(f"Unsafe sample_id for output filenames: {sample_id!r}")
        if not function_name.strip():
            raise ValueError("function_name must not be empty")
        output_dir.mkdir(parents=True, exist_ok=True)
        graph_a_path = output_dir / f"{sample_id}.graph_a.json"
        graph_b_path = output_dir / f"{sample_id}.graph_b.json"
        report_path = output_dir / f"{sample_id}.metrics.json"
        started = time.perf_counter()
        parse_seconds: float | None = None
        extraction_seconds: float | None = None
        report: dict[str, Any] = {
            "sample_id": sample_id,
            "source": str(source_path),
            "function_name": function_name,
            "joern_version": None,
            "detected_language": None,
            "parse_succeeded": False,
            "status": None,
            "error_stage": None,
            "error_message": None,
            "parse_seconds": None,
            "extraction_seconds": None,
            "total_seconds": None,
            "peak_memory_bytes": None,
            "memory_measurement": "not_measured",
        }

        try:
            with tempfile.TemporaryDirectory(prefix="joern-tier1-") as temporary:
                temp_dir = Path(temporary)
                source_text = source_path.read_text(encoding="utf-8")
                try:
                    language = _detect_language(source_text)
                except ValueError as error:
                    raise JoernExecutionError("language_detection", str(error)) from error
                report["detected_language"] = language
                local_source = temp_dir / (
                    f"{source_path.stem}{_LANGUAGE_EXTENSIONS[language]}"
                )
                shutil.copyfile(source_path, local_source)
                cpg_path = temp_dir / "source.cpg"
                payload_path = temp_dir / "joern_payload.json"
                script_path = temp_dir / "extract.sc"
                script_path.write_text(_joern_script(), encoding="utf-8")

                parse_started = time.perf_counter()
                self._run_stage(
                    "parse",
                    [
                        self.config.parse_executable,
                        "--language",
                        "c",
                        "--nooverlays",
                        "--output",
                        str(cpg_path),
                        str(local_source),
                    ],
                    temp_dir,
                )
                parse_seconds = time.perf_counter() - parse_started
                report["parse_succeeded"] = cpg_path.is_file()
                if not report["parse_succeeded"]:
                    raise JoernExecutionError(
                        "parse", "joern-parse returned successfully but wrote no CPG"
                    )

                extraction_started = time.perf_counter()
                completed = self._run_stage(
                    "extract",
                    [
                        self.config.executable,
                        "--script",
                        str(script_path),
                        "--param",
                        f"cpgFile={cpg_path}",
                        "--param",
                        f"outFile={payload_path}",
                        "--param",
                        f"functionName={function_name}",
                    ],
                    temp_dir,
                )
                extraction_seconds = time.perf_counter() - extraction_started
                if not payload_path.is_file():
                    raise JoernExecutionError(
                        "extract",
                        "Joern completed without writing its structured payload",
                    )
                raw_payload = json.loads(payload_path.read_text(encoding="utf-8"))
                if not isinstance(raw_payload, dict):
                    raise JoernExecutionError(
                        "extract", "Joern payload root must be a JSON object"
                    )
                graph_a, graph_b, metrics = _map_payload(
                    raw_payload,
                    sample_id=sample_id,
                    cwe=cwe,
                    project_wise_split=project_wise_split,
                    seen_project_split=seen_project_split,
                    project_name=project_name,
                    commit_id=commit_id,
                    source_text=source_text,
                    config=self.config,
                    joern_logs=(completed.stdout or "") + "\n" + (completed.stderr or ""),
                )
                self._write_json(graph_a_path, graph_a)
                self._write_json(graph_b_path, graph_b)
                report.update(metrics)
                report["status"] = graph_b["status"]
                report["joern_method_full_name"] = raw_payload.get("method_full_name")
                report["graph_a_json_bytes"] = graph_a_path.stat().st_size
                report["graph_b_json_bytes"] = graph_b_path.stat().st_size
        except subprocess.TimeoutExpired as error:
            message = f"Joern command timed out after {self.config.timeout_sec}s"
            self._write_failure_outputs(
                graph_a_path,
                graph_b_path,
                report,
                sample_id=sample_id,
                cwe=cwe,
                project_wise_split=project_wise_split,
                seen_project_split=seen_project_split,
                status="TIMEOUT_ERROR",
                stage="timeout",
                message=message,
            )
            raise JoernExecutionError("timeout", message) from error
        except JoernExecutionError as error:
            status = "PARSE_ERROR" if error.stage == "parse" else "AST_EXTRACTION_ERROR"
            self._write_failure_outputs(
                graph_a_path,
                graph_b_path,
                report,
                sample_id=sample_id,
                cwe=cwe,
                project_wise_split=project_wise_split,
                seen_project_split=seen_project_split,
                status=status,
                stage=error.stage,
                message=str(error),
            )
            raise
        except (json.JSONDecodeError, ValueError, KeyError, TypeError) as error:
            message = f"Invalid Joern extraction payload: {error}"
            self._write_failure_outputs(
                graph_a_path,
                graph_b_path,
                report,
                sample_id=sample_id,
                cwe=cwe,
                project_wise_split=project_wise_split,
                seen_project_split=seen_project_split,
                status="AST_EXTRACTION_ERROR",
                stage="payload_mapping",
                message=message,
            )
            raise JoernExecutionError("payload_mapping", message) from error
        except OSError as error:
            message = f"Joern runtime or filesystem error: {error}"
            self._write_failure_outputs(
                graph_a_path,
                graph_b_path,
                report,
                sample_id=sample_id,
                cwe=cwe,
                project_wise_split=project_wise_split,
                seen_project_split=seen_project_split,
                status="AST_EXTRACTION_ERROR",
                stage="runtime",
                message=message,
            )
            raise JoernExecutionError("runtime", message) from error
        finally:
            report["parse_seconds"] = parse_seconds
            report["extraction_seconds"] = extraction_seconds
            report["total_seconds"] = time.perf_counter() - started
            self._write_json(report_path, report)

        return ExtractionResult(graph_a_path, graph_b_path, report_path, report)

    def _run_stage(
        self, stage: str, command: list[str], working_dir: Path
    ) -> subprocess.CompletedProcess[str]:
        try:
            if os.name == "nt":
                completed = self._run_wsl(stage, command, working_dir)
            else:
                env = os.environ.copy()
                if self.config.java_home:
                    env["JAVA_HOME"] = self.config.java_home
                    env["PATH"] = (
                        str(Path(self.config.java_home) / "bin")
                        + os.pathsep
                        + env.get("PATH", "")
                    )
                if stage == "extract":
                    env["SL_LOGGING_LEVEL"] = "INFO"
                completed = subprocess.run(
                    command,
                    cwd=working_dir,
                    env=env,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=self.config.timeout_sec,
                )
        except FileNotFoundError as error:
            raise JoernExecutionError(
                stage, f"Executable not found while running {command[0]!r}: {error}"
            ) from error
        except subprocess.CalledProcessError as error:
            output = "\n".join(
                value
                for value in (
                    error.stdout if isinstance(error.stdout, str) else "",
                    error.stderr if isinstance(error.stderr, str) else "",
                )
                if value
            )
            raise JoernExecutionError(
                stage,
                f"Unable to prepare WSL command: {error}; {output[-12000:]}",
            ) from error
        if completed.returncode != 0:
            output = "\n".join(
                value for value in (completed.stdout, completed.stderr) if value
            )
            raise JoernExecutionError(
                stage,
                f"Command failed (exit {completed.returncode}): "
                f"{shlex.join(command)}\n{output[-12000:]}",
            )
        return completed

    def _run_wsl(
        self, stage: str, command: list[str], working_dir: Path
    ) -> subprocess.CompletedProcess[str]:
        wsl = shutil.which("wsl.exe") or shutil.which("wsl")
        if wsl is None:
            raise FileNotFoundError("wsl.exe is required to invoke the WSL Joern runtime")
        wsl_dir = self._to_wsl_path(wsl, working_dir)
        wsl_command: list[str] = []
        for argument in command:
            key, separator, value = argument.partition("=")
            if separator and re.match(r"^[A-Za-z]:[\\/]", value):
                argument = f"{key}={self._to_wsl_path(wsl, Path(value))}"
            elif re.match(r"^[A-Za-z]:[\\/]", argument):
                argument = self._to_wsl_path(wsl, Path(argument))
            wsl_command.append(argument)
        pieces = ["set -eu"]
        if self.config.java_home:
            pieces.append(f"export JAVA_HOME={shlex.quote(self.config.java_home)}")
            java_bin = self.config.java_home.rstrip("/") + "/bin"
            pieces.append(
                f"export PATH={shlex.quote(java_bin + ':/usr/local/bin:/usr/bin:/bin')}"
            )
        else:
            pieces.append('export JAVA_HOME="$HOME/jdk/jdk-21"')
            pieces.append(
                'export PATH="$HOME/jdk/jdk-21/bin:/usr/local/bin:/usr/bin:/bin"'
            )
        if stage == "extract":
            pieces.append("export SL_LOGGING_LEVEL=INFO")
        pieces.extend(
            [
                f"cd {shlex.quote(wsl_dir)}",
                shlex.join(wsl_command),
            ]
        )
        return subprocess.run(
            [
                wsl,
                "-d",
                self.config.wsl_distro,
                "--",
                "bash",
                "-lc",
                "; ".join(pieces),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=self.config.timeout_sec,
        )

    def _to_wsl_path(self, wsl: str, path: Path) -> str:
        escaped_path = str(path).replace("\\", "\\\\")
        converted = subprocess.run(
            [
                wsl,
                "-d",
                self.config.wsl_distro,
                "--",
                "wslpath",
                "-a",
                escaped_path,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if converted.returncode != 0:
            raise subprocess.CalledProcessError(
                converted.returncode,
                converted.args,
                output=converted.stdout,
                stderr=converted.stderr,
            )
        result = converted.stdout.strip()
        if not result:
            raise OSError(f"wslpath returned an empty path for {path}")
        return result

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _write_failure_outputs(
        self,
        graph_a_path: Path,
        graph_b_path: Path,
        report: dict[str, Any],
        *,
        sample_id: str,
        cwe: str | None,
        project_wise_split: str | None,
        seen_project_split: str | None,
        status: str,
        stage: str,
        message: str,
    ) -> None:
        metadata = {
            "sample_id": sample_id,
            "cwe": cwe,
            "project_wise_split": project_wise_split,
            "seen_project_split": seen_project_split,
        }
        for graph_type, path in (
            ("graph_a", graph_a_path),
            ("graph_b", graph_b_path),
        ):
            self._write_json(
                path,
                {
                    **metadata,
                    "graph_type": graph_type,
                    "status": status,
                    "ddg_status": "NOT_COMPUTED",
                    "num_nodes": 0,
                    "num_edges": 0,
                    "nodes": [],
                    "edges": [],
                    "error_message": message,
                },
            )
        report.update(
            {
                "status": status,
                "error_stage": stage,
                "error_message": message,
                "ddg_status": "NOT_COMPUTED",
                "graph_a_json_bytes": graph_a_path.stat().st_size,
                "graph_b_json_bytes": graph_b_path.stat().st_size,
                "peak_memory_bytes": None,
                "memory_measurement": "not_measured",
            }
        )

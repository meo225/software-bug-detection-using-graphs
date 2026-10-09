"""Deterministic, Joern-independent helpers for the approved graph schema."""

from __future__ import annotations

import html
import re
from collections.abc import Iterable, Sequence, Set
from dataclasses import dataclass

UNKNOWN_TOKEN = "<UNK>"
_SPECIAL_TOKENS = {"<STR>", "<NUM>", "<HEX>", "<UNK>", "<META>"}
_STRING_LITERAL = re.compile(r"^(?:u8|u|U|L)?(?:R)?[\"']")
_CWE_CVE_MARKER = re.compile(r"^(?:CWE|CVE)[_-]?\d+(?:[_-]\d+)*$", re.IGNORECASE)
_NUMBER = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?[fFlLuU]*$")
_HEX_NUMBER = re.compile(r"^[+-]?0[xX][0-9a-fA-F]+[uUlL]*$")
_HEX_COMMIT_TOKEN = re.compile(r"^[0-9a-fA-F]{7,40}$")
_PUNCTUATION_TOKENS = frozenset(
    "++ -- -> ... << >> <= >= == != && || += -= *= /= %= &= |= ^= <<= >>= :: .* ->* ## # { } [ ] ( ) ; : ? . ~ ! + - * / % ^ & | = < > ,".split()
)
_IDENTIFIER_PARTS = re.compile(
    r"(?<=[A-Z])(?=[A-Z][a-z])|(?<=[a-z0-9])(?=[A-Z])|[_\W]+"
)


@dataclass(frozen=True)
class AstNodeRef:
    """Local AST node identity plus source properties used for endpoint mapping."""

    node_id: int
    joern_id: str | int | None
    code: str | None = None
    line_number: int | None = None
    column_number: int | None = None
    ast_depth: int = 0


@dataclass(frozen=True)
class EndpointRef:
    """Joern endpoint data; ancestors are ordered nearest-first via AST_PARENT."""

    joern_id: str | int | None = None
    code: str | None = None
    line_number: int | None = None
    column_number: int | None = None
    ast_ancestor_ids: tuple[str | int, ...] = ()


@dataclass(frozen=True)
class EndpointMapping:
    node_id: int | None
    strategy: str
    reason: str | None = None

    @property
    def mapped(self) -> bool:
        return self.node_id is not None


@dataclass(frozen=True)
class EdgeMapping:
    src: int | None
    dst: int | None
    dropped_reason: str | None = None
    source_strategy: str | None = None
    target_strategy: str | None = None

    @property
    def kept(self) -> bool:
        return self.src is not None and self.dst is not None


@dataclass(frozen=True)
class AstEdgeStats:
    duplicate_edges: int
    self_loops: int


def _identity(value: str | int | None) -> str | None:
    return None if value is None else str(value)


def _source_signature(
    code: str | None, line_number: int | None, column_number: int | None
) -> tuple[int, int, str] | None:
    if not code or line_number is None or column_number is None:
        return None
    if line_number < 1 or column_number < 1:
        return None
    normalized_code = " ".join(code.split())
    if not normalized_code:
        return None
    return line_number, column_number, normalized_code


def _matches_sample_commit_id(token: str, commit_id: str | None) -> bool:
    if commit_id is None:
        return False
    normalized_commit = commit_id.strip()
    normalized_token = token.strip()
    if not _HEX_COMMIT_TOKEN.fullmatch(normalized_commit):
        return False
    if not _HEX_COMMIT_TOKEN.fullmatch(normalized_token):
        return False
    return len(normalized_token) <= len(normalized_commit) and normalized_commit.lower().startswith(
        normalized_token.lower()
    )


def map_endpoint(
    endpoint: EndpointRef,
    ast_nodes: Sequence[AstNodeRef],
    *,
    allow_ast_parent_fallback: bool = True,
) -> EndpointMapping:
    """Map an endpoint by stable Joern ID, source identity, then explicit ancestry.

    Source-identity collisions prefer the deepest AST node, then the smallest local
    ``node_id``. Missing or ambiguous evidence fails closed instead of guessing.
    """
    id_key = _identity(endpoint.joern_id)
    if id_key is not None:
        id_matches = [node for node in ast_nodes if _identity(node.joern_id) == id_key]
        if len(id_matches) == 1:
            return EndpointMapping(id_matches[0].node_id, "joern_id")
        if len(id_matches) > 1:
            return EndpointMapping(None, "unmapped", "ambiguous_joern_id")

    signature = _source_signature(
        endpoint.code, endpoint.line_number, endpoint.column_number
    )
    if signature is not None:
        location_matches = [
            node
            for node in ast_nodes
            if _source_signature(node.code, node.line_number, node.column_number)
            == signature
        ]
        if location_matches:
            chosen = min(location_matches, key=lambda node: (-node.ast_depth, node.node_id))
            return EndpointMapping(chosen.node_id, "source_location")

    if allow_ast_parent_fallback:
        nodes_by_id: dict[str, list[AstNodeRef]] = {}
        for node in ast_nodes:
            node_key = _identity(node.joern_id)
            if node_key is not None:
                nodes_by_id.setdefault(node_key, []).append(node)
        for ancestor_id in endpoint.ast_ancestor_ids:
            matches = nodes_by_id.get(_identity(ancestor_id) or "", [])
            if len(matches) == 1:
                return EndpointMapping(matches[0].node_id, "ast_parent")
            if len(matches) > 1:
                return EndpointMapping(None, "unmapped", "ambiguous_ast_parent_id")

    reason = "no_ast_parent" if endpoint.ast_ancestor_ids else "no_matching_identity"
    return EndpointMapping(None, "unmapped", reason)


def map_edge_endpoints(
    source: EndpointRef,
    target: EndpointRef,
    ast_nodes: Sequence[AstNodeRef],
    *,
    allow_ast_parent_fallback: bool = True,
) -> EdgeMapping:
    """Map both endpoints or drop the whole edge; never invent graph nodes."""
    source_mapping = map_endpoint(
        source, ast_nodes, allow_ast_parent_fallback=allow_ast_parent_fallback
    )
    target_mapping = map_endpoint(
        target, ast_nodes, allow_ast_parent_fallback=allow_ast_parent_fallback
    )
    failures = []
    if not source_mapping.mapped:
        failures.append(f"source:{source_mapping.reason}")
    if not target_mapping.mapped:
        failures.append(f"target:{target_mapping.reason}")
    if failures:
        return EdgeMapping(None, None, ";".join(failures))
    return EdgeMapping(
        source_mapping.node_id,
        target_mapping.node_id,
        source_strategy=source_mapping.strategy,
        target_strategy=target_mapping.strategy,
    )


def deduplicate_ast_edges(
    edges: Iterable[tuple[int, int]],
) -> tuple[tuple[tuple[int, int], ...], AstEdgeStats]:
    """Drop self-loops and duplicate directed ``(src, dst)`` AST relations."""
    unique_edges: set[tuple[int, int]] = set()
    duplicates = 0
    self_loops = 0
    for source, target in edges:
        if source == target:
            self_loops += 1
        elif (source, target) in unique_edges:
            duplicates += 1
        else:
            unique_edges.add((source, target))
    return tuple(sorted(unique_edges)), AstEdgeStats(duplicates, self_loops)


def normalize_code_token(
    token: str,
    *,
    is_comment: bool = False,
    project_name: str | None = None,
    commit_id: str | None = None,
    max_token_length: int = 64,
) -> tuple[str, ...]:
    """Normalize one AST token without modifying the source passed to Joern."""
    value = html.unescape(token).strip()
    if is_comment or not value:
        return ()
    if value in _SPECIAL_TOKENS:
        return (value,)
    if value in _PUNCTUATION_TOKENS:
        return (value,)
    if _STRING_LITERAL.match(value):
        return ("<STR>",)
    if _matches_sample_commit_id(value, commit_id):
        return ("<META>",)
    if _HEX_NUMBER.fullmatch(value):
        return ("<HEX>",)
    if _NUMBER.fullmatch(value):
        numeric = value.rstrip("fFlLuU")
        try:
            if "." in numeric or "e" in numeric.lower() or abs(float(numeric)) > 100:
                return ("<NUM>",)
        except ValueError:
            return ("<NUM>",)
        return (value.lower(),)
    if _CWE_CVE_MARKER.fullmatch(value):
        return ("<META>",)
    compact = re.sub(r"[^a-z0-9]", "", value.lower())
    if compact in {
        "cwe",
        "cve",
        "commit",
        "commitid",
        "commithash",
        "commitsha",
        "commitref",
        "commitrevision",
        "commitmessage",
        "project",
        "projectname",
        "groupid",
        "split",
        "splitname",
    }:
        return ("<META>",)

    parts = [part.lower() for part in _IDENTIFIER_PARTS.split(value) if part]
    if not parts:
        return ()
    if any(part in {"cwe", "cve", "train", "validation", "test"} for part in parts):
        return ("<META>",)
    project_parts = [part.lower() for part in _IDENTIFIER_PARTS.split(project_name or "") if part]
    if project_parts and any(part in project_parts for part in parts):
        return ("<META>",)
    normalized = tuple(part for part in parts if len(part) >= 2)
    if any(len(part) > max_token_length for part in normalized):
        return (UNKNOWN_TOKEN,)
    return normalized


def token_or_unknown(token: str, vocabulary: Set[str]) -> str:
    """Apply the schema OOV rule using the train-fitted vocabulary."""
    return token if token in vocabulary else UNKNOWN_TOKEN


def classify_extraction_status(
    *,
    parse_succeeded: bool,
    ast_available: bool,
    function_body_available: bool,
    statement_count: int | None,
    comment_count: int | None,
    num_nodes: int,
    num_edges: int,
    timed_out: bool = False,
    max_nodes: int = 1000,
    max_edges: int = 3000,
) -> str:
    """Classify parser outcomes without conflating empty bodies and parse errors."""
    counts = (statement_count, comment_count, num_nodes, num_edges, max_nodes, max_edges)
    if any(value is not None and value < 0 for value in counts):
        raise ValueError("Counts and graph limits must be non-negative")
    if timed_out:
        return "TIMEOUT_ERROR"
    if not parse_succeeded:
        return "PARSE_ERROR"
    if not ast_available or not function_body_available:
        return "AST_EXTRACTION_ERROR"
    if num_nodes > max_nodes or num_edges > max_edges:
        return "OVERSIZED_GRAPH"
    if statement_count == 0:
        if comment_count == 0:
            return "EMPTY_FUNCTION_BODY"
        if comment_count is not None and comment_count > 0:
            return "COMMENT_ONLY_FUNCTION"
        if num_nodes > 0:
            return "BODY_CLASSIFICATION_UNKNOWN"
    if num_nodes == 0:
        return "EMPTY_GRAPH"
    return "SUCCESS"
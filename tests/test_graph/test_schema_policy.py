"""Tests for schema configuration and deterministic, Joern-independent policies."""

from __future__ import annotations

import unittest
from pathlib import Path

import yaml

from src.graph.schema_policy import (
    AstNodeRef,
    EndpointRef,
    classify_extraction_status,
    deduplicate_ast_edges,
    map_edge_endpoints,
    map_endpoint,
    normalize_code_token,
    token_or_unknown,
)

ROOT = Path(__file__).resolve().parents[2]
GRAPH_CONFIG = ROOT / "configs" / "graph"


class GraphSchemaConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.graph_a = yaml.safe_load((GRAPH_CONFIG / "graph_a.yaml").read_text())[
            "graph"
        ]
        cls.graph_b = yaml.safe_load((GRAPH_CONFIG / "graph_b.yaml").read_text())[
            "graph"
        ]
        cls.cpg = yaml.safe_load((GRAPH_CONFIG / "cpg.yaml").read_text())
        cls.spec = yaml.safe_load((GRAPH_CONFIG / "schema_spec.yaml").read_text())

    def test_every_graph_yaml_parses_and_candidate_points_to_schemas(self) -> None:
        for config_path in GRAPH_CONFIG.glob("*.yaml"):
            self.assertIsInstance(yaml.safe_load(config_path.read_text()), dict)
        self.assertEqual(self.cpg["graph"]["concrete_schemas"]["graph_a"], "configs/graph/graph_a.yaml")
        self.assertEqual(self.cpg["graph"]["concrete_schemas"]["graph_b"], "configs/graph/graph_b.yaml")

    def test_graph_yaml_has_required_fields_and_matching_node_contract(self) -> None:
        for graph in (self.graph_a, self.graph_b):
            self.assertEqual(graph["scope"], "intra_procedural_function")
            self.assertEqual(graph["nodes"]["indexing"], "zero_indexed_consecutive")
            self.assertEqual(graph["extractor"]["timeout_sec"], 120)
            self.assertEqual(graph["paths"]["manifest_file"].rsplit("/", 1)[-1], "manifest.csv")
        self.assertEqual(self.graph_a["nodes"]["domain"], self.graph_b["nodes"]["domain"])
        self.assertEqual(self.graph_a["nodes"]["features"], self.graph_b["nodes"]["features"])
        self.assertTrue(self.graph_b["nodes"]["reuse_graph_a_domain"])

    def test_edge_types_and_feature_allowlist_are_consistent(self) -> None:
        self.assertEqual(
            [(edge["id"], edge["name"]) for edge in self.graph_a["edges"]["types"]],
            [(0, "AST")],
        )
        self.assertEqual(self.graph_a["edges"]["deduplication_policy"]["key"], ["src", "dst"])
        self.assertTrue(self.graph_a["edges"]["deduplication_policy"]["directed"])
        self.assertTrue(self.graph_a["edges"]["deduplication_policy"]["drop_self_loops"])
        self.assertEqual(
            [(edge["id"], edge["name"]) for edge in self.graph_b["edges"]["types"]],
            [(0, "AST"), (1, "CFG"), (2, "DATA_DEP")],
        )
        self.assertEqual(self.spec["feature_policy"]["allowed_node_features"], [
            "node_type", "code_token", "rel_line_number"
        ])
        self.assertTrue(self.spec["feature_policy"]["metadata_fields_forbidden"])

    def test_dataset_mapping_and_split_counts_are_well_formed(self) -> None:
        mapping = self.spec["cwe_mapping"]
        self.assertEqual(len(mapping), 23)
        self.assertEqual(sorted(mapping.values()), list(range(23)))
        self.assertEqual(self.spec["dataset"]["total_samples"], 9077)
        self.assertEqual(self.spec["dataset"]["total_cwe_classes"], len(mapping))
        for protocol in self.spec["split_protocols"].values():
            self.assertEqual(
                protocol["train_count"]
                + protocol["validation_count"]
                + protocol["test_count"],
                9077,
            )

    def test_graph_limits_artifacts_and_forbidden_metadata(self) -> None:
        limits = self.spec["size_limits"]
        self.assertEqual((limits["max_nodes"], limits["max_edges"], limits["timeout_sec"]), (1000, 3000, 120))
        self.assertEqual(limits["oversized_handling"], "flag_and_log")
        self.assertEqual(self.spec["storage"]["intermediate_format"], "json")
        self.assertEqual(self.spec["storage"]["processed_format"], "pt")
        forbidden = set(self.spec["feature_policy"]["metadata_fields_forbidden"])
        self.assertTrue({"project", "commit", "cve", "cwe", "split", "group_id", "hash"} <= forbidden)
        self.assertEqual(self.graph_a["nodes"]["features"][-1]["name"], "rel_line_number")

    def test_mapping_token_and_status_policies_are_declared(self) -> None:
        mapping = self.graph_b["edges"]["mapping_policy"]
        self.assertEqual(mapping["direct_key"], "joern_id")
        self.assertEqual(mapping["direct_key_scope"], "unique_within_cpg")
        self.assertEqual(mapping["duplicate_direct_id_handling"], "fail_closed")
        self.assertEqual(mapping["source_key"], ["line_number", "column_number", "normalized_code"])
        self.assertEqual(mapping["candidate_ranking"], ["ast_depth_desc", "node_id_asc"])
        self.assertEqual(mapping["ast_parent_fallback"]["ancestor_order"], "nearest_first")
        self.assertEqual(mapping["ast_parent_fallback"]["ambiguous_ancestor_handling"], "fail_closed_and_stop_chain")
        token_policy = self.spec["normalization"]
        self.assertFalse(token_policy["comments"]["include_in_code_tokens"])
        self.assertEqual(token_policy["all_string_and_char_literals"], "<STR>")
        self.assertEqual(token_policy["punctuation_policy"], "preserve_exact_token")
        self.assertEqual(token_policy["overlength_token_policy"], "map_to_UNK_if_any_subtoken_exceeds_limit")
        self.assertIn("commit_sha", token_policy["redact_patterns"]["metadata_field_names"])
        self.assertEqual(token_policy["redact_patterns"]["commit_hash"]["candidate_length"], [7, 40])
        self.assertEqual(token_policy["redact_patterns"]["commit_hash"]["without_commit_metadata"], "preserve_source_token")
        self.assertEqual(self.spec["vocabulary_policy"]["fit_target"], "train_split_only")
        self.assertEqual(self.spec["vocabulary_policy"]["oov_token"], "<UNK>")
        for status in (
            "EMPTY_FUNCTION_BODY",
            "COMMENT_ONLY_FUNCTION",
            "BODY_CLASSIFICATION_UNKNOWN",
            "PARSE_ERROR",
            "AST_EXTRACTION_ERROR",
        ):
            self.assertIn(status, self.spec["status_enums"])


class EndpointMappingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.nodes = (
            AstNodeRef(0, "ast-root", "block", 1, 1, 0),
            AstNodeRef(1, "ast-id", "buffer", 3, 5, 3),
            AstNodeRef(2, "ast-tie", "buffer", 3, 5, 3),
            AstNodeRef(4, "ast-deep", "buffer", 3, 5, 5),
        )

    def test_direct_joern_id_precedes_other_keys(self) -> None:
        mapped = map_endpoint(EndpointRef(joern_id="ast-id"), self.nodes)
        self.assertEqual((mapped.node_id, mapped.strategy), (1, "joern_id"))

    def test_source_identity_and_deterministic_tie_break(self) -> None:
        endpoint = EndpointRef(code=" buffer  ", line_number=3, column_number=5)
        mapped = map_endpoint(endpoint, self.nodes)
        self.assertEqual((mapped.node_id, mapped.strategy), (4, "source_location"))
        tied = tuple(node for node in self.nodes if node.ast_depth == 3)
        self.assertEqual(map_endpoint(endpoint, tied).node_id, 1)

    def test_parent_fallback_uses_nearest_existing_ancestor(self) -> None:
        endpoint = EndpointRef(ast_ancestor_ids=("not-in-ast", "ast-root"))
        mapped = map_endpoint(endpoint, self.nodes)
        self.assertEqual((mapped.node_id, mapped.strategy), (0, "ast_parent"))
        disabled = map_endpoint(endpoint, self.nodes, allow_ast_parent_fallback=False)
        self.assertFalse(disabled.mapped)

    def test_ambiguous_parent_stops_chain_and_no_match_drops(self) -> None:
        duplicate_parent = self.nodes + (AstNodeRef(5, "ast-root"),)
        ambiguous = map_endpoint(
            EndpointRef(ast_ancestor_ids=("ast-root", "ast-id")), duplicate_parent
        )
        self.assertEqual(ambiguous.reason, "ambiguous_ast_parent_id")
        missing = map_endpoint(
            EndpointRef(ast_ancestor_ids=("not-present",)), self.nodes
        )
        self.assertEqual(missing.reason, "no_ast_parent")

    def test_ambiguous_ids_and_unmapped_edges_fail_closed(self) -> None:
        duplicated = self.nodes + (AstNodeRef(5, "ast-id"),)
        ambiguous = map_endpoint(EndpointRef(joern_id="ast-id"), duplicated)
        self.assertEqual(ambiguous.reason, "ambiguous_joern_id")
        dropped = map_edge_endpoints(
            EndpointRef(joern_id="ast-root"), EndpointRef(code="unknown"), self.nodes
        )
        self.assertFalse(dropped.kept)
        self.assertIsNone(dropped.src)
        self.assertIn("target:", dropped.dropped_reason or "")

    def test_edge_mapping_records_endpoint_strategies(self) -> None:
        mapped = map_edge_endpoints(
            EndpointRef(joern_id="ast-root"),
            EndpointRef(code="buffer", line_number=3, column_number=5),
            self.nodes,
        )
        self.assertTrue(mapped.kept)
        self.assertEqual(
            (mapped.source_strategy, mapped.target_strategy),
            ("joern_id", "source_location"),
        )


class TokenAndEdgePolicyTests(unittest.TestCase):
    def test_comments_literals_identifiers_and_metadata(self) -> None:
        self.assertEqual(normalize_code_token("/* CVE-2024-1234 */", is_comment=True), ())
        self.assertEqual(normalize_code_token('"CWE-787 project-name"'), ("<STR>",))
        self.assertEqual(normalize_code_token("'x'"), ("<STR>",))
        self.assertEqual(normalize_code_token("parseHeader"), ("parse", "header"))
        self.assertEqual(normalize_code_token("buffer_len"), ("buffer", "len"))
        self.assertEqual(normalize_code_token("+"), ("+",))
        self.assertEqual(normalize_code_token("->"), ("->",))
        self.assertEqual(normalize_code_token("CWE_787"), ("<META>",))
        self.assertEqual(normalize_code_token("CVE-2024-1234"), ("<META>",))
        self.assertEqual(normalize_code_token("a1b2c3d4"), ("a1b2c3d4",))
        self.assertEqual(normalize_code_token("deadbee"), ("deadbee",))
        commit_id = "deadbee1234567890abcdef1234567890abcde"
        self.assertEqual(normalize_code_token("deadbee", commit_id=commit_id), ("<META>",))
        self.assertEqual(normalize_code_token(commit_id, commit_id=commit_id), ("<META>",))
        self.assertEqual(normalize_code_token("deadbee", commit_id="0123456789abcdef"), ("deadbee",))
        numeric_commit = "1234567"
        self.assertEqual(normalize_code_token(numeric_commit, commit_id=numeric_commit), ("<META>",))
        self.assertEqual(normalize_code_token("commit_id"), ("<META>",))
        self.assertEqual(normalize_code_token("commitSha"), ("<META>",))
        self.assertEqual(normalize_code_token("train_data"), ("<META>",))
        self.assertEqual(normalize_code_token("libgit2_handle", project_name="libgit2"), ("<META>",))
        self.assertEqual(normalize_code_token("validation"), ("<META>",))
        self.assertEqual(normalize_code_token("&lt;html_name&gt;"), ("html", "name"))
        self.assertEqual(normalize_code_token("x" * 65), ("<UNK>",))
        self.assertEqual(normalize_code_token("<UNK>"), ("<UNK>",))

    def test_oov_and_graph_a_edge_deduplication(self) -> None:
        self.assertEqual(token_or_unknown("buffer", {"buffer"}), "buffer")
        self.assertEqual(token_or_unknown("secret", {"buffer"}), "<UNK>")
        edges, stats = deduplicate_ast_edges(((0, 1), (0, 1), (1, 1), (1, 0)))
        self.assertEqual(edges, ((0, 1), (1, 0)))
        self.assertEqual((stats.duplicate_edges, stats.self_loops), (1, 1))


class ExtractionStatusTests(unittest.TestCase):
    def test_empty_comment_only_and_parse_states_remain_distinct(self) -> None:
        common = dict(
            parse_succeeded=True,
            ast_available=True,
            function_body_available=True,
            num_nodes=2,
            num_edges=1,
        )
        self.assertEqual(
            classify_extraction_status(**common, statement_count=0, comment_count=0),
            "EMPTY_FUNCTION_BODY",
        )
        self.assertEqual(
            classify_extraction_status(**common, statement_count=0, comment_count=2),
            "COMMENT_ONLY_FUNCTION",
        )
        self.assertEqual(
            classify_extraction_status(**common, statement_count=1, comment_count=0),
            "SUCCESS",
        )
        self.assertEqual(
            classify_extraction_status(
                parse_succeeded=False,
                ast_available=False,
                function_body_available=False,
                statement_count=None,
                comment_count=None,
                num_nodes=0,
                num_edges=0,
            ),
            "PARSE_ERROR",
        )
        self.assertEqual(
            classify_extraction_status(
                parse_succeeded=True,
                ast_available=False,
                function_body_available=False,
                statement_count=None,
                comment_count=None,
                num_nodes=0,
                num_edges=0,
            ),
            "AST_EXTRACTION_ERROR",
        )

    def test_body_unknown_and_actual_node_count_control_empty_graph(self) -> None:
        common = dict(
            parse_succeeded=True,
            ast_available=True,
            function_body_available=True,
            statement_count=0,
            comment_count=None,
            num_edges=0,
        )
        self.assertEqual(
            classify_extraction_status(**common, num_nodes=2),
            "BODY_CLASSIFICATION_UNKNOWN",
        )
        self.assertEqual(
            classify_extraction_status(**common, num_nodes=0), "EMPTY_GRAPH"
        )
        self.assertEqual(
            classify_extraction_status(
                **{**common, "comment_count": 0}, num_nodes=2
            ),
            "EMPTY_FUNCTION_BODY",
        )
        self.assertEqual(
            classify_extraction_status(
                **{**common, "comment_count": 3}, num_nodes=2
            ),
            "COMMENT_ONLY_FUNCTION",
        )
        self.assertEqual(
            classify_extraction_status(
                **{**common, "function_body_available": False}, num_nodes=2
            ),
            "AST_EXTRACTION_ERROR",
        )

    def test_empty_graph_timeout_and_size_states(self) -> None:
        args = dict(
            parse_succeeded=True,
            ast_available=True,
            function_body_available=True,
            statement_count=1,
            comment_count=0,
        )
        self.assertEqual(classify_extraction_status(**args, num_nodes=0, num_edges=0), "EMPTY_GRAPH")
        self.assertEqual(classify_extraction_status(**args, num_nodes=1001, num_edges=0), "OVERSIZED_GRAPH")
        self.assertEqual(
            classify_extraction_status(**args, num_nodes=0, num_edges=0, timed_out=True),
            "TIMEOUT_ERROR",
        )


if __name__ == "__main__":
    unittest.main()
"""Unit tests for Joern payload mapping and Tier-1 extraction failures."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.graph.joern import (
    JoernConfig,
    JoernExecutionError,
    JoernExtractor,
    _ddg_method_log_evidence,
    _detect_language,
    _lexical_tokens,
    _map_payload,
    _normalize_ddg_status,
    _normalized_code,
    _joern_script,
)


_SOURCE_TEXT = "int target(int input) {\n return projectName(input);\n}"


def _payload() -> dict:
    nodes = [
        {
            "joern_id": "10",
            "label": "METHOD",
            "code": "int target(int input) { return projectName(input); }",
            "line_number": 1,
            "column_number": 1,
        },
        {
            "joern_id": "11",
            "label": "IDENTIFIER",
            "code": "input",
            "line_number": 1,
            "column_number": 20,
        },
        {
            "joern_id": "12",
            "label": "CALL",
            "code": "projectName(input)",
            "line_number": None,
            "column_number": None,
        },
        {
            "joern_id": "13",
            "label": "COMMENT",
            "code": "/* comment should not be a node */",
            "line_number": 1,
            "column_number": 30,
        },
    ]
    return {
        "function_name": "target",
        "method_full_name": "target",
        "method_code": "int target(int input) {\n return projectName(input);\n}",
        "dataflow_applied_before": False,
        "ddg_edge_count_before": 0,
        "dataflow_applied_after": True,
        "dataflow_pass_attempted": True,
        "dataflow_pass_completed": True,
        "nodes": nodes,
        "ast_edges": [
            {"src": "10", "dst": "11"},
            {"src": "10", "dst": "11"},
            {"src": "10", "dst": "12"},
            {"src": "12", "dst": "12"},
            {"src": "12", "dst": "13"},
        ],
        "cfg_edges": [
            {"src": "11", "dst": "12"},
            {"src": "99", "dst": "12"},
        ],
        "ddg_edges": [{"src": "11", "dst": "12"}],
    }


def _completed_method_logs(method_name: str = "target") -> str:
    return (
        f"Calculating reaching definitions for: {method_name} in sample.c\n"
        f"Number of definitions for {method_name}: 3\n"
    )


class LexicalTokenTests(unittest.TestCase):
    def test_c_lexing_skips_comments_and_preserves_literal_and_operators(self) -> None:
        tokens = _lexical_tokens(
            'x /* comment */ += "secret"; // trailing\nreturn 0xFF; 1+2;'
        )
        self.assertEqual(
            [token for token, _ in tokens],
            [
                "x",
                "+=",
                '"secret"',
                ";",
                "return",
                "0xFF",
                ";",
                "1",
                "+",
                "2",
                ";",
            ],
        )

    def test_prefixed_literals_are_normalized_without_leaking_prefixes(self) -> None:
        code = 'u8"utf8" L\'c\' R"tag(raw text)tag"'
        tokens = _lexical_tokens(code)
        self.assertEqual(
            [token for token, _ in tokens],
            ['u8"utf8"', "L'c'", 'R"tag(raw text)tag"'],
        )
        self.assertEqual(
            _normalized_code(code, project_name=None, commit_id=None),
            "<STR> <STR> <STR>",
        )


class JoernMappingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = JoernConfig(max_nodes=1000, max_edges=3000)

    def map_payload(
        self,
        payload: dict | None = None,
        *,
        joern_logs: str | None = None,
        source_text: str = _SOURCE_TEXT,
    ):
        return _map_payload(
            payload or _payload(),
            sample_id="row-smoke",
            cwe=None,
            project_wise_split=None,
            seen_project_split=None,
            project_name="sample_project",
            commit_id=None,
            source_text=source_text,
            config=self.config,
            joern_logs=joern_logs if joern_logs is not None else _completed_method_logs(),
        )

    def test_graph_a_and_b_share_nodes_and_preserve_typed_edges(self) -> None:
        graph_a, graph_b, metrics = self.map_payload()
        self.assertEqual(graph_a["nodes"], graph_b["nodes"])
        self.assertEqual(graph_a["ddg_status"], "NOT_COMPUTED")
        self.assertEqual(graph_b["ddg_status"], "EDGES_PRESENT")
        self.assertEqual({edge["type"] for edge in graph_a["edges"]}, {0})
        self.assertEqual({edge["type"] for edge in graph_b["edges"]}, {0, 1, 2})
        self.assertEqual(graph_a["cwe"], None)
        self.assertEqual(graph_a["project_wise_split"], None)
        self.assertEqual(graph_a["seen_project_split"], None)
        self.assertEqual(metrics["edge_counts"]["graph_b_by_type"], {
            "AST": 2,
            "CFG": 1,
            "DATA_DEP": 1,
        })

    def test_dedup_self_loop_invalid_endpoints_and_comment_exclusion_are_counted(self) -> None:
        graph_a, graph_b, metrics = self.map_payload()
        ast_stats = metrics["edge_statistics"]["AST"]
        cfg_stats = metrics["edge_statistics"]["CFG"]
        self.assertEqual(ast_stats["duplicate_edges_dropped"], 1)
        self.assertEqual(ast_stats["self_loop_edges_dropped"], 1)
        self.assertEqual(ast_stats["unmappable_reasons"], {"comment_node_excluded": 1})
        self.assertEqual(cfg_stats["unmappable_reasons"], {"source_not_in_ast_domain": 1})
        self.assertEqual(metrics["excluded_comment_nodes"], 1)
        ids = {node["id"] for node in graph_a["nodes"]}
        self.assertTrue(all(edge["src"] in ids and edge["dst"] in ids for edge in graph_b["edges"]))
        self.assertNotIn("/* comment", json.dumps(graph_b["nodes"]))
        self.assertTrue(all(edge["src"] != edge["dst"] for edge in graph_b["edges"]))

    def test_existing_project_token_normalizer_is_used_for_code_features(self) -> None:
        graph_a, _, _ = self.map_payload()
        root_code = graph_a["nodes"][0]["code_token"]
        self.assertIn("<META>", root_code)
        self.assertIn("input", root_code)
        self.assertNotIn("projectname", root_code)
        self.assertEqual(graph_a["nodes"][2]["line_number"], 1)
        self.assertEqual(graph_a["nodes"][2]["rel_line_number"], 1 / 3)

    def test_oversized_graph_keeps_all_nodes_and_edges(self) -> None:
        config = JoernConfig(max_nodes=2, max_edges=1)
        graph_a, graph_b, metrics = _map_payload(
            _payload(),
            sample_id="row-large",
            cwe=None,
            project_wise_split=None,
            seen_project_split=None,
            project_name=None,
            commit_id=None,
            source_text=_SOURCE_TEXT,
            config=config,
            joern_logs="",
        )
        self.assertEqual(graph_a["status"], "OVERSIZED_GRAPH")
        self.assertEqual(graph_b["status"], "OVERSIZED_GRAPH")
        self.assertEqual(graph_b["num_nodes"], 3)
        self.assertEqual(graph_b["num_edges"], 4)
        self.assertEqual(len(graph_b["nodes"]), 3)
        self.assertEqual(len(graph_b["edges"]), 4)
        self.assertFalse(metrics["oversized"]["truncated"])
        self.assertTrue(metrics["oversized"]["limits_are_warning_only"])

    def test_duplicate_joern_ids_fail_closed(self) -> None:
        payload = _payload()
        payload["nodes"] = payload["nodes"] + [dict(payload["nodes"][0])]
        with self.assertRaisesRegex(ValueError, "duplicate Joern node IDs"):
            self.map_payload(payload)

    # --- DDG status: NOT_COMPUTED ---

    def test_not_computed_when_dataflow_was_not_attempted(self) -> None:
        # dataflow_pass_attempted=False means dataflowOss overlay was already
        # present before our script ran; we did not attempt a new pass.
        status = _normalize_ddg_status(
            dataflow_pass_attempted=False,
            dataflow_pass_completed=False,
            method_full_name="target",
            ddg_edge_count=0,
            joern_logs="",
        )
        self.assertEqual(status, "NOT_COMPUTED")

    def test_not_computed_regardless_of_edge_count_when_not_attempted(self) -> None:
        # Even if DDG edges exist from a prior run, status is NOT_COMPUTED
        # when the current extraction did not attempt the dataflow pass.
        status = _normalize_ddg_status(
            dataflow_pass_attempted=False,
            dataflow_pass_completed=False,
            method_full_name="target",
            ddg_edge_count=5,
            joern_logs=_completed_method_logs(),
        )
        self.assertEqual(status, "NOT_COMPUTED")

    # --- DDG status: EDGES_PRESENT ---

    def test_edges_present_requires_full_evidence_and_at_least_one_edge(self) -> None:
        status = _normalize_ddg_status(
            dataflow_pass_attempted=True,
            dataflow_pass_completed=True,
            method_full_name="target",
            ddg_edge_count=1,
            joern_logs=_completed_method_logs(),
        )
        self.assertEqual(status, "EDGES_PRESENT")

    def test_edges_present_with_multiple_valid_ddg_edges(self) -> None:
        status = _normalize_ddg_status(
            dataflow_pass_attempted=True,
            dataflow_pass_completed=True,
            method_full_name="target",
            ddg_edge_count=7,
            joern_logs=_completed_method_logs(),
        )
        self.assertEqual(status, "EDGES_PRESENT")

    # --- DDG status: zero edges always fails safe to INCOMPLETE ---

    def test_incomplete_when_full_log_evidence_but_zero_ddg_edges(self) -> None:
        # Joern 4.0.654 emits no per-method completion log, so zero observed
        # DDG edges can never be trusted as "computed but no dependence".
        status = _normalize_ddg_status(
            dataflow_pass_attempted=True,
            dataflow_pass_completed=True,
            method_full_name="target",
            ddg_edge_count=0,
            joern_logs=_completed_method_logs(),
        )
        self.assertEqual(status, "INCOMPLETE")

    def test_incomplete_via_map_payload_when_all_ddg_edges_unmappable(self) -> None:
        # All raw DDG edges are dropped at mapping time; without any valid
        # edge the record must fail safe to INCOMPLETE, never a "no edges"
        # success state.
        payload = _payload()
        payload["ddg_edges"] = [{"src": "11", "dst": "missing-node"}]
        _, graph_b, metrics = self.map_payload(payload)
        self.assertEqual(graph_b["ddg_status"], "INCOMPLETE")
        self.assertEqual(metrics["edge_counts"]["graph_b_by_type"]["DATA_DEP"], 0)
        self.assertEqual(metrics["edge_statistics"]["DATA_DEP"]["unmappable_count"], 1)

    # --- DDG status: INCOMPLETE ---

    def test_incomplete_when_overlay_present_but_no_method_log_at_all(self) -> None:
        # Overlay alone (dataflow_pass_completed=True) is NOT sufficient evidence.
        # Missing both start and definition-count log lines -> INCOMPLETE.
        status = _normalize_ddg_status(
            dataflow_pass_attempted=True,
            dataflow_pass_completed=True,
            method_full_name="target",
            ddg_edge_count=0,
            joern_logs="",
        )
        self.assertEqual(status, "INCOMPLETE")

    def test_incomplete_when_start_log_present_but_definition_count_missing(self) -> None:
        # Partial log evidence: start line logged but definition-count line absent.
        # Cannot verify completion at method level -> INCOMPLETE.
        start_only_log = "Calculating reaching definitions for: target in sample.c\n"
        status = _normalize_ddg_status(
            dataflow_pass_attempted=True,
            dataflow_pass_completed=True,
            method_full_name="target",
            ddg_edge_count=0,
            joern_logs=start_only_log,
        )
        self.assertEqual(status, "INCOMPLETE")

    def test_incomplete_when_definition_count_present_but_start_log_missing(self) -> None:
        # Converse: definition-count line logged but start line absent.
        # Still cannot confirm completion for this specific method -> INCOMPLETE.
        count_only_log = "Number of definitions for target: 3\n"
        status = _normalize_ddg_status(
            dataflow_pass_attempted=True,
            dataflow_pass_completed=True,
            method_full_name="target",
            ddg_edge_count=0,
            joern_logs=count_only_log,
        )
        self.assertEqual(status, "INCOMPLETE")

    def test_incomplete_when_pass_overlay_missing_despite_full_method_log(self) -> None:
        # run.ossdataflow must have completed (overlay present) in addition to
        # method-level logs.  If the overlay is absent, INCOMPLETE regardless.
        status = _normalize_ddg_status(
            dataflow_pass_attempted=True,
            dataflow_pass_completed=False,
            method_full_name="target",
            ddg_edge_count=0,
            joern_logs=_completed_method_logs(),
        )
        self.assertEqual(status, "INCOMPLETE")

    def test_incomplete_when_skip_log_present_even_with_ddg_edges(self) -> None:
        # Critical edge case: overlay ran, full method logs present, DDG edges
        # exist in the payload — but a skip line is also logged for this method.
        # The skip invalidates confidence in completeness -> INCOMPLETE.
        skip_log = (
            _completed_method_logs()
            + "target has more than 4000 definitions\nSkipping.\n"
        )
        status = _normalize_ddg_status(
            dataflow_pass_attempted=True,
            dataflow_pass_completed=True,
            method_full_name="target",
            ddg_edge_count=3,
            joern_logs=skip_log,
        )
        self.assertEqual(status, "INCOMPLETE")

    def test_incomplete_when_method_full_name_is_none(self) -> None:
        # If the Joern payload does not return a method_full_name we cannot
        # match any log line for this method -> INCOMPLETE.
        status = _normalize_ddg_status(
            dataflow_pass_attempted=True,
            dataflow_pass_completed=True,
            method_full_name=None,
            ddg_edge_count=0,
            joern_logs=_completed_method_logs(),
        )
        self.assertEqual(status, "INCOMPLETE")

    def test_ddg_overlay_with_skipped_method_is_incomplete_via_map_payload(self) -> None:
        # Integration-level: overlay active, dataflow_pass_completed=True, but
        # a per-method skip line is present.  map_payload must propagate INCOMPLETE.
        payload = _payload()
        _, graph_b, metrics = self.map_payload(
            payload,
            joern_logs=(
                _completed_method_logs()
                + "target has more than 4000 definitions\nSkipping.\n"
            ),
        )
        self.assertTrue(payload["dataflow_applied_after"])
        self.assertTrue(metrics["dataflow_pass_completed"])
        self.assertEqual(graph_b["ddg_status"], "INCOMPLETE")
        self.assertTrue(metrics["ddg_completion_evidence"]["method_skip_logged"])

    # --- Log evidence helper ---

    def test_log_evidence_flags_are_individually_accurate(self) -> None:
        # Verify the three evidence flags independently on canonical log fixtures.
        full_log = _completed_method_logs()
        ev = _ddg_method_log_evidence("target", full_log)
        self.assertTrue(ev["method_start_logged"])
        self.assertTrue(ev["method_definition_count_logged"])
        self.assertFalse(ev["method_skip_logged"])

        skip_log = full_log + "target has more than 4000 definitions\nSkipping.\n"
        ev_skip = _ddg_method_log_evidence("target", skip_log)
        self.assertTrue(ev_skip["method_start_logged"])
        self.assertTrue(ev_skip["method_definition_count_logged"])
        self.assertTrue(ev_skip["method_skip_logged"])

        ev_empty = _ddg_method_log_evidence("target", "")
        self.assertFalse(ev_empty["method_start_logged"])
        self.assertFalse(ev_empty["method_definition_count_logged"])
        self.assertFalse(ev_empty["method_skip_logged"])

    def test_log_evidence_does_not_match_unrelated_method_name(self) -> None:
        # Evidence for 'other_method' must not bleed into evidence for 'target'.
        log = (
            "Calculating reaching definitions for: other_method in file.c\n"
            "Number of definitions for other_method: 2\n"
        )
        ev = _ddg_method_log_evidence("target", log)
        self.assertFalse(ev["method_start_logged"])
        self.assertFalse(ev["method_definition_count_logged"])
        self.assertFalse(ev["method_skip_logged"])

    # --- Legacy combined test (kept for regression) ---

    def test_ddg_status_requires_dataflow_and_treats_skips_as_incomplete(self) -> None:
        """Regression guard: confirms all three status values remain reachable."""
        self.assertEqual(
            _normalize_ddg_status(
                dataflow_pass_attempted=False,
                dataflow_pass_completed=False,
                method_full_name="target",
                ddg_edge_count=0,
                joern_logs="",
            ),
            "NOT_COMPUTED",
        )
        self.assertEqual(
            _normalize_ddg_status(
                dataflow_pass_attempted=True,
                dataflow_pass_completed=True,
                method_full_name="target",
                ddg_edge_count=1,
                joern_logs=_completed_method_logs(),
            ),
            "EDGES_PRESENT",
        )
        self.assertEqual(
            _normalize_ddg_status(
                dataflow_pass_attempted=True,
                dataflow_pass_completed=True,
                method_full_name="target",
                ddg_edge_count=0,
                joern_logs=_completed_method_logs(),
            ),
            "INCOMPLETE",
        )
        self.assertEqual(
            _normalize_ddg_status(
                dataflow_pass_attempted=True,
                dataflow_pass_completed=True,
                method_full_name="target",
                ddg_edge_count=0,
                joern_logs=(
                    _completed_method_logs()
                    + "target has more than 4000 definitions\nSkipping.\n"
                ),
            ),
            "INCOMPLETE",
        )
        self.assertEqual(
            _normalize_ddg_status(
                dataflow_pass_attempted=True,
                dataflow_pass_completed=True,
                method_full_name="target",
                ddg_edge_count=0,
                joern_logs="",
            ),
            "INCOMPLETE",
        )
        self.assertEqual(
            _normalize_ddg_status(
                dataflow_pass_attempted=True,
                dataflow_pass_completed=False,
                method_full_name="target",
                ddg_edge_count=0,
                joern_logs=_completed_method_logs(),
            ),
            "INCOMPLETE",
        )



class JoernPrerequisiteQueryTests(unittest.TestCase):
    def test_builtin_layers_precede_reference_validation_and_dataflow(self) -> None:
        script = _joern_script()
        stages = [
            'prepareLayer("base") { run.base }',
            'prepareLayer("typerel") { run.typerelations }',
            'prepareLayer("callgraph") { run.callgraph }',
            'prepareLayer("controlflow") { run.controlflow }',
            'val methods = cpg.method.nameExact(functionName).l',
            'if (methods.size != 1)',
            'val unresolvedMethodRefs = cpg.methodRef.l.filter',
            'require(unresolvedMethodRefs.isEmpty',
            'prepareLayer("dataflowOss") { run.ossdataflow }',
            'Files.writeString(Paths.get(outFile)',
        ]
        positions = [script.index(stage) for stage in stages]
        self.assertEqual(positions, sorted(positions))
        self.assertIn('require(cpg.metaData.overlays.contains(name)', script)

    def test_script_member_is_distinct_from_stored_overlay_name(self) -> None:
        script = _joern_script()
        # The installed OverlaysDynamic generator exposes the lower-case creator
        # class name, whereas TypeRelations stores the overlay name "typerel".
        self.assertIn('prepareLayer("typerel") { run.typerelations }', script)
        self.assertIn('prepareLayer("callgraph") { run.callgraph }', script)
        self.assertNotRegex(script, r"\brun\.typerel\b")

    def test_reference_guard_checks_cardinality_and_symbolic_identity(self) -> None:
        script = _joern_script()
        self.assertIn('ref.outE(EdgeTypes.REF).l.map(_.dst).filter(_.label == "METHOD")', script)
        self.assertIn('if (targets.size == 1) Some(ref.referencedMethod.fullName) else None', script)
        self.assertIn('val resolved = targetName.contains(ref.methodFullName)', script)
        self.assertIn('Unresolved mandatory METHOD_REF targets:', script)
        self.assertIn('"unresolved" -> unresolvedMethodRefs.size', script)
        for mutation in ('addEdge', 'withRefEdge', 'NewMethodRef', 'diffGraph', 'catch'):
            self.assertNotIn(mutation, script)


class JoernFailureTests(unittest.TestCase):
    def test_unresolved_method_ref_error_remains_an_explicit_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.c"
            source.write_text("int target(void) { return 1; }")
            extractor = JoernExtractor()

            def unresolved(stage: str, command: list[str], working_dir: Path):
                if stage == "parse":
                    Path(command[command.index("--output") + 1]).write_bytes(b"mock-cpg")
                    return subprocess.CompletedProcess(command, 0, "", "")
                raise JoernExecutionError("extract", "Unresolved mandatory METHOD_REF targets: 123")

            with patch.object(extractor, "_run_stage", side_effect=unresolved):
                with self.assertRaisesRegex(JoernExecutionError, "Unresolved mandatory METHOD_REF"):
                    extractor.extract(source, root / "out", sample_id="unresolved", function_name="target")
            for kind in ("graph_a", "graph_b"):
                graph = json.loads((root / "out" / f"unresolved.{kind}.json").read_text())
                self.assertEqual(graph["status"], "AST_EXTRACTION_ERROR")
                self.assertEqual(graph["ddg_status"], "NOT_COMPUTED")
                self.assertEqual(graph["nodes"], [])
                self.assertEqual(graph["edges"], [])

    def test_parse_error_writes_explicit_failure_records_and_reraises(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "broken.c"
            source.write_text("not valid C")
            extractor = JoernExtractor()

            def fail_parse(stage: str, command: list[str], working_dir: Path):
                self.assertEqual(stage, "parse")
                raise JoernExecutionError("parse", "joern-parse failed")

            with patch.object(extractor, "_run_stage", side_effect=fail_parse):
                with self.assertRaisesRegex(JoernExecutionError, "joern-parse failed"):
                    extractor.extract(
                        source, root / "out", sample_id="bad-source", function_name="broken"
                    )

            graph_a = json.loads((root / "out" / "bad-source.graph_a.json").read_text())
            graph_b = json.loads((root / "out" / "bad-source.graph_b.json").read_text())
            report = json.loads((root / "out" / "bad-source.metrics.json").read_text())
            self.assertEqual(graph_a["status"], "PARSE_ERROR")
            self.assertEqual(graph_b["status"], "PARSE_ERROR")
            self.assertEqual(graph_b["ddg_status"], "NOT_COMPUTED")
            self.assertEqual(graph_b["nodes"], [])
            self.assertEqual(report["error_stage"], "parse")
            self.assertEqual(report["ddg_status"], "NOT_COMPUTED")

    def test_joern_extraction_error_is_not_reported_as_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "valid.c"
            source.write_text("int target(void) { return 1; }")
            extractor = JoernExtractor()

            def fail_extract(stage: str, command: list[str], working_dir: Path):
                if stage == "parse":
                    cpg = Path(command[command.index("--output") + 1])
                    cpg.write_bytes(b"mock-cpg")
                    return subprocess.CompletedProcess(command, 0, "", "")
                raise JoernExecutionError("extract", "Joern script failed")

            with patch.object(extractor, "_run_stage", side_effect=fail_extract):
                with self.assertRaisesRegex(JoernExecutionError, "Joern script failed"):
                    extractor.extract(
                        source, root / "out", sample_id="joern-failure", function_name="target"
                    )
            record = json.loads(
                (root / "out" / "joern-failure.graph_b.json").read_text()
            )
            self.assertEqual(record["status"], "AST_EXTRACTION_ERROR")
            self.assertEqual(record["ddg_status"], "NOT_COMPUTED")


class LanguageDetectionTests(unittest.TestCase):
    def test_plain_c_function_is_detected_as_c(self) -> None:
        source = (
            "static int process(struct req *r, int flags) {\n"
            "    if (r == 0) { return -1; }\n"
            "    r->state = flags;\n"
            "    return r->state;\n"
            "}\n"
        )
        self.assertEqual(_detect_language(source), "c")

    def test_c_identifiers_spelling_cpp_keywords_do_not_signal_cpp(self) -> None:
        source = (
            "int f(int new, int delete, int operator, int try, int throw) {\n"
            "    return new + delete + operator + try + throw;\n"
            "}\n"
        )
        self.assertEqual(_detect_language(source), "c")

    def test_cpp_looking_text_inside_string_literal_is_ignored(self) -> None:
        source = (
            'const char *s = "std::vector<int> template<class T> namespace N";\n'
            "return s[0];\n"
        )
        self.assertEqual(_detect_language(source), "c")

    def test_cpp_looking_text_inside_comment_is_ignored(self) -> None:
        source = "int x; // namespace foo { class Bar::baz }\n"
        self.assertEqual(_detect_language(source), "c")

    def test_scope_resolution_signals_cpp(self) -> None:
        self.assertEqual(
            _detect_language("int Foo::bar() { return x; }\n"), "cpp"
        )

    def test_template_declaration_signals_cpp(self) -> None:
        self.assertEqual(
            _detect_language("template<typename T> T ident(T v) { return v; }\n"),
            "cpp",
        )

    def test_cpp_only_keywords_signal_cpp(self) -> None:
        self.assertEqual(_detect_language("namespace a { int b; }\n"), "cpp")
        self.assertEqual(
            _detect_language("class Foo { virtual void f(); };\n"), "cpp"
        )
        self.assertEqual(
            _detect_language("void Foo::f() { this->x = 1; }\n"), "cpp"
        )

    def test_struct_usage_alone_does_not_signal_cpp(self) -> None:
        self.assertEqual(
            _detect_language("struct point { int x; int y; };\n"), "c"
        )

    def test_empty_or_comment_only_source_fails_closed(self) -> None:
        for source in ("", "  \n\t\n", "// nothing here\n", "/* nothing */\n"):
            with self.assertRaisesRegex(ValueError, "Cannot determine source language"):
                _detect_language(source)


def _single_node_payload(line_number: int | None) -> dict:
    return {
        "function_name": "target",
        "method_full_name": "target",
        "method_code": "int target(void) { return 0; }",
        "dataflow_pass_attempted": True,
        "dataflow_pass_completed": True,
        "nodes": [
            {
                "joern_id": "10",
                "label": "METHOD",
                "code": "int target(void) { return 0; }",
                "line_number": line_number,
                "column_number": 1,
            }
        ],
        "ast_edges": [],
        "cfg_edges": [],
        "ddg_edges": [],
    }


class NodePositionTests(unittest.TestCase):
    def map_single(
        self,
        line_number: int | None,
        *,
        source_text: str,
    ):
        return _map_payload(
            _single_node_payload(line_number),
            sample_id="row-pos",
            cwe=None,
            project_wise_split=None,
            seen_project_split=None,
            project_name=None,
            commit_id=None,
            source_text=source_text,
            config=JoernConfig(),
            joern_logs="",
        )

    def test_denominator_uses_source_text_not_joern_method_code(self) -> None:
        # Joern's method.code can be truncated (observed at #ifdef regions);
        # the schema denominator is the extraction input source, so a node on
        # the last source line must give rel_line_number == 1.0, not > 1.
        source_text = "\n".join(f"line {i}" for i in range(1, 11))
        graph_a, _, _ = self.map_single(10, source_text=source_text)
        self.assertEqual(graph_a["nodes"][0]["line_number"], 10)
        self.assertEqual(graph_a["nodes"][0]["rel_line_number"], 1.0)

    def test_ifdef_multi_branch_source_positions_stay_in_range(self) -> None:
        source_text = (
            "int target(int x) {\n"
            "#ifdef CONFIG_A\n"
            "    return x + 1;\n"
            "#else\n"
            "    return x - 1;\n"
            "#endif\n"
            "}\n"
        )
        total = len(source_text.splitlines())
        for line in (1, 3, 5, total):
            graph_a, _, _ = self.map_single(line, source_text=source_text)
            rel = graph_a["nodes"][0]["rel_line_number"]
            self.assertEqual(rel, line / total)
            self.assertGreaterEqual(rel, 0.0)
            self.assertLessEqual(rel, 1.0)

    def test_first_and_last_line_nodes(self) -> None:
        source_text = "a\nb\nc\nd\ne"
        first, _, _ = self.map_single(1, source_text=source_text)
        last, _, _ = self.map_single(5, source_text=source_text)
        self.assertEqual(first["nodes"][0]["rel_line_number"], 0.2)
        self.assertEqual(last["nodes"][0]["rel_line_number"], 1.0)

    def test_missing_line_inherits_nearest_ast_parent(self) -> None:
        payload = _single_node_payload(None)
        parent = {
            "joern_id": "20",
            "label": "BLOCK",
            "code": "{ ... }",
            "line_number": 4,
            "column_number": 1,
        }
        child = {
            "joern_id": "21",
            "label": "CALL",
            "code": "f()",
            "line_number": None,
            "column_number": None,
        }
        payload["nodes"] = [parent, child]
        payload["ast_edges"] = [{"src": "20", "dst": "21"}]
        graph_a, _, _ = _map_payload(
            payload,
            sample_id="row-inherit",
            cwe=None,
            project_wise_split=None,
            seen_project_split=None,
            project_name=None,
            commit_id=None,
            source_text="\n".join(["x"] * 8),
            config=JoernConfig(),
            joern_logs="",
        )
        self.assertEqual(graph_a["nodes"][1]["line_number"], 4)
        self.assertEqual(graph_a["nodes"][1]["rel_line_number"], 0.5)

    def test_line_outside_source_range_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "outside the function source range"):
            self.map_single(42, source_text=_SOURCE_TEXT)

    def test_all_positions_in_default_payload_respect_unit_interval(self) -> None:
        config = JoernConfig()
        graph_a, graph_b, _ = _map_payload(
            _payload(),
            sample_id="row-inv",
            cwe=None,
            project_wise_split=None,
            seen_project_split=None,
            project_name=None,
            commit_id=None,
            source_text=_SOURCE_TEXT,
            config=config,
            joern_logs="",
        )
        for node in graph_a["nodes"] + graph_b["nodes"]:
            self.assertGreaterEqual(node["rel_line_number"], 0.0)
            self.assertLessEqual(node["rel_line_number"], 1.0)


class ExtractLanguageIntegrationTests(unittest.TestCase):
    def run_extract_with_mock(
        self, source: Path, extractor: JoernExtractor
    ) -> tuple[list[str], Path]:
        captured: list[str] = []

        def fake_run(stage: str, command: list[str], working_dir: Path):
            if stage == "parse":
                captured.extend(command)
                cpg = Path(command[command.index("--output") + 1])
                cpg.write_bytes(b"mock-cpg")
                return subprocess.CompletedProcess(command, 0, "", "")
            raise JoernExecutionError("extract", "stop after parse")

        with patch.object(extractor, "_run_stage", side_effect=fake_run):
            with self.assertRaisesRegex(JoernExecutionError, "stop after parse"):
                extractor.extract(
                    source,
                    source.parent / "out",
                    sample_id="lang-smoke",
                    function_name="f",
                )
        report_path = source.parent / "out" / "lang-smoke.metrics.json"
        return captured, report_path

    def test_cpp_source_gets_cpp_extension_and_report_language(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "sample.c"
            source.write_text("int Foo::bar() { return this->x; }")
            extractor = JoernExtractor()
            command, report_path = self.run_extract_with_mock(source, extractor)
            parse_input = command[-1]
            self.assertTrue(parse_input.endswith(".cpp"), parse_input)
            report = json.loads(report_path.read_text())
            self.assertEqual(report["detected_language"], "cpp")

    def test_c_source_gets_c_extension_and_report_language(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "sample.c"
            source.write_text("int target(void) { return 1; }")
            extractor = JoernExtractor()
            command, report_path = self.run_extract_with_mock(source, extractor)
            self.assertTrue(command[-1].endswith(".c"), command[-1])
            report = json.loads(report_path.read_text())
            self.assertEqual(report["detected_language"], "c")

    def test_undetectable_language_writes_diagnostic_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "empty.c"
            source.write_text("// comment only\n")
            extractor = JoernExtractor()
            with self.assertRaisesRegex(
                JoernExecutionError, "Cannot determine source language"
            ):
                extractor.extract(
                    source,
                    root / "out",
                    sample_id="no-language",
                    function_name="f",
                )
            report = json.loads(
                (root / "out" / "no-language.metrics.json").read_text()
            )
            self.assertEqual(report["error_stage"], "language_detection")
            graph_b = json.loads(
                (root / "out" / "no-language.graph_b.json").read_text()
            )
            self.assertEqual(graph_b["status"], "AST_EXTRACTION_ERROR")
            self.assertEqual(graph_b["ddg_status"], "NOT_COMPUTED")


if __name__ == "__main__":
    unittest.main()

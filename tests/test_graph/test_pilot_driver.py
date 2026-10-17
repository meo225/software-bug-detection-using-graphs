"""Focused controlled-driver tests. Every extraction/process boundary is mocked."""
import copy
import hashlib
import inspect
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import create_autospec

import pytest

from scripts import run_graph_extraction as driver
from src.graph.joern import JoernConfig, JoernExecutionError, JoernExtractor, _map_payload

REAL_EXTRACT = JoernExtractor.extract
CONFIG = driver.ROOT / "configs/graph/schema_spec.yaml"


def fixture_data(index=0, source=None):
    record = dict(project="sample-project", commit_id="a" * 40, cwe=[], target=1,
                  func=source or f"int f{index}(void) {{\r\n return 1;\r\n}}\n")
    row = dict(sample_id=f"row-{index}", project=record["project"], commit=record["commit_id"], cwe="",
               label="vulnerable", source_reference=f"dataset row sample_id=row-{index}",
               source_sha256=driver.source_sha256(record))
    return record, row


@pytest.fixture(autouse=True)
def no_real_subprocess(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("A driver unit test attempted a real subprocess")
    monkeypatch.setattr(subprocess, "run", forbidden)


def install_extractor(monkeypatch, action):
    # Autospec preserves the REAL required function_name keyword and full contract.
    def invoke(self, source_path, output_dir, *, sample_id, function_name,
               cwe=None, project_wise_split=None, seen_project_split=None,
               project_name=None, commit_id=None):
        args = dict(sample_id=sample_id, function_name=function_name, cwe=cwe,
                    project_wise_split=project_wise_split, seen_project_split=seen_project_split,
                    project_name=project_name, commit_id=commit_id)
        return action(self, source_path, output_dir, args)
    mock = create_autospec(REAL_EXTRACT, side_effect=invoke)
    monkeypatch.setattr(JoernExtractor, "extract", mock)
    return mock


def valid_artifacts(extractor, source, output, args, *, ddg=False):
    # Reuse the real schema mapper for fixture serialization, never invoke Joern.
    name = args["function_name"]
    logs = (f"Calculating reaching definitions for: {name} in source.c\n"
            f"Number of definitions for {name}: 3\n") if ddg else ""
    raw = dict(method_full_name=name, dataflow_pass_attempted=ddg,
               dataflow_pass_completed=ddg, dataflow_applied_after=ddg, dataflow_applied_before=False,
               nodes=[dict(joern_id=str(i), label=label, code=code, line_number=line)
                      for i, label, code, line in [(0, "METHOD", name, 1), (1, "BLOCK", "{}", 2), (2, "RETURN", "return 1", 2)]],
               ast_edges=[dict(src="0", dst="1"), dict(src="1", dst="2")],
               cfg_edges=[dict(src="1", dst="2")],
               ddg_edges=[dict(src="0", dst="2")] if ddg else [])
    a, b, metrics = _map_payload(raw, sample_id=args["sample_id"], cwe=args["cwe"],
        project_wise_split=args["project_wise_split"], seen_project_split=args["seen_project_split"],
        project_name=args["project_name"], commit_id=args["commit_id"],
        source_text=source.read_bytes().decode("utf-8"), config=extractor.config, joern_logs=logs)
    metrics.update(sample_id=args["sample_id"], function_name=name, source=str(source),
                   status=b["status"], parse_succeeded=True, error_stage=None, error_message=None,
                   joern_method_full_name=name)
    for stage in ("parse", "extract"):
        driver._event(extractor.audit_log_path, stage=stage, status="SUCCESS",
            command=["mock-joern", stage], executed_command=["mock-joern", stage], exit_code=0,
            stdout=logs if stage == "extract" else "", stderr="")
    for suffix, payload in (("graph_a", a), ("graph_b", b), ("metrics", metrics)):
        (output / f"{args['sample_id']}.{suffix}.json").write_text(json.dumps(payload), encoding="utf-8")
    return SimpleNamespace(report=metrics)


def extract(tmp_path, rows, records):
    return driver.run_full_extraction(rows, records, [], tmp_path / "validated_v2", CONFIG)


def summary_of(error):
    return json.loads(error.value.summary_path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("sample_id", [" row-0", "row-0 ", "row-0\n", "row-٠", "row-01"])
def test_strict_ids(sample_id):
    with pytest.raises(driver.ManifestValidationError):
        driver.parse_sample_id(sample_id)


def test_exact_utf8_bytes():
    record, _ = fixture_data()
    assert driver.source_sha256(record) == hashlib.sha256(record["func"].encode("utf-8")).hexdigest()
    assert driver.source_sha256(record) != driver.source_sha256(dict(record, func=record["func"].replace("\r\n", "\n")))


@pytest.mark.parametrize("source,name", [
    ("int f(void) { return 1; }", "f"),
    ("/* decoy() { } */ static int f(int (*callback)(int)) { return callback(1); }", "f"),
    ('int f(char a[]) { const char *x = "fake() { }"; return 1; }', "f"),
    ("void ns::Widget::run() const noexcept { }", "run"),
    ("int f() __attribute__((used)) { return 1; }", "f"),
    ("Widget::~Widget() { }", "~Widget"),
    ("legacy_name(struct context *ctx, int value) { return value; }", "legacy_name"),
])
def test_method_resolution(source, name):
    assert driver.resolve_function_name(source) == name


@pytest.mark.parametrize("source", ["", "int declaration(void);", "switch (value) { default: break; }",
    "int f() {} int g() {}", "WRAPPER(real_name) { }", "int f( { }", "int f() {",
    "#ifdef A\nint f() {}\n#else\nint g() {}\n#endif", "int (*f)(int) { return 1; }",
    "API(annotation) int f() { return 1; }", "int operator()(int x) { return x; }",
    "catch (Error e) { }", "return f() { }", "wrapper(real_name) { }"])
def test_unresolved_or_ambiguous_source_rejected(source):
    with pytest.raises(driver.ManifestValidationError):
        driver.resolve_function_name(source)


def test_real_extractor_contract_and_redaction_context(tmp_path, monkeypatch):
    record, row = fixture_data()
    def action(extractor, source, output, args):
        inspect.signature(REAL_EXTRACT).bind(extractor, source, output, **args)
        assert args["function_name"] == "f0"
        assert args["project_name"] == record["project"]
        assert args["commit_id"] == record["commit_id"]
        assert args["cwe"] == ""
        assert source.read_bytes() == record["func"].encode("utf-8")
        return valid_artifacts(extractor, source, output, args, ddg=True)
    mock = install_extractor(monkeypatch, action)
    summary = extract(tmp_path, [row], {0: record})
    assert json.loads(summary.read_text())["status"] == "SUCCESS"
    assert mock.call_count == 1
    files = {p.name for p in (tmp_path / "validated_v2/row-0").iterdir()}
    assert files == {"row-0.graph_a.json", "row-0.graph_b.json", "row-0.metrics.json", "identity.json", "stages.jsonl"}
    with pytest.raises(TypeError, match="function_name"):
        mock(None, Path("src"), Path("out"), sample_id="row-0")


@pytest.mark.parametrize("mode", ["--validate-only", "--preflight"])
def test_preflight_and_validation_do_not_launch_processes(tmp_path, monkeypatch, capsys, mode):
    record, row = fixture_data()
    manifest, dataset, evidence = (tmp_path / name for name in ("manifest.csv", "data.jsonl", "evidence.txt"))
    driver.write_manifest([row], manifest)
    dataset.write_text(json.dumps(record) + "\n", encoding="utf-8")
    monkeypatch.setattr(driver, "_make_extractor", lambda *args: pytest.fail("Extractor instantiated during preflight"))
    monkeypatch.setattr(sys, "argv", ["run_graph_extraction.py", mode, "--manifest", str(manifest),
        "--dataset", str(dataset), "--evidence-out", str(evidence)])
    assert driver.main() == 0
    assert "PASS" in evidence.read_text(encoding="utf-8")
    assert not (tmp_path / "validated_v2").exists()
    capsys.readouterr()


@pytest.mark.parametrize("field,value", [("project", "wrong"), ("commit", "wrong"), ("cwe", "CWE-1"),
    ("label", "non-vulnerable"), ("source_sha256", "0" * 64), ("source_sha256", ""),
    ("source_sha256", "z" * 64), ("sample_id", "row-9"), ("sample_id", "../escape"),
    ("source_reference", "dataset row sample_id=row-1")])
def test_invalid_stops_before_extractor_and_later_sample(tmp_path, monkeypatch, field, value):
    record, row = fixture_data()
    later, later_row = fixture_data(1)
    row[field] = value
    monkeypatch.setattr(driver, "_make_extractor", lambda *args: pytest.fail("Invalid sample reached extractor"))
    with pytest.raises(driver.DriverRunError) as error:
        extract(tmp_path, [row, later_row], {0: record, 1: later})
    result = summary_of(error)
    assert [e["status"] for e in result["samples"]] == ["FAILED", "NOT_RUN"]
    assert Path(result["samples"][0]["quarantine"]).is_dir()
    assert not (tmp_path / "validated_v2").exists()


@pytest.mark.parametrize("source", ["switch (x) { default: break; }", "int f() {} int g() {}"])
def test_resolution_failure_quarantined_and_stops(tmp_path, monkeypatch, source):
    record, row = fixture_data(source=source)
    later, later_row = fixture_data(1)
    monkeypatch.setattr(driver, "_make_extractor", lambda *args: pytest.fail("Unresolved method reached extractor"))
    with pytest.raises(driver.DriverRunError) as error:
        extract(tmp_path, [row, later_row], {0: record, 1: later})
    result = summary_of(error)
    assert result["samples"][0]["failed_stage"] == "method_resolution"
    assert result["samples"][1]["status"] == "NOT_RUN"


def test_extraction_failure_stops_and_retains_incomplete_staging(tmp_path, monkeypatch):
    records, rows = zip(*(fixture_data(i) for i in range(3)))
    calls = []
    def action(extractor, source, output, args):
        calls.append(args["sample_id"])
        if args["sample_id"] == "row-1":
            (output / "partial.json").write_text("partial")
            raise RuntimeError("simulated extractor failure")
        return valid_artifacts(extractor, source, output, args)
    install_extractor(monkeypatch, action)
    with pytest.raises(driver.DriverRunError) as error:
        extract(tmp_path, list(rows), dict(enumerate(records)))
    result = summary_of(error)
    assert calls == ["row-0", "row-1"]
    assert [e["status"] for e in result["samples"]] == ["SUCCESS", "FAILED", "NOT_RUN"]
    quarantine = Path(result["samples"][1]["quarantine"])
    assert (quarantine / "partial.json").read_text() == "partial"
    assert (quarantine / "source.c").read_bytes() == records[1]["func"].encode("utf-8")
    assert (tmp_path / "validated_v2/row-0/row-0.graph_a.json").is_file()
    assert not (tmp_path / "validated_v2/row-1").exists()


def test_publication_failure_retains_prior_and_current_completed_outputs(tmp_path, monkeypatch):
    records, rows = zip(*(fixture_data(i) for i in range(3)))
    install_extractor(monkeypatch, valid_artifacts)
    real_copy = driver.shutil.copyfile
    def broken_copy(src, dst):
        if Path(src).name == "row-1.graph_b.json":
            raise OSError("simulated disk failure")
        return real_copy(src, dst)
    monkeypatch.setattr(driver.shutil, "copyfile", broken_copy)
    with pytest.raises(driver.DriverRunError) as error:
        extract(tmp_path, list(rows), dict(enumerate(records)))
    result = summary_of(error)
    assert [e["status"] for e in result["samples"]] == ["SUCCESS", "FAILED", "NOT_RUN"]
    assert result["samples"][1]["failed_stage"] == "publication"
    quarantine = Path(result["samples"][1]["quarantine"])
    assert len(list(quarantine.glob("row-1.*.json"))) == 3
    assert Path(result["samples"][1]["publication_partial"]).parent == quarantine
    assert (quarantine / "publication_partial/row-1.graph_a.json").exists()
    assert (tmp_path / "validated_v2/row-0/row-0.graph_a.json").exists()
    assert not (tmp_path / "validated_v2/row-1").exists()


@pytest.mark.parametrize("mutation", ["missing", "bad_json", "wrong_id", "cwe", "split", "nodes",
    "node_fields", "edge_type", "endpoint", "duplicate", "self_loop", "relative", "relative_nan",
    "source_line", "ddg", "metrics", "status", "source_bytes", "logs", "failure_status", "domain",
    "comment_node", "identity", "truncated", "wrong_method", "ddg_skip", "ddg_log_missing"])
def test_invalid_artifacts_never_published(tmp_path, monkeypatch, mutation):
    record, row = fixture_data()
    def action(extractor, source, output, args):
        result = valid_artifacts(extractor, source, output, args, ddg=mutation in {"ddg_skip", "ddg_log_missing"})
        path = output / "row-0.graph_b.json"
        b = json.loads(path.read_text())
        if mutation == "missing":
            path.unlink()
        elif mutation == "bad_json":
            path.write_text("{")
        elif mutation == "source_bytes":
            source.write_bytes(b"changed")
        elif mutation == "logs":
            extractor.audit_log_path.write_text("")
        else:
            if mutation == "wrong_id": b["sample_id"] = "row-9"
            elif mutation == "cwe": b["cwe"] = None
            elif mutation == "split": b["project_wise_split"] = "train"
            elif mutation == "nodes": b["nodes"][0]["id"] = 99
            elif mutation == "node_fields": b["nodes"][0]["project"] = "leak"
            elif mutation == "edge_type": b["edges"][0]["type"] = 9
            elif mutation == "endpoint": b["edges"][0]["dst"] = 99
            elif mutation == "duplicate": b["edges"].append(copy.deepcopy(b["edges"][0])); b["num_edges"] += 1
            elif mutation == "self_loop": b["edges"][0]["dst"] = b["edges"][0]["src"]
            elif mutation == "relative": b["nodes"][0]["rel_line_number"] = 0.7
            elif mutation == "relative_nan": b["nodes"][0]["rel_line_number"] = float("nan")
            elif mutation == "source_line": b["nodes"][0]["line_number"] = 100
            elif mutation == "domain": b["nodes"][0]["code_token"] = "different node"
            elif mutation == "comment_node": b["nodes"][0]["node_type"] = "Comment"
            elif mutation == "ddg": b["ddg_status"] = "EDGES_PRESENT"
            elif mutation == "identity":
                audit_path = output / "identity.json"
                audit = json.loads(audit_path.read_text()); audit["source_sha256"] = "0" * 64
                audit_path.write_text(json.dumps(audit))
            elif mutation in {"truncated", "wrong_method"}:
                metrics_path = output / "row-0.metrics.json"
                metrics = json.loads(metrics_path.read_text())
                if mutation == "truncated": metrics["oversized"]["truncated"] = True
                else: metrics["joern_method_full_name"] = "unrelated_function"
                metrics_path.write_text(json.dumps(metrics))
            elif mutation in {"ddg_skip", "ddg_log_missing"}:
                # Contradictory/absent log evidence must defeat EDGES_PRESENT,
                # even with actual DDG edges and completed overlay flags.
                events = [json.loads(line) for line in extractor.audit_log_path.read_text().splitlines()]
                if mutation == "ddg_skip":
                    events[-1]["stderr"] = "f0 has more than 4000 definitions\nSkipping.\n"
                else:
                    events[-1]["stdout"] = ""
                extractor.audit_log_path.write_text("".join(json.dumps(event) + "\n" for event in events))
            elif mutation == "status": b["status"] = "OVERSIZED_GRAPH"
            elif mutation == "failure_status": b["status"] = "PARSE_ERROR"
            elif mutation == "metrics":
                metrics_path = output / "row-0.metrics.json"
                metrics = json.loads(metrics_path.read_text()); metrics["function_name"] = "wrong"
                metrics_path.write_text(json.dumps(metrics))
            path.write_text(json.dumps(b))
        return result
    install_extractor(monkeypatch, action)
    with pytest.raises(driver.DriverRunError) as error:
        extract(tmp_path, [row], {0: record})
    result = summary_of(error)
    assert result["samples"][0]["failed_stage"] == "acceptance"
    assert Path(result["samples"][0]["quarantine"]).is_dir()
    assert not (tmp_path / "validated_v2").exists()


def test_real_failure_schema_validated_in_quarantine(tmp_path, monkeypatch):
    record, row = fixture_data()
    def action(extractor, source, output, args):
        report = dict(sample_id=args["sample_id"], source=str(source), function_name=args["function_name"], parse_succeeded=False)
        extractor._write_failure_outputs(output / "row-0.graph_a.json", output / "row-0.graph_b.json", report,
            sample_id=args["sample_id"], cwe=args["cwe"], project_wise_split=None, seen_project_split=None,
            status="PARSE_ERROR", stage="parse", message="mock parse failure")
        (output / "row-0.metrics.json").write_text(json.dumps(report))
        raise JoernExecutionError("parse", "mock parse failure")
    install_extractor(monkeypatch, action)
    with pytest.raises(driver.DriverRunError) as error:
        extract(tmp_path, [row], {0: record})
    result = summary_of(error)
    assert result["samples"][0]["failure_artifacts"] == "VALID_FAILURE_SCHEMA"
    assert not (tmp_path / "validated_v2").exists()


@pytest.mark.parametrize("mode", ["success", "nonzero", "timeout"])
def test_stage_logging_records_commands_results_and_timeouts(tmp_path, monkeypatch, mode):
    from unittest.mock import Mock
    completed = subprocess.CompletedProcess(["mock-wsl", "mock-joern"], 7 if mode == "nonzero" else 0, "stdout evidence", "stderr evidence")
    result = subprocess.TimeoutExpired(["mock-joern"], 120, output=b"partial stdout", stderr=b"partial stderr") if mode == "timeout" else completed
    if driver.os.name == "nt":
        mock = Mock(side_effect=result) if mode == "timeout" else Mock(return_value=result)
        monkeypatch.setattr(JoernExtractor, "_run_wsl", mock)
    else:
        mock = Mock(side_effect=result) if mode == "timeout" else Mock(return_value=result)
        monkeypatch.setattr(subprocess, "run", mock)
    path = tmp_path / "stages.jsonl"
    extractor = driver._make_extractor(JoernConfig(), path)
    if mode == "success":
        assert extractor._run_stage("extract", ["mock-joern"], tmp_path).returncode == 0
    else:
        with pytest.raises((JoernExecutionError, subprocess.TimeoutExpired)):
            extractor._run_stage("extract", ["mock-joern"], tmp_path)
    events = [json.loads(line) for line in path.read_text().splitlines()]
    assert events[0]["command"] == ["mock-joern"]
    assert events[-1]["exit_code"] == (None if mode == "timeout" else completed.returncode)
    assert events[-1]["stdout"] and events[-1]["stderr"]
    assert events[-1]["status"] == {"success": "SUCCESS", "nonzero": "FAILED", "timeout": "TIMEOUT"}[mode]


def test_existing_output_and_historical_artifacts_untouched(tmp_path, monkeypatch):
    record, row = fixture_data()
    old = tmp_path / "row-0.graph_a.json"; old.write_bytes(b"historical")
    output = tmp_path / "validated_v2"; output.mkdir(); marker = output / "existing"; marker.write_bytes(b"existing")
    monkeypatch.setattr(driver, "_make_extractor", lambda *args: pytest.fail("Collision reached extractor"))
    with pytest.raises(driver.ManifestValidationError, match="overwrite"):
        extract(tmp_path, [row], {0: record})
    assert old.read_bytes() == b"historical" and marker.read_bytes() == b"existing"


def test_ddg_skip_evidence_accepts_only_incomplete_status(tmp_path, monkeypatch):
    from src.graph.joern import _ddg_method_log_evidence
    record, row = fixture_data()
    def action(extractor, source, output, args):
        result = valid_artifacts(extractor, source, output, args, ddg=True)
        events = [json.loads(line) for line in extractor.audit_log_path.read_text().splitlines()]
        events[-1]["stderr"] = "f0 has more than 4000 definitions\nSkipping.\n"
        extractor.audit_log_path.write_text("".join(json.dumps(e) + "\n" for e in events))
        path = output / "row-0.graph_b.json"; b = json.loads(path.read_text())
        b["ddg_status"] = "INCOMPLETE"; path.write_text(json.dumps(b))
        path = output / "row-0.metrics.json"; metrics = json.loads(path.read_text())
        metrics["ddg_status"] = "INCOMPLETE"
        metrics["ddg_completion_evidence"] = _ddg_method_log_evidence("f0", events[-1]["stdout"] + "\n" + events[-1]["stderr"])
        path.write_text(json.dumps(metrics)); result.report = metrics
        return result
    install_extractor(monkeypatch, action)
    result = extract(tmp_path, [row], {0: record})
    assert json.loads(result.read_text())["status"] == "SUCCESS"
    assert json.loads((tmp_path / "validated_v2/row-0/row-0.graph_b.json").read_text())["ddg_status"] == "INCOMPLETE"


def test_log_failure_still_quarantines_and_stops(tmp_path, monkeypatch):
    record, row = fixture_data()
    later, later_row = fixture_data(1)
    def action(extractor, source, output, args):
        raise RuntimeError("extract failure")
    install_extractor(monkeypatch, action)
    real_event = driver._event
    def broken_log(path, **entry):
        if entry["status"] == "FAILED":
            raise OSError("log disk failure")
        real_event(path, **entry)
    monkeypatch.setattr(driver, "_event", broken_log)
    with pytest.raises(driver.DriverRunError) as error:
        extract(tmp_path, [row, later_row], {0: record, 1: later})
    result = summary_of(error)
    assert result["samples"][0]["log_error"] == "log disk failure"
    assert Path(result["samples"][0]["quarantine"]).is_dir()
    assert result["samples"][1]["status"] == "NOT_RUN"


@pytest.mark.parametrize("corruption", ["metadata", "hash"])
def test_enrichment_does_not_bless_corrupt_manifest(tmp_path, corruption):
    record, row = fixture_data()
    if corruption == "metadata":
        row["project"] = "wrong"
    else:
        row["source_sha256"] = "0" * 64
    dataset = tmp_path / "data.jsonl"
    dataset.write_text(json.dumps(record) + "\n", encoding="utf-8")
    manifest = tmp_path / "manifest.csv"
    driver.write_manifest([row], manifest)
    before = manifest.read_bytes()
    with pytest.raises(driver.ManifestValidationError, match="Enrichment rejected"):
        driver.enrich_manifest(manifest, dataset)
    assert manifest.read_bytes() == before


def test_backup_and_unknown_fields_preserved(tmp_path):
    record, row = fixture_data()
    row.pop("source_sha256")
    row["custom"] = "retain,exactly\nincluding newline"
    manifest = tmp_path / "manifest.csv"
    # write_manifest adds an empty hash column, so use the existing CSV helper directly.
    import csv
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row), lineterminator="\n")
        writer.writeheader()
        writer.writerow(row)
    before = manifest.read_bytes()
    dataset = tmp_path / "data.jsonl"
    dataset.write_text(json.dumps(record) + "\n", encoding="utf-8")
    driver.enrich_manifest(manifest, dataset)
    backup = tmp_path / "manifest.csv.baseline.csv"
    assert backup.read_bytes() == before
    assert Path(str(backup) + ".sha256").read_text(encoding="ascii").strip() == hashlib.sha256(before).hexdigest()
    once = manifest.read_bytes()
    driver.enrich_manifest(manifest, dataset)
    assert manifest.read_bytes() == once
    assert driver.read_manifest(manifest)[0]["custom"] == row["custom"]


@pytest.mark.parametrize("line", ["\n", "bad json\n", "[]\n"])
def test_malformed_dataset_fails_closed(tmp_path, line):
    path = tmp_path / "data.jsonl"
    path.write_text(line, encoding="utf-8")
    with pytest.raises(driver.ManifestValidationError):
        driver.load_records_at_indices(path, {0})

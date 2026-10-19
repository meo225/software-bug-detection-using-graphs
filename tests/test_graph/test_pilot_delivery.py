"""Synthetic delivery fixtures only; no production artifacts or runtime calls."""
import copy
import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from scripts import export_pilot_delivery as delivery
from scripts import run_graph_extraction as driver
from src.graph import joern

REAL_GIT_DIFF_CHECK = delivery.git_diff_check


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(delivery.encode(value))


@pytest.fixture(autouse=True)
def prohibit_extraction(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Delivery attempted a subprocess or extraction")
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(joern.JoernExtractor, "extract", forbidden)
    monkeypatch.setattr(joern.JoernExtractor, "_run_wsl", forbidden)
    monkeypatch.setattr(joern.JoernExtractor, "_to_wsl_path", forbidden)
    monkeypatch.setattr(driver, "run_full_extraction", forbidden)
    monkeypatch.setattr(driver, "_make_extractor", forbidden)
    # A fixture directory is not a Git checkout. Only this fixed Git integrity
    # check is substituted, never the real artifact gate or schema mapper.
    monkeypatch.setattr(delivery, "git_diff_check", lambda root: None)


@pytest.fixture
def cohort(tmp_path):
    root = tmp_path / "synthetic-repository"
    (root / "reports/graph").mkdir(parents=True)
    (root / "data/graphs").mkdir(parents=True)
    control = root / "protected.txt"
    control.write_text("synthetic immutable input", encoding="utf-8")
    config = joern.JoernConfig()
    entries = []
    for order, sid in enumerate(delivery.IDS):
        index = driver.parse_sample_id(sid)
        function = f"function{index}"
        source = f"int {function}(void) {{\n return 1;\n}}\n"
        if sid in delivery.UNSUPPORTED:
            source = "switch (x) { default: break; }\n"
        cwe = [] if order % 3 == 0 else ["CWE-119", "CWE-787"] if order % 3 == 1 else ["CWE-617"]
        record = dict(project="fixture-project", commit_id="a" * 40,
                      target=1, cwe=cwe, func=source)
        row = dict(sample_id=sid, project=record["project"], commit=record["commit_id"],
                   label="vulnerable", cwe="|".join(cwe),
                   source_reference=f"dataset row sample_id={sid}",
                   source_sha256=driver.source_sha256(record))
        state = "FAILED" if sid in delivery.FAILED else "UNSUPPORTED" if sid in delivery.UNSUPPORTED else "SUCCESS"
        if state == "UNSUPPORTED":
            entries.append(delivery.Entry(row, record, state, None, None, (), {}))
            continue
        run = root / "synthetic-evidence" / sid
        stage = run / "sample-000" if state == "SUCCESS" else run / "quarantine/sample-000"
        stage.mkdir(parents=True)
        (stage / "source.c").write_bytes(source.encode("utf-8"))
        write(stage / "identity.json", dict(manifest_entry=row, dataset_index=index,
              source_sha256=row["source_sha256"], function_name=function, configuration=vars(config)))
        logs = (f"Calculating reaching definitions for: {function} in source.c\n"
                f"Number of definitions for {function}: 3\n")
        raw = dict(method_full_name=function, dataflow_pass_attempted=True,
            dataflow_pass_completed=True, dataflow_applied_before=False, dataflow_applied_after=True,
            nodes=[dict(joern_id=str(n), label=label, code=code, line_number=line)
                   for n, label, code, line in [(0, "METHOD", function, 1),
                       (1, "BLOCK", "{}", 2), (2, "RETURN", "return 1", 2)]],
            ast_edges=[dict(src="0", dst="1"), dict(src="1", dst="2")],
            cfg_edges=[dict(src="1", dst="2")], ddg_edges=[dict(src="0", dst="2")])
        a, b, metrics = joern._map_payload(raw, sample_id=sid, cwe=row["cwe"],
            project_wise_split=None, seen_project_split=None, project_name=row["project"],
            commit_id=row["commit"], source_text=source, config=config, joern_logs=logs)
        metrics.update(sample_id=sid, function_name=function, source=str(stage / "source.c"),
            parse_succeeded=True, error_stage=None, error_message=None, status=b["status"],
            joern_method_full_name=function)
        log_events = [dict(stage="parse", status="SUCCESS", exit_code=0,
                          command=["synthetic-parse"], stdout="", stderr=""),
                      dict(stage="extract", status="SUCCESS", exit_code=0,
                          command=["synthetic-extract"], stdout=logs, stderr="")]
        if state == "FAILED":
            reason = f"Expected exactly one method named {function}, found 0"
            for graph in (a, b):
                graph.update(status="AST_EXTRACTION_ERROR", ddg_status="NOT_COMPUTED",
                             nodes=[], edges=[], num_nodes=0, num_edges=0, error_message=reason)
            metrics.update(source=str(run / "sample-000/source.c"), status="AST_EXTRACTION_ERROR",
                           error_stage="extract", error_message=reason, ddg_status="NOT_COMPUTED")
            log_events[1].update(status="FAILED", exit_code=1, stdout="", stderr=reason)
        for suffix, value in (("graph_a", a), ("graph_b", b), ("metrics", metrics)):
            write(stage / f"{sid}.{suffix}.json", value)
        (stage / "stages.jsonl").write_text("\n".join(json.dumps(e) for e in log_events) + "\n", encoding="utf-8")
        publication = stage
        if state == "SUCCESS":
            publication = root / "accepted" / sid
            publication.mkdir(parents=True)
            for name in ("identity.json", "stages.jsonl", f"{sid}.graph_a.json",
                         f"{sid}.graph_b.json", f"{sid}.metrics.json"):
                (publication / name).write_bytes((stage / name).read_bytes())
        attempt = run / "run_summary.json"
        write(attempt, {"sample_id": sid, "status": state})
        history = [delivery.reference(root, attempt)]
        if sid == "row-1601":
            earlier = run / "earlier-environment-failure.json"
            write(earlier, {"status": "FAILED", "error": "WinError 5 before Joern"})
            history.insert(0, delivery.reference(root, earlier))
        hashes = {p.name: delivery.sha(p) for p in publication.iterdir() if p.is_file()}
        entries.append(delivery.Entry(row, record, state, publication, stage, tuple(history), hashes))
    return root, delivery.Plan(tuple(entries), config, {"protected.txt": delivery.sha(control)})


def refresh(entry):
    return replace(entry, hashes={p.name: delivery.sha(p) for p in entry.publication.iterdir() if p.is_file()})


def change_graph(entry, kind, callback):
    path = entry.publication / f"{entry.row['sample_id']}.{kind}.json"
    graph = delivery.read(path)
    callback(graph)
    write(path, graph)
    if entry.publication != entry.staging:
        write(entry.staging / path.name, graph)
    return refresh(entry)


def test_full_synthetic_export_60_json_two_manifests(cohort):
    root, plan = cohort
    before = delivery.inventory(root)
    evidence = delivery.export(root, plan)
    package = root / "reports/graph/3_2_pilot"
    delivery.validate_package(root, package, plan)
    assert len(list(package.rglob("*.json"))) == 60
    assert len(list(package.rglob("manifest.csv"))) == 2
    receipt = delivery.read(evidence / "final_integrity.json")
    assert receipt["V7_V8"] == "PASS" and len(receipt["files"]) == 62
    delivery.verify_hashes(root, before)
    for entry in plan.entries:
        for kind in delivery.KINDS:
            exported = delivery.read(package / kind / f"{entry.row['sample_id']}.json")
            assert exported["cwe"] == entry.row["cwe"]
            assert exported["project_wise_split"] is None and exported["seen_project_split"] is None
            if entry.status != "UNSUPPORTED":
                original = delivery.read(entry.publication / f"{entry.row['sample_id']}.{kind}.json")
                assert delivery.equal_typed({k: v for k, v in exported.items() if k not in delivery.FIELDS}, original)
            else:
                assert exported["status"] == "UNSUPPORTED_SOURCE_REPRESENTATION"
                assert exported["nodes"] == exported["edges"] == []
                assert exported["ddg_status"] == "NOT_COMPUTED"
    text = (package / "graph_a/manifest.csv").read_text()
    assert "earlier-environment-failure.json" in text and "WinError" not in text


def test_real_gate_is_replayed_not_mocked(cohort, monkeypatch):
    root, plan = cohort
    calls = []
    original_gate = driver.validate_artifacts
    def observed(*args, **kwargs):
        calls.append(args[1]["sample_id"])
        return original_gate(*args, **kwargs)
    monkeypatch.setattr(driver, "validate_artifacts", observed)
    delivery.validate_plan(root, plan)
    assert len(calls) == 25 and len(set(calls)) == 25


@pytest.mark.parametrize("value", [True, 1.0])
def test_typed_projection_distinguishes_bool_int_float(value):
    assert not delivery.equal_typed({"x": [1]}, {"x": [value]})


def test_projection_retains_order_and_source_object():
    graph = {"nodes": [{"id": 0, "x": 1.0}], "edges": [], "status": "SUCCESS"}
    original = copy.deepcopy(graph)
    exported = delivery.delivery_object(graph, {"source_reference": "original"}, "extracted_graph")
    assert delivery.equal_typed({k: v for k, v in exported.items() if k not in delivery.FIELDS}, original)
    assert graph == original
    exported["nodes"][0]["x"] = 2
    assert graph == original
    assert not delivery.equal_typed({"a": 1, "b": 2}, {"b": 2, "a": 1})


@pytest.mark.parametrize("field", delivery.FIELDS)
def test_conflicting_delivery_keys_rejected(field):
    with pytest.raises(delivery.DeliveryError, match="Conflicting"):
        delivery.delivery_object({field: "previous"}, {"source_reference": "ref"}, "extracted_graph")


@pytest.mark.parametrize("mutation,match", [
    (lambda g: g.update(num_nodes=9), "Node count"),
    (lambda g: g.update(num_edges=9), "Edge count"),
    (lambda g: g["edges"][0].update(type=3), "Relation type"),
    (lambda g: g["edges"][0].update(src=True), "typed edge"),
    (lambda g: g["edges"][0].update(dst=99), "endpoint"),
    (lambda g: g["nodes"][0].update(code_token="different"), "Shared node domain"),
    (lambda g: g.update(project_wise_split="train"), "Metadata"),
    (lambda g: g.update(source_reference="old"), "Conflicting"),
])
def test_input_graph_corruption_rejected(cohort, mutation, match):
    root, plan = cohort
    entry = change_graph(plan.entries[0], "graph_a", mutation)
    with pytest.raises(delivery.DeliveryError, match=match):
        delivery.originals(root, entry, plan.config)


def test_shared_ast_mismatch(cohort):
    root, plan = cohort
    entry = change_graph(plan.entries[0], "graph_b", lambda g: g["edges"][0].update(src=2))
    with pytest.raises(delivery.DeliveryError, match="Shared AST"):
        delivery.originals(root, entry, plan.config)


def test_oversized_is_preserved_without_truncation(cohort):
    root, plan = cohort
    # Synthetic thresholds exercise the real unchanged gate's warning policy.
    config = joern.JoernConfig(max_nodes=2, max_edges=3)
    entry = plan.entries[0]
    identity = delivery.read(entry.staging / "identity.json")
    identity["configuration"] = vars(config)
    for folder in (entry.staging, entry.publication):
        write(folder / "identity.json", identity)
        for kind in delivery.KINDS:
            p = folder / f"{entry.row['sample_id']}.{kind}.json"
            graph = delivery.read(p); graph["status"] = "OVERSIZED_GRAPH"; write(p, graph)
        p = folder / f"{entry.row['sample_id']}.metrics.json"
        metrics = delivery.read(p); metrics.update(status="OVERSIZED_GRAPH")
        metrics["oversized"].update(graph_a=True, graph_b=True)
        write(p, metrics)
    entry = refresh(entry)
    graphs = delivery.originals(root, entry, config)
    assert len(graphs["graph_b"]["nodes"]) == 3
    assert len(graphs["graph_b"]["edges"]) == 4
    assert delivery.delivery_object(graphs["graph_b"], entry.row, "extracted_graph")["status"] == "OVERSIZED_GRAPH"


def test_duplicate_id_fails_before_any_output(cohort):
    root, plan = cohort
    duplicate = replace(plan.entries[1], row=plan.entries[0].row)
    plan = replace(plan, entries=(plan.entries[0], duplicate, *plan.entries[2:]))
    with pytest.raises(delivery.DeliveryError, match="cohort/order"):
        delivery.export(root, plan)
    assert not (root / "data/graphs/pilot_delivery_export_evidence").exists()


@pytest.mark.parametrize("field,value", [("source_sha256", "0" * 64),
                                         ("source_reference", "invented"), ("cwe", "wrong")])
def test_identity_corruption(cohort, field, value):
    root, plan = cohort
    first = replace(plan.entries[0], row={**plan.entries[0].row, field: value})
    with pytest.raises(delivery.DeliveryError, match="Source/metadata"):
        delivery.validate_plan(root, replace(plan, entries=(first, *plan.entries[1:])))


def test_artifact_hash_and_control_hash_mismatches(cohort):
    root, plan = cohort
    entry = plan.entries[0]
    with pytest.raises(delivery.DeliveryError, match="checksum"):
        delivery.originals(root, replace(entry, hashes={**entry.hashes, "identity.json": "0" * 64}), plan.config)
    with pytest.raises(delivery.DeliveryError, match="Checksum"):
        delivery.validate_plan(root, replace(plan, controls={"protected.txt": "0" * 64}))


def test_failure_reason_mismatch(cohort):
    root, plan = cohort
    entry = next(e for e in plan.entries if e.status == "FAILED")
    entry = change_graph(entry, "graph_b", lambda g: g.update(error_message="rewritten reason"))
    with pytest.raises(delivery.DeliveryError, match="reason/status"):
        delivery.originals(root, entry, plan.config)


def test_existing_destination_refused_even_if_empty(cohort):
    root, plan = cohort
    destination = root / "reports/graph/3_2_pilot"
    destination.mkdir()
    with pytest.raises(delivery.DeliveryError, match="already exists"):
        delivery.export(root, plan)
    assert not list(destination.iterdir())
    assert not (root / "data/graphs/pilot_delivery_export_evidence").exists()


def test_interrupted_publication_retains_complete_stage_and_failure(cohort, monkeypatch):
    root, plan = cohort
    def interrupted(stage, target):
        raise OSError("synthetic interrupted publication")
    monkeypatch.setattr(delivery, "publish_no_replace", interrupted)
    with pytest.raises(OSError, match="interrupted"):
        delivery.export(root, plan)
    assert not (root / "reports/graph/3_2_pilot").exists()
    stages = list((root / "reports/graph").glob(".3_2_pilot-export-*"))
    assert len(stages) == 1 and len(list(stages[0].rglob("*.json"))) == 60
    evidence = next((root / "data/graphs/pilot_delivery_export_evidence").iterdir())
    assert delivery.read(evidence / "failure.json")["published"] is False
    assert not (evidence / "final_integrity.json").exists()


def test_atomic_publish_refuses_collision(tmp_path):
    stage, target = tmp_path / "stage", tmp_path / "target"
    stage.mkdir(); target.mkdir()
    (target / "keep").write_text("unchanged")
    with pytest.raises(delivery.DeliveryError, match="collision"):
        delivery.publish_no_replace(stage, target)
    assert stage.exists() and (target / "keep").read_text() == "unchanged"


@pytest.mark.parametrize("mutation", ["hash", "count", "extra", "order"])
def test_package_validation_rejects_tampering(cohort, mutation):
    root, plan = cohort
    stage = root / "scratch-package"; stage.mkdir()
    delivery.build_package(root, stage, plan)
    if mutation == "extra":
        write(stage / "graph_a/extra.json", {})
    elif mutation == "order":
        p = stage / "graph_a/manifest.csv"
        lines = p.read_text().splitlines(); lines[1], lines[2] = lines[2], lines[1]
        p.write_text("\n".join(lines) + "\n")
    elif mutation == "hash":
        p = stage / "graph_a/manifest.csv"
        text = p.read_text(); digest = delivery.sha(stage / f"graph_a/{delivery.IDS[0]}.json")
        p.write_text(text.replace(digest, "0" * 64, 1))
    else:
        p = stage / f"graph_a/{delivery.IDS[0]}.json"
        g = delivery.read(p); g["num_edges"] += 1; write(p, g)
    with pytest.raises(delivery.DeliveryError):
        delivery.validate_package(root, stage, plan)


def test_cli_read_only_does_not_export(cohort, monkeypatch, capsys):
    root, plan = cohort
    monkeypatch.setattr(delivery, "load_plan", lambda path: plan)
    monkeypatch.setattr(delivery, "export", lambda *args: pytest.fail("Read-only CLI exported"))
    assert delivery.main(["--root", str(root), "--check-only"]) == 0
    assert "No export" in capsys.readouterr().out


def test_unapproved_id_cannot_be_unsupported():
    with pytest.raises(delivery.DeliveryError):
        delivery.unsupported({"sample_id": "row-0"}, "graph_a")


def test_duplicate_json_keys_and_nonfinite_values_rejected(tmp_path):
    p = tmp_path / "bad.json"
    for text in ('{"nodes": [], "nodes": []}', '{"value": NaN}'):
        p.write_text(text)
        with pytest.raises(delivery.DeliveryError):
            delivery.read(p)


def checkpoint_receipts(root, plan, monkeypatch):
    """Build a wholly synthetic replica of the fixed checkpoint receipt layout."""
    base = root / "data/graphs"
    manifest = root / "data/sample_manifests/diversevul_graph_sample.csv"
    manifest.parent.mkdir(parents=True)
    driver.write_manifest([e.row for e in plan.entries], manifest)
    dataset = root / "data/raw/diversevul/diversevul_20230702.json"
    dataset.parent.mkdir(parents=True)
    indexed = {driver.parse_sample_id(e.row["sample_id"]): e.record for e in plan.entries}
    with dataset.open("w", encoding="utf-8", newline="\n") as f:
        for index in range(max(indexed) + 1):
            f.write(json.dumps(indexed.get(index, {"fixture_placeholder": index})) + "\n")
    historical = root / delivery.HISTORICAL_REPORT
    final = root / delivery.FINAL_REPORT
    historical.write_text("synthetic historical report")
    final.write_text("synthetic final report")
    monkeypatch.setattr(delivery, "HISTORICAL_SHA256", delivery.sha(historical))
    monkeypatch.setattr(delivery, "FINAL_SHA256", delivery.sha(final))
    freeze = base / "v2_baseline_7a_evidence/freeze.json"
    write(freeze, {"query_sha256_utf8_lf": delivery.QUERY_SHA256,
                  "configuration": vars(plan.config), "protected_fingerprints": {
                      delivery.reference(root, manifest): delivery.sha(manifest),
                      delivery.reference(root, dataset): delivery.sha(dataset)}})
    latest = []
    old_entries = []
    old_attempts = []
    for e in plan.entries:
        sid = e.row["sample_id"]
        old_entries.append({"manifest_entry": e.row,
            "cohort_status": "NOT_RUN" if sid in {"row-11455", "row-11987"} else e.status,
            "latest_accepted_v2": str(e.publication) if e.status == "SUCCESS" else None})
        if sid in {"row-11455", "row-11987"}:
            latest.append(dict(sample_id=sid, status="SUCCESS", artifacts=str(e.publication),
                               staging=str(e.staging)))
        elif e.status == "FAILED":
            marker = "7b8_row1601" if sid == "row-1601" else "7b2" if sid == "row-6038" else "7b"
            path = base / f".v2_pilot_{marker}-run-fixture/run_summary.json"
            write(path, {"samples": [dict(sample_id=sid, status="FAILED", quarantine=str(e.staging))]})
        elif e.status == "SUCCESS":
            old_attempts.append(dict(sample_id=sid, status="SUCCESS", artifacts=str(e.publication)))
    write(base / ".older-run-fixture/run_summary.json", {"samples": old_attempts})
    write(base / ".v2_pilot_7b3-run-fixture/run_summary.json", {"samples": [
        dict(sample_id="row-1601", status="FAILED", error="WinError 5 before Joern")]})
    write(base / "v2_pilot_7b3_evidence/cohort_ledger.json", {"records": old_entries})
    for n in (1, 2):
        write(base / f"v2_repeatability_v1_evidence/attempt-{n}/result.json", {"status": "SUCCESS"})
    summary = dict(status="SUCCESS", samples=latest)
    summary_path = base / ".v2_pilot_7b9-run-fixture/run_summary.json"
    write(summary_path, summary)
    write(base / "v2_pilot_7b9_final_two_evidence/outcome.json", dict(status="SUCCESS", summary=summary,
        accepted=[dict(sample_id=e.row["sample_id"], published_sha256=e.hashes)
                  for e in plan.entries if e.row["sample_id"] in {"row-11455", "row-11987"}]))
    write(base / "v2_pilot_7b9_final_two_evidence/retained_run_summary.json",
          dict(path=str(summary_path), sha256=delivery.sha(summary_path), summary=summary))
    files = delivery.inventory(root)
    legacy_names = {delivery.HISTORICAL_REPORT: delivery.FINAL_REPORT,
                    delivery.FINAL_REPORT: delivery.LEGACY_FINAL_REPORT}
    write(base / "v2_pilot_7b9_final_two_evidence/baseline.json",
          {"protected_sha256": {str(root / legacy_names.get(p, p)): h
                                for p, h in files.items()}})


@pytest.fixture
def renamed_reports(tmp_path, monkeypatch):
    historical = tmp_path / delivery.HISTORICAL_REPORT
    final = tmp_path / delivery.FINAL_REPORT
    historical.parent.mkdir(parents=True)
    historical.write_bytes(b"synthetic historical\r\n")
    final.write_bytes(b"synthetic final\n")
    monkeypatch.setattr(delivery, "HISTORICAL_SHA256", delivery.sha(historical))
    monkeypatch.setattr(delivery, "FINAL_SHA256", delivery.sha(final))
    control = tmp_path / "protected.txt"
    control.write_bytes(b"unrelated protected input")
    legacy = {delivery.FINAL_REPORT: delivery.HISTORICAL_SHA256,
              delivery.LEGACY_FINAL_REPORT: delivery.FINAL_SHA256,
              "protected.txt": delivery.sha(control)}
    return tmp_path, legacy


def test_legacy_report_paths_reconcile_without_writes(renamed_reports):
    root, legacy = renamed_reports
    before = delivery.inventory(root)
    frozen = copy.deepcopy(legacy)
    resolved = delivery.reconcile_report_paths(
        root, {str(root / p): h for p, h in legacy.items()})
    assert resolved == {delivery.HISTORICAL_REPORT: delivery.HISTORICAL_SHA256,
                        delivery.FINAL_REPORT: delivery.FINAL_SHA256,
                        "protected.txt": legacy["protected.txt"]}
    delivery.verify_hashes(root, resolved)
    assert legacy == frozen and delivery.inventory(root) == before


def test_current_report_inventory_is_supported(renamed_reports):
    root, _ = renamed_reports
    current = {delivery.HISTORICAL_REPORT: delivery.HISTORICAL_SHA256,
               delivery.FINAL_REPORT: delivery.FINAL_SHA256}
    assert delivery.reconcile_report_paths(root, current) == current
    delivery.verify_hashes(root, current)


@pytest.mark.parametrize("name", [delivery.HISTORICAL_REPORT, delivery.FINAL_REPORT])
def test_relocated_report_content_must_match_exact_hash(renamed_reports, name):
    root, legacy = renamed_reports
    (root / name).write_bytes(b"changed report")
    with pytest.raises(delivery.DeliveryError, match="Checksum mismatch"):
        delivery.verify_hashes(root, delivery.reconcile_report_paths(root, legacy))


@pytest.mark.parametrize("identity", ["historical", "legacy_final", "unknown"])
def test_unknown_report_path_hash_identity_is_rejected(renamed_reports, identity):
    root, _ = renamed_reports
    name, digest = {
        "historical": (delivery.HISTORICAL_REPORT, delivery.FINAL_SHA256),
        "legacy_final": (delivery.LEGACY_FINAL_REPORT, delivery.HISTORICAL_SHA256),
        "unknown": (delivery.FINAL_REPORT, "0" * 64),
    }[identity]
    with pytest.raises(delivery.DeliveryError, match="Unknown report path/checksum"):
        delivery.reconcile_report_paths(root, {name: digest})


@pytest.mark.parametrize("report", ["historical", "final"])
def test_duplicate_legacy_and_current_report_targets_are_rejected(renamed_reports, report):
    root, _ = renamed_reports
    old, current, digest = (
        (delivery.FINAL_REPORT, delivery.HISTORICAL_REPORT, delivery.HISTORICAL_SHA256)
        if report == "historical" else
        (delivery.LEGACY_FINAL_REPORT, delivery.FINAL_REPORT, delivery.FINAL_SHA256))
    with pytest.raises(delivery.DeliveryError, match="Duplicate or conflicting report mapping"):
        delivery.reconcile_report_paths(root, {old: digest}, {current: digest})


@pytest.mark.parametrize("conflicting", [False, True])
def test_report_source_cannot_have_multiple_inventory_identities(renamed_reports, conflicting):
    root, _ = renamed_reports
    first = {delivery.FINAL_REPORT: delivery.HISTORICAL_SHA256}
    second = {delivery.FINAL_REPORT:
              delivery.FINAL_SHA256 if conflicting else delivery.HISTORICAL_SHA256}
    with pytest.raises(delivery.DeliveryError, match="Duplicate or conflicting report source"):
        delivery.reconcile_report_paths(root, first, second)


def test_absolute_relative_duplicate_report_keys_are_rejected(renamed_reports):
    root, _ = renamed_reports
    with pytest.raises(delivery.DeliveryError, match="Duplicate protected path"):
        delivery.reconcile_report_paths(root, {
            delivery.FINAL_REPORT: delivery.HISTORICAL_SHA256,
            str(root / delivery.FINAL_REPORT): delivery.HISTORICAL_SHA256})


def test_report_basename_elsewhere_is_not_a_relocation_alias(renamed_reports):
    root, _ = renamed_reports
    unknown = "unapproved/3_2_joern_pilot_final_v2.md"
    resolved = delivery.reconcile_report_paths(root, {unknown: delivery.FINAL_SHA256})
    assert resolved == {unknown: delivery.FINAL_SHA256}
    with pytest.raises(delivery.DeliveryError, match="Checksum mismatch"):
        delivery.verify_hashes(root, resolved)


def test_unrelated_protected_checksums_are_preserved(renamed_reports):
    root, legacy = renamed_reports
    resolved = delivery.reconcile_report_paths(root, legacy, {
        "protected.txt": legacy["protected.txt"]})
    (root / "protected.txt").write_bytes(b"changed unrelated input")
    with pytest.raises(delivery.DeliveryError, match="Checksum mismatch: protected.txt"):
        delivery.verify_hashes(root, resolved)
    with pytest.raises(delivery.DeliveryError, match="Conflicting protected checksum"):
        delivery.reconcile_report_paths(root, legacy, {"protected.txt": "0" * 64})


def test_reconciled_report_checksums_do_not_override_other_protected_entries(renamed_reports):
    root, legacy = renamed_reports
    with pytest.raises(delivery.DeliveryError, match="Duplicate protected path"):
        delivery.reconcile_report_paths(root, {
            "protected.txt": legacy["protected.txt"],
            str(root / "protected.txt"): "0" * 64})


def test_real_receipt_reconciliation_is_read_only_and_selects_latest(cohort, monkeypatch):
    root, plan = cohort
    checkpoint_receipts(root, plan, monkeypatch)
    before = delivery.inventory(root)
    resolved = delivery.load_plan(root)
    assert delivery.inventory(root) == before
    assert resolved.controls[delivery.HISTORICAL_REPORT] == delivery.HISTORICAL_SHA256
    assert resolved.controls[delivery.FINAL_REPORT] == delivery.FINAL_SHA256
    assert delivery.LEGACY_FINAL_REPORT not in resolved.controls
    assert [e.row["sample_id"] for e in resolved.entries] == list(delivery.IDS)
    assert [e.status for e in resolved.entries] == [e.status for e in plan.entries]
    failed = next(e for e in resolved.entries if e.row["sample_id"] == "row-1601")
    assert failed.staging == next(e for e in plan.entries if e.row["sample_id"] == "row-1601").staging
    assert len(failed.attempts) == 2
    assert any("7b3" in p for p in failed.attempts)
    assert any("7b8" in p for p in failed.attempts)


@pytest.mark.parametrize("name", [delivery.HISTORICAL_REPORT, delivery.FINAL_REPORT,
                                  "protected.txt"])
def test_receipt_replay_rejects_report_and_unrelated_tampering(cohort, monkeypatch, name):
    root, plan = cohort
    checkpoint_receipts(root, plan, monkeypatch)
    (root / name).write_bytes(b"changed protected content")
    with pytest.raises(delivery.DeliveryError, match="Checksum mismatch"):
        delivery.load_plan(root)


def test_receipt_replay_rejects_conflicting_report_alias(cohort, monkeypatch):
    root, plan = cohort
    checkpoint_receipts(root, plan, monkeypatch)
    path = root / "data/graphs/v2_pilot_7b9_final_two_evidence/baseline.json"
    receipt = delivery.read(path)
    receipt["protected_sha256"][str(root / delivery.HISTORICAL_REPORT)] = delivery.HISTORICAL_SHA256
    write(path, receipt)
    with pytest.raises(delivery.DeliveryError, match="Duplicate or conflicting report mapping"):
        delivery.load_plan(root)


def test_stale_checkpoint_mapping_rejected(cohort, monkeypatch):
    root, plan = cohort
    checkpoint_receipts(root, plan, monkeypatch)
    # Even if an external caller supplies a changed receipt, its protected
    # fingerprint must reject the incorrect mapping before any publication.
    path = root / "data/graphs/v2_pilot_7b3_evidence/cohort_ledger.json"
    ledger = delivery.read(path)
    ledger["records"][0]["latest_accepted_v2"] = str(plan.entries[1].publication)
    write(path, ledger)
    with pytest.raises(delivery.DeliveryError, match="Checksum mismatch"):
        delivery.load_plan(root)


def test_unrelated_new_file_aborts_before_publication(cohort, monkeypatch):
    root, plan = cohort
    original = delivery.build_package
    def concurrent_change(*args):
        original(*args)
        (root / "unrelated-new-file").write_text("external writer")
    monkeypatch.setattr(delivery, "build_package", concurrent_change)
    with pytest.raises(delivery.DeliveryError, match="Unexpected new file"):
        delivery.export(root, plan)
    assert not (root / "reports/graph/3_2_pilot").exists()
    assert len(list((root / "reports/graph").glob(".3_2_pilot-export-*"))) == 1


def test_post_publication_failure_is_not_silently_accepted(cohort, monkeypatch):
    root, plan = cohort
    publish = delivery.publish_no_replace
    def publish_then_detect_problem(stage, destination):
        publish(stage, destination)
        (root / "protected.txt").write_text("synthetic concurrent modification")
    monkeypatch.setattr(delivery, "publish_no_replace", publish_then_detect_problem)
    with pytest.raises(delivery.DeliveryError, match="Checksum mismatch"):
        delivery.export(root, plan)
    assert (root / "reports/graph/3_2_pilot").is_dir()
    evidence = next((root / "data/graphs/pilot_delivery_export_evidence").iterdir())
    assert delivery.read(evidence / "failure.json")["published"] is True
    assert not (evidence / "final_integrity.json").exists()


def completion_fixture(path):
    path.mkdir()
    return dict(V7_V8="PASS", published=True, protected_files_checked=1,
                mismatches=[], files={f"file-{n}": "a" * 64 for n in range(62)})


def test_completion_pending_then_final_without_replacement(tmp_path):
    evidence = tmp_path / "receipts"
    receipt = completion_fixture(evidence)
    delivery.finalize_completion(evidence, receipt)
    assert delivery.check_completion(evidence, receipt) == receipt
    assert not list(evidence.glob("*.pending"))
    before = (evidence / "final_integrity.json").read_bytes()
    with pytest.raises(delivery.DeliveryError, match="collision"):
        delivery.finalize_completion(evidence, receipt)
    assert (evidence / "final_integrity.json").read_bytes() == before
    assert len(list(evidence.glob("*.pending"))) == 1


def test_partial_completion_write_never_creates_final(tmp_path, monkeypatch):
    evidence = tmp_path / "receipts"
    receipt = completion_fixture(evidence)
    def partial(path, data):
        assert path.suffix == ".pending"
        with path.open("xb") as stream:
            stream.write(data[:len(data) // 2])
        raise OSError("synthetic disk full during pending write")
    monkeypatch.setattr(delivery, "write_new", partial)
    with pytest.raises(OSError, match="disk full"):
        delivery.finalize_completion(evidence, receipt)
    assert not (evidence / "final_integrity.json").exists()
    pending = list(evidence.glob("*.pending"))
    assert len(pending) == 1
    with pytest.raises(ValueError):
        delivery.read(pending[0])


@pytest.mark.parametrize("operation", ["flush", "fsync"])
def test_pending_synchronization_failure_has_no_final(tmp_path, monkeypatch, operation):
    evidence = tmp_path / "receipts"
    receipt = completion_fixture(evidence)
    if operation == "fsync":
        def fail_sync(fd):
            raise OSError("synthetic fsync failure")
        monkeypatch.setattr(delivery.os, "fsync", fail_sync)
    else:
        original_open = Path.open
        class FlushFailure:
            def __init__(self, stream):
                self.stream = stream
            def __enter__(self):
                return self
            def __exit__(self, *args):
                self.stream.close()
            def write(self, data):
                return self.stream.write(data)
            def flush(self):
                raise OSError("synthetic flush failure")
            def fileno(self):
                return self.stream.fileno()
        def open_stream(path, *args, **kwargs):
            stream = original_open(path, *args, **kwargs)
            return FlushFailure(stream) if path.suffix == ".pending" and args == ("xb",) else stream
        monkeypatch.setattr(Path, "open", open_stream)
    with pytest.raises(OSError, match=operation):
        delivery.finalize_completion(evidence, receipt)
    assert not (evidence / "final_integrity.json").exists()
    assert len(list(evidence.glob("*.pending"))) == 1


def test_completion_publication_failure_preserves_pending(tmp_path, monkeypatch):
    evidence = tmp_path / "receipts"
    receipt = completion_fixture(evidence)
    def unavailable(stage, final):
        assert delivery.read(stage) == receipt
        assert final.name == "final_integrity.json"
        raise OSError("synthetic receipt rename failure")
    monkeypatch.setattr(delivery, "publish_no_replace", unavailable)
    with pytest.raises(OSError, match="rename failure"):
        delivery.finalize_completion(evidence, receipt)
    assert not (evidence / "final_integrity.json").exists()
    assert delivery.read(next(evidence.glob("*.pending"))) == receipt


def test_failure_receipt_overrides_finalized_pass(tmp_path):
    evidence = tmp_path / "receipts"
    receipt = completion_fixture(evidence)
    delivery.finalize_completion(evidence, receipt)
    write(evidence / "failure.json", {"error": "synthetic later failure"})
    with pytest.raises(delivery.DeliveryError, match="takes precedence"):
        delivery.check_completion(evidence, receipt)
    with pytest.raises(delivery.DeliveryError, match="takes precedence"):
        delivery.finalize_completion(evidence, receipt)


def test_evidence_directory_creation_failure_is_visible(cohort, monkeypatch, capsys):
    root, plan = cohort
    mkdir = Path.mkdir
    def denied(path, *args, **kwargs):
        if path.parent.name == "pilot_delivery_export_evidence":
            raise PermissionError("synthetic evidence mkdir denied")
        return mkdir(path, *args, **kwargs)
    monkeypatch.setattr(Path, "mkdir", denied)
    with pytest.raises(PermissionError, match="mkdir denied"):
        delivery.export(root, plan)
    assert "failure receipt could not be persisted" in capsys.readouterr().err
    assert not (root / "reports/graph/3_2_pilot").exists()
    assert not list((root / "reports/graph").glob(".3_2_pilot-export-*"))


def test_evidence_uuid_collision_does_not_append_to_prior_evidence(cohort, monkeypatch, capsys):
    from types import SimpleNamespace
    root, plan = cohort
    existing = root / "data/graphs/pilot_delivery_export_evidence/collision"
    write(existing / "existing.json", {"prior_run": "immutable"})
    before = delivery.inventory(root)
    monkeypatch.setattr(delivery.uuid, "uuid4", lambda: SimpleNamespace(hex="collision"))
    with pytest.raises(FileExistsError):
        delivery.export(root, plan)
    assert delivery.inventory(root) == before
    assert not (existing / "failure.json").exists()
    assert "not created by this run" in capsys.readouterr().err


def test_failure_receipt_write_failure_keeps_original_error(tmp_path, monkeypatch, capsys):
    def cannot_write(*args):
        raise OSError("synthetic receipt storage unavailable")
    monkeypatch.setattr(delivery, "write_new", cannot_write)
    original = RuntimeError("original mandatory failure")
    delivery.retain_failure(tmp_path, original, published=False, staging="stage", destination="target")
    message = capsys.readouterr().err
    assert "original mandatory failure" in message and "storage unavailable" in message
    assert "Do not accept this run" in message


def test_inventory_os_walk_onerror_is_fatal(tmp_path, monkeypatch):
    def unreadable(root, *, onerror):
        onerror(PermissionError("synthetic inaccessible subtree"))
        yield str(root), [], []
    monkeypatch.setattr(delivery.os, "walk", unreadable)
    with pytest.raises(PermissionError, match="inaccessible subtree"):
        delivery.inventory(tmp_path)


def test_inventory_file_read_failure_is_fatal(tmp_path, monkeypatch):
    (tmp_path / "protected").write_text("fixture")
    def unreadable(path):
        raise PermissionError("synthetic checksum read denied")
    monkeypatch.setattr(delivery, "sha", unreadable)
    with pytest.raises(PermissionError, match="checksum read denied"):
        delivery.inventory(tmp_path)


def test_missing_inventory_root_or_protected_file_is_fatal(tmp_path):
    with pytest.raises(delivery.DeliveryError, match="Missing protected inventory root"):
        delivery.inventory(tmp_path / "missing")
    with pytest.raises(delivery.DeliveryError, match="Checksum mismatch"):
        delivery.verify_hashes(tmp_path, {"missing": "a" * 64})


def test_collision_created_after_precheck_is_not_replaced(tmp_path, monkeypatch):
    stage, target = tmp_path / "stage", tmp_path / "target"
    stage.mkdir()
    original_check = delivery.os.path.lexists
    def race(path):
        exists = original_check(path)
        if Path(path) == target and not exists:
            target.mkdir()
            (target / "existing").write_text("retain")
        return exists
    monkeypatch.setattr(delivery.os.path, "lexists", race)
    with pytest.raises(OSError):
        delivery.publish_no_replace(stage, target)
    assert stage.is_dir() and (target / "existing").read_text() == "retain"


def test_real_git_diff_check_function_reports_failure_without_git_mutation(tmp_path, monkeypatch):
    from types import SimpleNamespace
    calls = []
    def controlled_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=2, stdout=b"synthetic whitespace error", stderr=b"")
    monkeypatch.setattr(subprocess, "run", controlled_run)
    with pytest.raises(delivery.DeliveryError, match="synthetic whitespace error"):
        REAL_GIT_DIFF_CHECK(tmp_path)
    assert len(calls) == 1
    assert calls[0][0] == ["git", "-C", str(tmp_path), "diff", "--check"]
    assert calls[0][1] == dict(capture_output=True, timeout=30, check=False)


def test_completion_error_after_package_publication_retains_package(cohort, monkeypatch):
    root, plan = cohort
    publish = delivery.publish_no_replace
    def denied_receipt(stage, destination):
        if destination.name == "final_integrity.json":
            raise OSError("synthetic final receipt publication denied")
        return publish(stage, destination)
    monkeypatch.setattr(delivery, "publish_no_replace", denied_receipt)
    with pytest.raises(OSError, match="receipt publication denied"):
        delivery.export(root, plan)
    package = root / "reports/graph/3_2_pilot"
    assert package.is_dir() and len(list(package.rglob("*.json"))) == 60
    evidence = next((root / "data/graphs/pilot_delivery_export_evidence").iterdir())
    assert len(list(evidence.glob("*.pending"))) == 1
    assert delivery.read(evidence / "failure.json")["published"] is True
    assert not (evidence / "final_integrity.json").exists()


def test_error_immediately_after_receipt_rename_is_failed(cohort, monkeypatch):
    root, plan = cohort
    publish = delivery.publish_no_replace
    def rename_then_error(stage, destination):
        publish(stage, destination)
        if destination.name == "final_integrity.json":
            raise OSError("synthetic error after final rename")
    monkeypatch.setattr(delivery, "publish_no_replace", rename_then_error)
    with pytest.raises(OSError, match="after final rename"):
        delivery.export(root, plan)
    assert (root / "reports/graph/3_2_pilot").is_dir()
    evidence = next((root / "data/graphs/pilot_delivery_export_evidence").iterdir())
    assert (evidence / "final_integrity.json").exists()
    assert (evidence / "failure.json").exists()
    with pytest.raises(delivery.DeliveryError, match="takes precedence"):
        delivery.check_completion(evidence)

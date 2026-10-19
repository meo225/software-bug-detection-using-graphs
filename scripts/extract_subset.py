"""pipeline trich xuat do thi cho tap du lieu diversevul task 3.3

thuc hien trich xuat hai bieu dien do thi cho 9077 ham
graph a la do thi cay cu phap truu tuong ast
graph b la do thi ngu nghia ket hop ast luong dieu khien cfg va phu thuoc du lieu data_dep
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.graph.joern import JoernConfig, JoernExecutionError, JoernExtractor  # noqa: E402
from src.utils.config import load_config  # noqa: E402
from src.utils.logging import get_logger  # noqa: E402
from scripts.run_graph_extraction import (  # noqa: E402
    load_records_at_indices,
    parse_sample_id,
    resolve_function_name,
)

LOGGER = get_logger("extract_subset")

DEFAULT_MANIFEST = ROOT / "data" / "splits" / "diversevul_experiment_manifest.csv"
DEFAULT_DATASET = ROOT / "data" / "raw" / "diversevul" / "diversevul.jsonl"
DEFAULT_SCHEMA = ROOT / "configs" / "graph" / "schema_spec.yaml"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "graphs" / "subset_9077"

TOTAL_SAMPLES = 9077
BATCH_DEFINITIONS = {
    1: (0, 3000),
    2: (3000, 6000),
    3: (6000, 9077),
}


@dataclass
class SampleExtractionOutcome:
    sample_id: str
    index: int
    cwe: str
    project: str
    project_wise_split: str
    seen_project_split: str
    status: str
    error_message: str | None
    num_nodes: int
    num_edges_a: int
    num_edges_b: int
    ast_edges: int
    cfg_edges: int
    ddg_edges: int
    parse_seconds: float | None
    extraction_seconds: float | None
    total_seconds: float


def write_fallback_failure_json(
    dest_path: Path,
    sample_id: str,
    cwe: str,
    project_wise_split: str,
    seen_project_split: str,
    graph_type: str,
    status: str,
    error_message: str,
) -> None:
    payload = {
        "sample_id": sample_id,
        "cwe": cwe,
        "project_wise_split": project_wise_split,
        "seen_project_split": seen_project_split,
        "graph_type": graph_type,
        "status": status,
        "ddg_status": "NOT_COMPUTED",
        "num_nodes": 0,
        "num_edges": 0,
        "nodes": [],
        "edges": [],
        "error_message": error_message,
        "source_reference": f"dataset row sample_id={sample_id}",
        "record_kind": "failure_record",
    }
    dest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def process_single_sample(
    row: dict[str, str],
    record: dict[str, Any],
    graph_a_dir: Path,
    graph_b_dir: Path,
    config: JoernConfig,
) -> SampleExtractionOutcome:
    sample_id = row["sample_id"]
    index = parse_sample_id(sample_id)
    cwe = row.get("cwe", "")
    project = row.get("project", "")
    p_split = row.get("project_wise_split", "")
    s_split = row.get("seen_project_split", "")

    final_a_path = graph_a_dir / f"{sample_id}.json"
    final_b_path = graph_b_dir / f"{sample_id}.json"

    started = time.perf_counter()

    source_code = record.get("func", "")
    if not isinstance(source_code, str) or not source_code.strip():
        msg = "ma nguon rong hoac thieu truong func"
        write_fallback_failure_json(final_a_path, sample_id, cwe, p_split, s_split, "graph_a", "AST_EXTRACTION_ERROR", msg)
        write_fallback_failure_json(final_b_path, sample_id, cwe, p_split, s_split, "graph_b", "AST_EXTRACTION_ERROR", msg)
        return SampleExtractionOutcome(
            sample_id=sample_id, index=index, cwe=cwe, project=project,
            project_wise_split=p_split, seen_project_split=s_split,
            status="AST_EXTRACTION_ERROR", error_message=msg,
            num_nodes=0, num_edges_a=0, num_edges_b=0, ast_edges=0, cfg_edges=0, ddg_edges=0,
            parse_seconds=None, extraction_seconds=None, total_seconds=time.perf_counter() - started
        )

    try:
        function_name = resolve_function_name(source_code)
    except Exception as err:
        status = "UNSUPPORTED_SOURCE_REPRESENTATION" if "fragment" in str(err) else "METHOD_RESOLUTION_ERROR"
        msg = f"loi xac dinh ten ham: {err}"
        write_fallback_failure_json(final_a_path, sample_id, cwe, p_split, s_split, "graph_a", status, msg)
        write_fallback_failure_json(final_b_path, sample_id, cwe, p_split, s_split, "graph_b", status, msg)
        return SampleExtractionOutcome(
            sample_id=sample_id, index=index, cwe=cwe, project=project,
            project_wise_split=p_split, seen_project_split=s_split,
            status=status, error_message=msg,
            num_nodes=0, num_edges_a=0, num_edges_b=0, ast_edges=0, cfg_edges=0, ddg_edges=0,
            parse_seconds=None, extraction_seconds=None, total_seconds=time.perf_counter() - started
        )

    with tempfile.TemporaryDirectory(prefix=f"subset-{sample_id}-") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        source_file = temp_dir / "source.c"
        source_file.write_text(source_code, encoding="utf-8")

        extractor = JoernExtractor(config)
        try:
            res = extractor.extract(
                source_file,
                temp_dir,
                sample_id=sample_id,
                function_name=function_name,
                cwe=cwe,
                project_wise_split=p_split,
                seen_project_split=s_split,
                project_name=project,
                commit_id=row.get("commit"),
            )
            report = res.report
            data_a = json.loads(res.graph_a_path.read_text(encoding="utf-8"))
            data_b = json.loads(res.graph_b_path.read_text(encoding="utf-8"))

            shutil.copyfile(res.graph_a_path, final_a_path)
            shutil.copyfile(res.graph_b_path, final_b_path)

            status = data_b.get("status", "SUCCESS")
            num_nodes = data_b.get("num_nodes", 0)
            num_edges_a = data_a.get("num_edges", 0)
            num_edges_b = data_b.get("num_edges", 0)

            ast_count = sum(1 for e in data_b.get("edges", []) if e.get("type") == 0)
            cfg_count = sum(1 for e in data_b.get("edges", []) if e.get("type") == 1)
            ddg_count = sum(1 for e in data_b.get("edges", []) if e.get("type") == 2)

            return SampleExtractionOutcome(
                sample_id=sample_id, index=index, cwe=cwe, project=project,
                project_wise_split=p_split, seen_project_split=s_split,
                status=status, error_message=None,
                num_nodes=num_nodes, num_edges_a=num_edges_a, num_edges_b=num_edges_b,
                ast_edges=ast_count, cfg_edges=cfg_count, ddg_edges=ddg_count,
                parse_seconds=report.get("parse_seconds"),
                extraction_seconds=report.get("extraction_seconds"),
                total_seconds=time.perf_counter() - started
            )
        except JoernExecutionError as err:
            err_msg = str(err)
            stage_status = "PARSE_ERROR" if err.stage == "parse" else "AST_EXTRACTION_ERROR"
            temp_a = temp_dir / f"{sample_id}.graph_a.json"
            temp_b = temp_dir / f"{sample_id}.graph_b.json"
            if temp_a.is_file() and temp_b.is_file():
                shutil.copyfile(temp_a, final_a_path)
                shutil.copyfile(temp_b, final_b_path)
            else:
                write_fallback_failure_json(final_a_path, sample_id, cwe, p_split, s_split, "graph_a", stage_status, err_msg)
                write_fallback_failure_json(final_b_path, sample_id, cwe, p_split, s_split, "graph_b", stage_status, err_msg)

            return SampleExtractionOutcome(
                sample_id=sample_id, index=index, cwe=cwe, project=project,
                project_wise_split=p_split, seen_project_split=s_split,
                status=stage_status, error_message=err_msg,
                num_nodes=0, num_edges_a=0, num_edges_b=0, ast_edges=0, cfg_edges=0, ddg_edges=0,
                parse_seconds=None, extraction_seconds=None, total_seconds=time.perf_counter() - started
            )
        except Exception as err:
            err_msg = f"loi khong xac dinh: {err}"
            write_fallback_failure_json(final_a_path, sample_id, cwe, p_split, s_split, "graph_a", "AST_EXTRACTION_ERROR", err_msg)
            write_fallback_failure_json(final_b_path, sample_id, cwe, p_split, s_split, "graph_b", "AST_EXTRACTION_ERROR", err_msg)
            return SampleExtractionOutcome(
                sample_id=sample_id, index=index, cwe=cwe, project=project,
                project_wise_split=p_split, seen_project_split=s_split,
                status="AST_EXTRACTION_ERROR", error_message=err_msg,
                num_nodes=0, num_edges_a=0, num_edges_b=0, ast_edges=0, cfg_edges=0, ddg_edges=0,
                parse_seconds=None, extraction_seconds=None, total_seconds=time.perf_counter() - started
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="trich xuat graph a va graph b cho tap mau diversevul")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="tep manifest mau")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET, help="tep du lieu goc diversevul")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="thu muc xuat ket qua")
    parser.add_argument("--schema-config", type=Path, default=DEFAULT_SCHEMA, help="tep cau hinh schema")
    parser.add_argument("--batch", type=int, choices=[1, 2, 3], help="chi so phan doan 1 hoac 2 hoac 3")
    parser.add_argument("--start-idx", type=int, help="chi so bat dau")
    parser.add_argument("--end-idx", type=int, help="chi so ket thuc")
    parser.add_argument("--workers", type=int, default=4, help="so luong tien trinh thuc thi")
    parser.add_argument("--joern", default="joern", help="lenh thuc thi joern")
    parser.add_argument("--joern-parse", default="joern-parse", help="lenh thuc thi joern-parse")
    parser.add_argument("--java-home", help="duong dan thu muc jdk 21")
    parser.add_argument("--wsl-distro", default="Ubuntu", help="ten ban phan phoi wsl")
    parser.add_argument("--timeout", type=int, default=120, help="thoi gian gioi han tinh bang giay")
    parser.add_argument("--no-resume", action="store_true", help="khong bo qua cac mau da hoan tat")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.manifest.is_file():
        LOGGER.error("khong tim thay manifest tai: %s", args.manifest)
        return 1
    if not args.dataset.is_file():
        LOGGER.error("khong tim thay dataset tai: %s", args.dataset)
        return 1

    with open(args.manifest, "r", encoding="utf-8") as f:
        all_rows = list(csv.DictReader(f))
    total_in_manifest = len(all_rows)

    if args.batch is not None:
        start_idx, end_idx = BATCH_DEFINITIONS[args.batch]
        batch_name = f"batch_{args.batch}"
    elif args.start_idx is not None or args.end_idx is not None:
        start_idx = args.start_idx or 0
        end_idx = args.end_idx or total_in_manifest
        batch_name = f"range_{start_idx}_{end_idx}"
    else:
        start_idx = 0
        end_idx = total_in_manifest
        batch_name = "all"

    selected_rows = all_rows[start_idx:end_idx]
    LOGGER.info(
        "khoi chay phan doan %s voi %d mau tu chi so %d den %d tong so %d",
        batch_name, len(selected_rows), start_idx, end_idx, total_in_manifest
    )

    graph_a_dir = args.output_dir / "graph_a"
    graph_b_dir = args.output_dir / "graph_b"
    graph_a_dir.mkdir(parents=True, exist_ok=True)
    graph_b_dir.mkdir(parents=True, exist_ok=True)

    manifest_output_path = args.output_dir / f"manifest_{batch_name}.csv"

    schema = load_config(args.schema_config) if args.schema_config.is_file() else {}
    limits = schema.get("size_limits", {})
    config = JoernConfig(
        executable=args.joern,
        parse_executable=args.joern_parse,
        java_home=args.java_home,
        wsl_distro=args.wsl_distro,
        timeout_sec=args.timeout,
        max_nodes=int(limits.get("max_nodes", 1000)),
        max_edges=int(limits.get("max_edges", 3000)),
    )

    rows_to_process: list[dict[str, str]] = []
    already_done_outcomes: list[SampleExtractionOutcome] = []

    for row in selected_rows:
        sample_id = row["sample_id"]
        path_a = graph_a_dir / f"{sample_id}.json"
        path_b = graph_b_dir / f"{sample_id}.json"
        if not args.no_resume and path_a.is_file() and path_b.is_file():
            try:
                b_data = json.loads(path_b.read_text(encoding="utf-8"))
                a_data = json.loads(path_a.read_text(encoding="utf-8"))
                already_done_outcomes.append(
                    SampleExtractionOutcome(
                        sample_id=sample_id,
                        index=parse_sample_id(sample_id),
                        cwe=row.get("cwe", ""),
                        project=row.get("project", ""),
                        project_wise_split=row.get("project_wise_split", ""),
                        seen_project_split=row.get("seen_project_split", ""),
                        status=b_data.get("status", "SUCCESS"),
                        error_message=b_data.get("error_message"),
                        num_nodes=b_data.get("num_nodes", 0),
                        num_edges_a=a_data.get("num_edges", 0),
                        num_edges_b=b_data.get("num_edges", 0),
                        ast_edges=sum(1 for e in b_data.get("edges", []) if e.get("type") == 0),
                        cfg_edges=sum(1 for e in b_data.get("edges", []) if e.get("type") == 1),
                        ddg_edges=sum(1 for e in b_data.get("edges", []) if e.get("type") == 2),
                        parse_seconds=None,
                        extraction_seconds=None,
                        total_seconds=0.0,
                    )
                )
                continue
            except Exception:
                pass
        rows_to_process.append(row)

    LOGGER.info(
        "da hoan tat truoc do: %d mau - con lai: %d mau",
        len(already_done_outcomes), len(rows_to_process)
    )

    fieldnames = list(asdict(SampleExtractionOutcome(
        sample_id="", index=0, cwe="", project="", project_wise_split="", seen_project_split="",
        status="", error_message="", num_nodes=0, num_edges_a=0, num_edges_b=0,
        ast_edges=0, cfg_edges=0, ddg_edges=0, parse_seconds=0.0, extraction_seconds=0.0, total_seconds=0.0
    )).keys())

    manifest_file = open(manifest_output_path, "w", encoding="utf-8", newline="")
    manifest_writer = csv.DictWriter(manifest_file, fieldnames=fieldnames)
    manifest_writer.writeheader()
    for outcome in already_done_outcomes:
        manifest_writer.writerow(asdict(outcome))
    manifest_file.flush()

    if not rows_to_process:
        LOGGER.info("toan bo mau trong phan doan nay da hoan tat")
        manifest_file.close()
        return 0

    needed_indices = {parse_sample_id(r["sample_id"]) for r in rows_to_process}
    LOGGER.info("dang tai %d ban ghi tu %s", len(needed_indices), args.dataset)
    t0 = time.perf_counter()
    records_by_index = load_records_at_indices(args.dataset, needed_indices)
    LOGGER.info("thoi gian tai ban ghi: %.2f giay", time.perf_counter() - t0)

    completed_count = len(already_done_outcomes)
    success_count = sum(1 for o in already_done_outcomes if o.status in ("SUCCESS", "OVERSIZED_GRAPH"))

    LOGGER.info("bat dau tien trinh thuc thi voi %d tien trinh", args.workers)
    t_start = time.perf_counter()

    if args.workers <= 1:
        for idx, row in enumerate(rows_to_process, 1):
            sample_id = row["sample_id"]
            d_index = parse_sample_id(sample_id)
            record = records_by_index[d_index]
            outcome = process_single_sample(row, record, graph_a_dir, graph_b_dir, config)
            completed_count += 1
            if outcome.status in ("SUCCESS", "OVERSIZED_GRAPH"):
                success_count += 1
            manifest_writer.writerow(asdict(outcome))
            manifest_file.flush()
            print(
                f"tien do: {completed_count}/{len(selected_rows)} - mau: {sample_id} - "
                f"du an: {row.get('project')} - trang thai: {outcome.status} - "
                f"so nut: {outcome.num_nodes} - so canh: {outcome.num_edges_b} - "
                f"thoi gian: {outcome.total_seconds:.1f}s"
            )
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            futures = {
                executor.submit(
                    process_single_sample,
                    row,
                    records_by_index[parse_sample_id(row["sample_id"])],
                    graph_a_dir,
                    graph_b_dir,
                    config,
                ): row["sample_id"]
                for row in rows_to_process
            }

            for future in as_completed(futures):
                s_id = futures[future]
                try:
                    outcome = future.result()
                except Exception as exc:
                    LOGGER.error("loi tien trinh tai mau %s: %s", s_id, exc)
                    outcome = SampleExtractionOutcome(
                        sample_id=s_id, index=parse_sample_id(s_id), cwe="", project="",
                        project_wise_split="", seen_project_split="",
                        status="WORKER_ERROR", error_message=str(exc),
                        num_nodes=0, num_edges_a=0, num_edges_b=0, ast_edges=0, cfg_edges=0, ddg_edges=0,
                        parse_seconds=None, extraction_seconds=None, total_seconds=0.0
                    )
                completed_count += 1
                if outcome.status in ("SUCCESS", "OVERSIZED_GRAPH"):
                    success_count += 1
                manifest_writer.writerow(asdict(outcome))
                manifest_file.flush()

                elapsed = time.perf_counter() - t_start
                avg_time = elapsed / max(1, completed_count - len(already_done_outcomes))
                remaining = (len(selected_rows) - completed_count) * avg_time
                print(
                    f"tien do: {completed_count}/{len(selected_rows)} - mau: {outcome.sample_id} - "
                    f"du an: {outcome.project} - trang thai: {outcome.status} - "
                    f"so nut: {outcome.num_nodes} - so canh: {outcome.num_edges_b} - "
                    f"thoi gian: {outcome.total_seconds:.1f}s - du kien con lai: {remaining / 3600:.1f}h"
                )

    manifest_file.close()
    LOGGER.info(
        "hoan tat phan doan %s: %d tren %d mau dat yeu cau",
        batch_name, success_count, len(selected_rows)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

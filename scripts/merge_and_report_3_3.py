"""tong hop ket qua trich xuat do thi va lap bao cao ky thuat task 3.3

hop nhat tao tac do thi cho 9077 ham
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
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_graph_extraction import parse_sample_id  # noqa: E402

DEFAULT_MANIFEST = ROOT / "data" / "splits" / "diversevul_experiment_manifest.csv"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "graphs" / "subset_9077"
DEFAULT_REPORT_PATH = ROOT / "reports" / "graph" / "3_3_extraction.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="hop nhat ket qua do thi va tao bao cao ky thuat")
    parser.add_argument(
        "--batch-dirs",
        nargs="+",
        type=Path,
        required=True,
        help="danh sach thu muc phan doan chua ket qua",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="tep manifest thi nghiem goc 9077 mau",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="thu muc hop nhat ket qua",
    )
    parser.add_argument(
        "--report-out",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="duong dan tep bao cao tong ket markdown",
    )
    parser.add_argument(
        "--joern-version",
        default="4.0.654",
        help="phien ban joern",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.manifest.is_file():
        print(f"loi khong tim thay manifest tai: {args.manifest}", file=sys.stderr)
        return 1

    with open(args.manifest, "r", encoding="utf-8") as f:
        official_rows = list(csv.DictReader(f))
    total_official = len(official_rows)
    print(f"manifest thi nghiem: {total_official} mau")

    dest_graph_a = args.output_dir / "graph_a"
    dest_graph_b = args.output_dir / "graph_b"
    dest_graph_a.mkdir(parents=True, exist_ok=True)
    dest_graph_b.mkdir(parents=True, exist_ok=True)

    sample_records: dict[str, dict[str, Any]] = {}

    for batch_dir in args.batch_dirs:
        if not batch_dir.is_dir():
            print(f"canh bao khong tim thay thu muc: {batch_dir}", file=sys.stderr)
            continue

        print(f"doc du lieu thu muc: {batch_dir}")
        manifest_files = list(batch_dir.glob("manifest_*.csv"))
        for m_file in manifest_files:
            with open(m_file, "r", encoding="utf-8") as mf:
                for row in csv.DictReader(mf):
                    sample_records[row["sample_id"]] = row

        for kind, dest_dir in (("graph_a", dest_graph_a), ("graph_b", dest_graph_b)):
            src_kind_dir = batch_dir / kind
            if src_kind_dir.is_dir():
                for json_file in src_kind_dir.glob("*.json"):
                    shutil.copyfile(json_file, dest_dir / json_file.name)

    print(f"tong so mau da thu thap: {len(sample_records)} tren {total_official}")

    processed_samples = []
    missing_samples = []
    success_statuses = {"SUCCESS", "OVERSIZED_GRAPH"}

    for off in official_rows:
        s_id = off["sample_id"]
        json_a = dest_graph_a / f"{s_id}.json"
        json_b = dest_graph_b / f"{s_id}.json"

        if json_a.is_file() and json_b.is_file():
            data_b = json.loads(json_b.read_text(encoding="utf-8"))
            data_a = json.loads(json_a.read_text(encoding="utf-8"))
            status = data_b.get("status", "UNKNOWN")
            err_msg = data_b.get("error_message")
            num_nodes = data_b.get("num_nodes", 0)
            edges_a = data_a.get("num_edges", 0)
            edges_b = data_b.get("num_edges", 0)
            ast_e = sum(1 for e in data_b.get("edges", []) if e.get("type") == 0)
            cfg_e = sum(1 for e in data_b.get("edges", []) if e.get("type") == 1)
            ddg_e = sum(1 for e in data_b.get("edges", []) if e.get("type") == 2)

            processed_samples.append({
                "sample_id": s_id,
                "project": off.get("project", ""),
                "cwe": off.get("cwe", ""),
                "project_wise_split": off.get("project_wise_split", ""),
                "seen_project_split": off.get("seen_project_split", ""),
                "status": status,
                "error_message": err_msg,
                "num_nodes": num_nodes,
                "num_edges_a": edges_a,
                "num_edges_b": edges_b,
                "ast_edges": ast_e,
                "cfg_edges": cfg_e,
                "ddg_edges": ddg_e,
            })
        else:
            missing_samples.append(s_id)

    total_processed = len(processed_samples)
    total_success = sum(1 for s in processed_samples if s["status"] in success_statuses)
    total_rejected = total_processed - total_success
    total_oversized = sum(1 for s in processed_samples if s["status"] == "OVERSIZED_GRAPH")

    print(f"tong muc tieu: {total_official}")
    print(f"tong da xu ly: {total_processed}")
    print(f"tong hop le: {total_success}")
    print(f"tong bi loai: {total_rejected}")
    print(f"vuot nguong kich thuoc: {total_oversized}")
    print(f"so mau chua hoan tat: {len(missing_samples)}")

    for kind, dest_dir in (("graph_a", dest_graph_a), ("graph_b", dest_graph_b)):
        manifest_path = dest_dir / "manifest.csv"
        with open(manifest_path, "w", encoding="utf-8", newline="") as mf:
            writer = csv.DictWriter(mf, fieldnames=[
                "sample_id", "project", "cwe", "project_wise_split", "seen_project_split",
                "status", "num_nodes", "num_edges", "error_message"
            ])
            writer.writeheader()
            for s in processed_samples:
                edges_count = s["num_edges_a"] if kind == "graph_a" else s["num_edges_b"]
                writer.writerow({
                    "sample_id": s["sample_id"],
                    "project": s["project"],
                    "cwe": s["cwe"],
                    "project_wise_split": s["project_wise_split"],
                    "seen_project_split": s["seen_project_split"],
                    "status": s["status"],
                    "num_nodes": s["num_nodes"],
                    "num_edges": edges_count,
                    "error_message": s["error_message"] or "",
                })
        print(f"ghi manifest thanh cong: {manifest_path}")

    cwe_stats = defaultdict(lambda: {"total": 0, "success": 0, "failed": 0})
    for s in processed_samples:
        c = s["cwe"]
        cwe_stats[c]["total"] += 1
        if s["status"] in success_statuses:
            cwe_stats[c]["success"] += 1
        else:
            cwe_stats[c]["failed"] += 1

    successful_items = [s for s in processed_samples if s["status"] in success_statuses]
    nodes_list = [s["num_nodes"] for s in successful_items] or [0]
    edges_a_list = [s["num_edges_a"] for s in successful_items] or [0]
    edges_b_list = [s["num_edges_b"] for s in successful_items] or [0]
    ast_list = [s["ast_edges"] for s in successful_items] or [0]
    cfg_list = [s["cfg_edges"] for s in successful_items] or [0]
    ddg_list = [s["ddg_edges"] for s in successful_items] or [0]

    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.report_out, "w", encoding="utf-8") as rf:
        rf.write("# bao cao ket qua trich xuat do thi cho tap mau diversevul task 3.3\n\n")
        rf.write(f"phien ban joern: {args.joern_version}\n")
        rf.write("schema: configs/graph/schema_spec.yaml\n\n")
        rf.write("## 1. nguyen tac bao toan mau\n\n")
        rf.write("thuc hien trich xuat hai bieu dien do thi cho 9077 ham\n")
        rf.write("- graph a: do thi cay cu phap truu tuong ast\n")
        rf.write("- graph b: do thi ngu nghia ket hop ast, luong dieu khien cfg va phu thuoc du lieu data_dep\n\n")
        rf.write(f"so luong ham thanh cong cong so luong ham bi loai: {total_success} + {total_rejected} = {total_processed} tren {total_official}\n\n")
        rf.write(f"- tong so do thi hop le: {total_success} tren {total_official}\n")
        rf.write(f"- so luong do thi vuot nguong kich thuoc: {total_oversized}\n")
        rf.write(f"- tong so mau bi loai: {total_rejected} tren {total_official}\n")
        if missing_samples:
            rf.write(f"- so luong mau chua xu ly: {len(missing_samples)}\n\n")
        else:
            rf.write("- ty le bao phu: 100 phan tram\n\n")

        rf.write("## 2. thong ke theo 23 lop cwe\n\n")
        rf.write("| cwe | tong so mau | so luong thanh cong | ty le thanh cong | so luong bi loai |\n")
        rf.write("| :--- | ---: | ---: | ---: | ---: |\n")
        for cwe_id in sorted(cwe_stats.keys()):
            st = cwe_stats[cwe_id]
            pct = (st["success"] / st["total"]) * 100 if st["total"] else 0.0
            rf.write(f"| {cwe_id} | {st['total']} | {st['success']} | {pct:.2f}% | {st['failed']} |\n")

        rf.write("\n## 3. thong ke kich thuoc do thi\n\n")
        rf.write("| dai luong | nho nhat | trung vi | trung binh | lon nhat | tong so |\n")
        rf.write("| :--- | ---: | ---: | ---: | ---: | ---: |\n")
        rf.write(f"| nut dung chung | {min(nodes_list)} | {sorted(nodes_list)[len(nodes_list)//2]} | {sum(nodes_list)/max(1, len(nodes_list)):.1f} | {max(nodes_list)} | {sum(nodes_list)} |\n")
        rf.write(f"| canh graph a ast | {min(edges_a_list)} | {sorted(edges_a_list)[len(edges_a_list)//2]} | {sum(edges_a_list)/max(1, len(edges_a_list)):.1f} | {max(edges_a_list)} | {sum(edges_a_list)} |\n")
        rf.write(f"| canh cfg graph b | {min(cfg_list)} | {sorted(cfg_list)[len(cfg_list)//2]} | {sum(cfg_list)/max(1, len(cfg_list)):.1f} | {max(cfg_list)} | {sum(cfg_list)} |\n")
        rf.write(f"| canh data_dep graph b | {min(ddg_list)} | {sorted(ddg_list)[len(ddg_list)//2]} | {sum(ddg_list)/max(1, len(ddg_list)):.1f} | {max(ddg_list)} | {sum(ddg_list)} |\n")
        rf.write(f"| tong canh graph b | {min(edges_b_list)} | {sorted(edges_b_list)[len(edges_b_list)//2]} | {sum(edges_b_list)/max(1, len(edges_b_list)):.1f} | {max(edges_b_list)} | {sum(edges_b_list)} |\n\n")

        rf.write("## 4. phan loai cac truong hop bi loai\n\n")
        rejection_reasons = Counter(s["status"] for s in processed_samples if s["status"] not in success_statuses)
        for reason, count in rejection_reasons.items():
            rf.write(f"- {reason}: {count} mau\n")

        rf.write("\n## 5. ket luan nghiem thu\n\n")
        if total_processed == total_official and total_success >= (total_official * 0.8):
            rf.write("toan bo 9077 mau da duoc doi chieu va bao toan day du. du dieu kien nghiem thu chuyen giao sang phase 4.\n")
        else:
            rf.write("can hoan tat them cac mau chua xu ly truoc khi chuyen sang phase 4.\n")

    print(f"xuat bao cao thanh cong: {args.report_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

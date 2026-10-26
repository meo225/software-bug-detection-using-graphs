"""Tổng hợp kết quả trích xuất đồ thị và lập báo cáo kỹ thuật Task 3.3

Hợp nhất tạo tác đồ thị cho 9.077 hàm:
- Graph A: đồ thị cây cú pháp trừu tượng AST
- Graph B: đồ thị ngữ nghĩa kết hợp AST, luồng điều khiển CFG và phụ thuộc dữ liệu DATA_DEP
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
    parser = argparse.ArgumentParser(description="Hợp nhất kết quả đồ thị và tạo báo cáo kỹ thuật")
    parser.add_argument(
        "--batch-dirs",
        nargs="+",
        type=Path,
        required=True,
        help="Danh sách thư mục phân đoạn chứa kết quả",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Tệp manifest thí nghiệm gốc 9.077 mẫu",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Thư mục hợp nhất kết quả",
    )
    parser.add_argument(
        "--report-out",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Đường dẫn tệp báo cáo tổng kết Markdown",
    )
    parser.add_argument(
        "--joern-version",
        default="4.0.654",
        help="Phiên bản Joern",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.manifest.is_file():
        print(f"Lỗi không tìm thấy manifest tại: {args.manifest}", file=sys.stderr)
        return 1

    with open(args.manifest, "r", encoding="utf-8") as f:
        official_rows = list(csv.DictReader(f))
    total_official = len(official_rows)
    print(f"Manifest thí nghiệm: {total_official} mẫu")

    dest_graph_a = args.output_dir / "graph_a"
    dest_graph_b = args.output_dir / "graph_b"
    dest_graph_a.mkdir(parents=True, exist_ok=True)
    dest_graph_b.mkdir(parents=True, exist_ok=True)

    sample_records: dict[str, dict[str, Any]] = {}

    for batch_dir in args.batch_dirs:
        if not batch_dir.is_dir():
            print(f"Cảnh báo không tìm thấy thư mục: {batch_dir}", file=sys.stderr)
            continue

        print(f"Đọc dữ liệu thư mục: {batch_dir}")
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

    print(f"Tổng số mẫu đã thu thập: {len(sample_records)} trên {total_official}")

    processed_samples = []
    missing_samples = []
    success_statuses = {"SUCCESS", "OVERSIZED_GRAPH"}

    for off in official_rows:
        s_id = off["sample_id"]
        json_a = dest_graph_a / f"{s_id}.json"
        json_b = dest_graph_b / f"{s_id}.json"

        if json_a.is_file() and json_b.is_file():
            try:
                data_b = json.loads(json_b.read_text(encoding="utf-8"))
                data_a = json.loads(json_a.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                # Tệp ghi dở do phiên bị hủy: tính là chưa hoàn tất để chạy bù.
                missing_samples.append(s_id)
                continue
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

    print(f"Tổng mục tiêu: {total_official}")
    print(f"Tổng đã xử lý: {total_processed}")
    print(f"Tổng hợp lệ: {total_success}")
    print(f"Tổng bị loại: {total_rejected}")
    print(f"Vượt ngưỡng kích thước: {total_oversized}")
    print(f"Số mẫu chưa hoàn tất: {len(missing_samples)}")

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
        print(f"Ghi manifest thành công: {manifest_path}")

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
        rf.write("# Báo cáo kết quả trích xuất đồ thị cho tập mẫu DiverseVul Task 3.3\n\n")
        rf.write(f"Phiên bản Joern: {args.joern_version}\n")
        rf.write("Schema: configs/graph/schema_spec.yaml\n\n")
        rf.write("## 1. Nguyên tắc bảo toàn mẫu\n\n")
        rf.write("Thực hiện trích xuất hai biểu diễn đồ thị cho 9.077 hàm:\n")
        rf.write("- Graph A: đồ thị cây cú pháp trừu tượng AST\n")
        rf.write("- Graph B: đồ thị ngữ nghĩa kết hợp AST, luồng điều khiển CFG và phụ thuộc dữ liệu DATA_DEP\n\n")
        rf.write(f"Số lượng hàm thành công cộng số lượng hàm bị loại: {total_success} + {total_rejected} = {total_processed} trên {total_official}\n\n")
        rf.write(f"- Tổng số đồ thị hợp lệ: {total_success} trên {total_official}\n")
        rf.write(f"- Số lượng đồ thị vượt ngưỡng kích thước: {total_oversized}\n")
        rf.write(f"- Tổng số mẫu bị loại: {total_rejected} trên {total_official}\n")
        if missing_samples:
            rf.write(f"- Số lượng mẫu chưa xử lý: {len(missing_samples)}\n\n")
        else:
            rf.write("- Tỷ lệ bao phủ: 100%\n\n")

        rf.write("## 2. Thống kê theo 23 lớp CWE\n\n")
        rf.write("| CWE | Tổng số mẫu | Số lượng thành công | Tỷ lệ thành công | Số lượng bị loại |\n")
        rf.write("| :--- | ---: | ---: | ---: | ---: |\n")
        for cwe_id in sorted(cwe_stats.keys()):
            st = cwe_stats[cwe_id]
            pct = (st["success"] / st["total"]) * 100 if st["total"] else 0.0
            rf.write(f"| {cwe_id} | {st['total']} | {st['success']} | {pct:.2f}% | {st['failed']} |\n")

        rf.write("\n## 3. Thống kê kích thước đồ thị\n\n")
        rf.write("| Đại lượng | Nhỏ nhất | Trung vị | Trung bình | Lớn nhất | Tổng số |\n")
        rf.write("| :--- | ---: | ---: | ---: | ---: | ---: |\n")
        rf.write(f"| Node dùng chung | {min(nodes_list)} | {sorted(nodes_list)[len(nodes_list)//2]} | {sum(nodes_list)/max(1, len(nodes_list)):.1f} | {max(nodes_list)} | {sum(nodes_list)} |\n")
        rf.write(f"| Cạnh Graph A AST | {min(edges_a_list)} | {sorted(edges_a_list)[len(edges_a_list)//2]} | {sum(edges_a_list)/max(1, len(edges_a_list)):.1f} | {max(edges_a_list)} | {sum(edges_a_list)} |\n")
        rf.write(f"| Cạnh CFG Graph B | {min(cfg_list)} | {sorted(cfg_list)[len(cfg_list)//2]} | {sum(cfg_list)/max(1, len(cfg_list)):.1f} | {max(cfg_list)} | {sum(cfg_list)} |\n")
        rf.write(f"| Cạnh DATA_DEP Graph B | {min(ddg_list)} | {sorted(ddg_list)[len(ddg_list)//2]} | {sum(ddg_list)/max(1, len(ddg_list)):.1f} | {max(ddg_list)} | {sum(ddg_list)} |\n")
        rf.write(f"| Tổng cạnh Graph B | {min(edges_b_list)} | {sorted(edges_b_list)[len(edges_b_list)//2]} | {sum(edges_b_list)/max(1, len(edges_b_list)):.1f} | {max(edges_b_list)} | {sum(edges_b_list)} |\n\n")

        rf.write("## 4. Phân loại các trường hợp bị loại\n\n")
        rejection_reasons = Counter(s["status"] for s in processed_samples if s["status"] not in success_statuses)
        for reason, count in rejection_reasons.items():
            rf.write(f"- {reason}: {count} mẫu\n")

        rf.write("\n## 5. Kết luận nghiệm thu\n\n")
        if total_processed == total_official and total_success >= (total_official * 0.8):
            rf.write("Toàn bộ 9.077 mẫu đã được đối chiếu và bảo toàn đầy đủ. Đủ điều kiện nghiệm thu chuyển giao sang Phase 4.\n")
        else:
            rf.write("Cần hoàn tất thêm các mẫu chưa xử lý trước khi chuyển sang Phase 4.\n")

    print(f"Xuất báo cáo thành công: {args.report_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

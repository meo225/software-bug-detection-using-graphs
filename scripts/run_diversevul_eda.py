"""Run the DiverseVul audit and generate all committed EDA artifacts."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")

os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "data" / "interim" / "matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src.data.diversevul_audit import metadata_audit, read_optional_metadata, run_audit, write_json
from src.data.loader import load_dataset
from src.utils.config import load_config
from src.utils.paths import resolve_from_root

TABLE_DIR = ROOT / "reports" / "dataset" / "tables"
FIGURE_DIR = ROOT / "reports" / "dataset" / "figures"
REPORT_PATH = ROOT / "reports" / "dataset" / "dataset_eda.md"
MANIFEST_PATH = ROOT / "data" / "sample_manifests" / "diversevul_graph_sample.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "data" / "diversevul.yaml")
    parser.add_argument("--dataset-file", type=Path, help="Explicit main dataset file when discovery is ambiguous.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero instead of writing a blocked status when data is absent.")
    return parser.parse_args()


def _placeholder_figure(path: Path, message: str) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.axis("off")
    ax.text(0.5, 0.55, "EDA not run", ha="center", va="center", fontsize=20, weight="bold")
    ax.text(0.5, 0.40, message, ha="center", va="center", fontsize=11, wrap=True)
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def write_blocked_outputs(reason: str, raw_dir: Path) -> None:
    """Create explicitly marked placeholders without inventing measurements."""
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    schemas = {
        "dataset_summary.csv": ["metric", "value", "status", "note"],
        "missing_values.csv": ["field", "meaning", "dtype", "missing_count", "missing_percentage", "example"],
        "cwe_distribution.csv": ["cwe", "sample_count", "percentage_of_labeled_vulnerable", "project_count", "commit_count"],
        "threshold_analysis.csv": ["threshold", "number_of_cwe", "number_of_samples", "percentage_samples_retained", "minimum_class_size", "maximum_class_size"],
        "multi_cwe_summary.csv": ["category", "sample_count", "percentage_of_vulnerable"],
        "project_distribution.csv": ["project", "total_samples", "vulnerable_samples", "number_of_cwe"],
        "cwe_project_distribution.csv": ["cwe", "sample_count", "project_count", "largest_project_sample_count", "largest_project_share"],
        "duplicate_summary.csv": ["level", "records_with_code", "unique_code", "duplicate_groups", "duplicate_affected_records", "duplicate_excess_records", "duplicate_affected_percentage", "vulnerable_label_conflict_groups", "cwe_conflict_groups"],
    }
    for name, columns in schemas.items():
        frame = pd.DataFrame(columns=columns)
        if name == "dataset_summary.csv":
            frame = pd.DataFrame([{"metric": "audit_status", "value": "blocked", "status": "not_computed", "note": reason}])
        frame.to_csv(TABLE_DIR / name, index=False)
    pd.DataFrame(columns=["sample_id", "project", "commit", "cwe", "label", "source_reference"]).to_csv(MANIFEST_PATH, index=False)
    for name in ("cwe_top20.png", "cwe_distribution.png", "project_distribution.png", "function_length_distribution.png"):
        _placeholder_figure(FIGURE_DIR / name, "Raw DiverseVul data is missing. No values are plotted.")
    write_json(TABLE_DIR / "audit_status.json", {"status": "blocked", "reason": reason, "expected_raw_dir": str(raw_dir)})
    REPORT_PATH.write_text(_blocked_report(reason, raw_dir), encoding="utf-8")


def _blocked_report(reason: str, raw_dir: Path) -> str:
    return f"""# Audit dataset DiverseVul

**Trạng thái: BLOCKED - chưa có dữ liệu thô.**

Chưa có thống kê DiverseVul nào được tính. Các file CSV và PNG trong thư mục báo cáo được đánh dấu rõ là file giữ chỗ để tránh hiểu nhầm dữ liệu đầu vào bị thiếu thành kết quả có giá trị bằng 0.

## File dataset thực tế đã sử dụng

Không có. Thư mục dữ liệu thô đã kiểm tra là `{raw_dir.as_posix()}` và không chứa file dataset thuộc định dạng được hỗ trợ.

Nguyên nhân: `{reason}`

## Cách cung cấp dữ liệu

1. Tải dataset chính từ đường dẫn trong repository DiverseVul chính thức.
2. Có thể tải thêm metadata commit/repository và bảng label-noise riêng.
3. Đặt các file trong `data/raw/diversevul/`; không commit chúng.
4. Chạy `python scripts/run_diversevul_eda.py --strict` từ thư mục gốc repository.
5. Chạy toàn bộ `notebooks/01_diversevul_eda.ipynb` từ đầu đến cuối để kiểm tra khả năng tái lập ở lớp trình bày.

Runner hỗ trợ CSV, JSON, JSONL/NDJSON, Parquet và file pickle từ nguồn chính thức. Dùng `--dataset-file PATH` nếu có nhiều file có thể là dataset chính. Chỉ dùng pickle từ bản phát hành chính thức đáng tin cậy vì quá trình load pickle có thể thực thi code.

## Schema

Chưa quan sát được. Pipeline sẽ in và xuất các cột, dtype, shape, missingness, ví dụ và ánh xạ đã xác định cho source/label/CWE/project/commit/hash/CVE/repository. Pipeline báo lỗi thay vì tự tạo field bắt buộc không có trong dữ liệu.

## Các kiểm tra đã chuẩn bị nhưng chưa chạy trên DiverseVul

- so sánh số record, vulnerable, non-vulnerable, project, commit và CWE giữa paper và bản dữ liệu thực tế
- coverage CWE chỉ trên vulnerable sample, Top 10/20, phân bố long-tail và coverage tích lũy
- các threshold 20/50/100/200 mà không tự chọn threshold cuối cùng
- tỷ lệ sample có 0, 1 hoặc nhiều CWE và các ví dụ giới hạn
- mức tập trung theo project/CWE và tính khả thi của split tại 2/3/5/10 project
- duplicate chính xác, duplicate sau normalization bảo thủ và label conflict
- source bị thiếu cùng các phân vị độ dài theo ký tự/dòng
- manifest 30 function xác định bằng seed cố định để thử graph
- độ bao phủ khi join metadata và các URL bị thiếu

## Bối cảnh từ paper, không phải kết quả EDA

Baseline so sánh được mã hóa trong audit gồm 349.437 function, 18.945 vulnerable function, 330.492 non-vulnerable function, 797 project, 7.514 commit và 150 CWE. Các số này không bao giờ được dùng thay cho phép đo trên dataset bị thiếu.

Phân tích thủ công trong paper báo cáo độ chính xác của vulnerable-function label chỉ khoảng 60%. Đây là hạn chế của label suy ra từ fixing commit, không phải thống kê được tính lại trên full dataset đang vắng mặt. Repository chính thức cũng cho biết metadata bao phủ 7.512 commit và thiếu ba commit URL so với dataset đã trích xuất.

## Trả lời các câu hỏi nghiên cứu

Q1-Q13 vẫn ở trạng thái **chưa đo được** đối với bản dữ liệu local. Bằng chứng hiện tại chưa đủ để kết luận có bao nhiêu CWE usable, project-wise split có khả thi hay bản DiverseVul này đã sẵn sàng cho bước tạo graph hay chưa.

## Các quyết định nghiên cứu còn mở

Audit không tự chọn Top-K/threshold, chính sách single-label hay multi-label, final split, graph representation, cấu hình Joern hoặc kiến trúc GNN.
"""


def _barh(frame: pd.DataFrame, label: str, value: str, path: Path, title: str, top: int = 20) -> None:
    plot = frame.head(top).sort_values(value)
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(plot[label], plot[value], color="#2f6b9a")
    ax.set(title=title, xlabel="Samples", ylabel="")
    ax.grid(axis="x", alpha=0.2)
    fig.tight_layout()
    fig.savefig(path, dpi=160, facecolor="white")
    plt.close(fig)


def write_figures(result) -> None:
    cwe = result.tables["cwe_distribution"]
    _barh(cwe, "cwe", "sample_count", FIGURE_DIR / "cwe_top20.png", "Top 20 CWE among vulnerable labeled functions")
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    counts = cwe["sample_count"].sort_values(ascending=False).reset_index(drop=True)
    axes[0].plot(range(1, len(counts) + 1), counts, color="#2f6b9a")
    axes[0].set_yscale("log")
    axes[0].set(title="CWE class-size long tail", xlabel="CWE rank", ylabel="Samples (log scale)")
    axes[1].plot(range(1, len(counts) + 1), counts.cumsum().div(counts.sum()).mul(100), color="#c77721")
    axes[1].set(title="Cumulative CWE-label coverage", xlabel="CWE rank", ylabel="Cumulative percentage")
    fig.tight_layout(); fig.savefig(FIGURE_DIR / "cwe_distribution.png", dpi=160, facecolor="white"); plt.close(fig)
    _barh(result.tables["project_distribution"], "project", "vulnerable_samples", FIGURE_DIR / "project_distribution.png", "Top projects by vulnerable functions")
    source = result.records["source_code"].fillna("").astype(str)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    axes[0].hist(source.str.len().clip(upper=source.str.len().quantile(.99)), bins=50, color="#2f6b9a")
    axes[0].set(title="Characters/function (clipped at p99)", xlabel="Characters", ylabel="Functions")
    lines = source.map(lambda text: 0 if not text else text.count("\n") + 1)
    axes[1].hist(lines.clip(upper=lines.quantile(.99)), bins=50, color="#c77721")
    axes[1].set(title="Lines/function (clipped at p99)", xlabel="Lines", ylabel="Functions")
    fig.tight_layout(); fig.savefig(FIGURE_DIR / "function_length_distribution.png", dpi=160, facecolor="white"); plt.close(fig)


def _fmt(value: object) -> str:
    return f"{value:,.2f}" if isinstance(value, float) else f"{value:,}" if isinstance(value, int) else str(value)


def _markdown_table(frame: pd.DataFrame, limit: int | None = None) -> str:
    shown = frame.head(limit) if limit else frame
    headers = [str(column) for column in shown.columns]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in shown.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(_fmt(value).replace("|", "\\|") for value in row) + " |")
    return "\n".join(lines)


def write_report(result, dataset_file: Path, metadata_file: Path | None) -> None:
    tables = result.tables
    f = result.findings
    cwe = tables["cwe_distribution"]
    dup = tables["duplicate_summary"]
    top_candidate = tables["cwe_project_distribution"].query("sample_count >= 20").head(20)
    text = f"""# Audit dataset DiverseVul

**Trạng thái: HOÀN TẤT đối với các file local liệt kê dưới đây.** Báo cáo mô tả bản dữ liệu đã load; không tự chọn dataset cuối cùng, tập class, chính sách label, split, graph representation hoặc model.

## File dataset thực tế đã sử dụng

- Dataset chính: `{dataset_file.as_posix()}`
- Metadata riêng: `{metadata_file.as_posix() if metadata_file else 'không được cung cấp'}`

Kích thước: **{len(result.records):,} dòng x {f['raw_column_count']:,} cột thô**. Schema thô thực tế và missing values nằm trong `tables/missing_values.csv`.

Các field đã ánh xạ: `{result.fields}`

## So sánh với paper

{_markdown_table(tables['paper_comparison'])}

Mọi chênh lệch được giữ nguyên như quan sát. Nguyên nhân có thể liên quan đến release/version, parsing, độ bao phủ metadata hoặc record bị trùng và cần được điều tra; số liệu không bao giờ bị sửa để khớp paper.

## Coverage và mất cân bằng CWE

- Vulnerable function có ít nhất một CWE parse được: **{f['vulnerable_with_cwe']:,}**
- Vulnerable function không có CWE parse được: **{f['vulnerable_without_cwe']:,}**
- Số CWE unique parse được trên vulnerable function: **{f['unique_cwe_vulnerable']:,}**

Top 20:

{_markdown_table(cwe, 20)}

Bằng chứng theo threshold (một multi-CWE function chỉ được tính giữ lại một lần nếu có bất kỳ label nào đạt ngưỡng):

{_markdown_table(tables['threshold_analysis'])}

## Multi-CWE

{_markdown_table(tables['multi_cwe_summary'])}

Không record multi-CWE nào bị rút gọn thành label đầu tiên. Các ví dụ nằm trong `tables/multi_cwe_examples.csv`.

## Phân bố project và tính khả thi của project-wise split

{_markdown_table(tables['project_split_feasibility'])}

Bảng bằng chứng cho các candidate, không phải tập class đã chọn:

{_markdown_table(top_candidate, 20)}

`largest_project_share` cao cho thấy rủi ro tập trung theo project hoặc leakage ngay cả khi class có nhiều sample.

## Duplicate và label conflict

{_markdown_table(dup)}

Normalization chỉ chuyển đổi line ending, bỏ space/tab ở cuối từng dòng và xóa dòng trống ở biên. Quy trình không gộp whitespace bên trong hoặc xóa comment.

## Chất lượng source code và mức sẵn sàng cho graph

{_markdown_table(tables['source_quality_summary'])}

{_markdown_table(tables['function_length_summary'])}

Sample giới hạn để kiểm tra thủ công nằm trong `tables/source_inspection_sample.csv`. Manifest `data/sample_manifests/diversevul_graph_sample.csv` chứa reference được chọn bằng seed cố định cho tối đa 30 vulnerable function, trải trên các nhóm độ dài và số CWE. Manifest không nhúng toàn bộ source code. Audit này không chạy Joern.

## Audit metadata

{_markdown_table(tables['metadata_audit'])}

## Bối cảnh label noise

Paper báo cáo vulnerable-function label chỉ chính xác khoảng 60% trong sample được kiểm tra thủ công. Các dạng lỗi chính gồm vulnerability trải qua nhiều function, thay đổi helper/caller cần thiết cho bản vá và thay đổi không liên quan trong security-fixing commit. Đây là bối cảnh từ paper, không phải kết quả được tính lại trên full dataset. Nếu bảng label-noise chính thức được cung cấp, bảng đó phải được tóm tắt riêng và không được trộn vào mẫu số của full dataset.

## Trả lời trực tiếp các câu hỏi nghiên cứu

1. **Có khớp paper không:** xem chênh lệch chính xác ở trên; không mismatch nào bị sửa để khớp paper.
2. **Vulnerable function có CWE:** {f['vulnerable_with_cwe']:,}.
3. **Có bao nhiêu CWE usable:** không có một con số duy nhất nếu chưa có policy; các bảng threshold và project support cung cấp số candidate.
4. **Mức mất cân bằng:** phân bố theo rank và biểu đồ tích lũy thể hiện long tail quan sát được.
5. **Threshold:** cả bốn threshold được báo cáo và không threshold nào được tự chọn.
6. **Multi-CWE:** {f['multi_cwe_samples']:,} vulnerable sample có ít nhất hai CWE parse được.
7. **Duplicate:** tỷ lệ exact và normalized duplicate được báo cáo ở trên.
8. **Label conflict:** số nhóm conflict vulnerable/non-vulnerable và CWE được báo cáo ở trên.
9. **Độ trải theo project:** xem project count trên từng CWE và largest-project share.
10. **Project-wise split:** chỉ khả thi đối với các class đạt mức project support mong muốn; audit không tạo final split.
11. **Mức sẵn sàng cho Joern:** độ đầy đủ/độ dài source và sample manifest hỗ trợ một thử nghiệm giới hạn; tỷ lệ parse thành công vẫn cần được đo ở phase tiếp theo.
12. **Candidate CWE:** dùng bảng bằng chứng không ràng buộc ở trên, sau đó team quyết định policy.
13. **Mức phù hợp tổng thể:** DiverseVul chỉ phù hợp có điều kiện cho nghiên cứu function-to-CWE khi có policy multi-CWE tường minh, xử lý duplicate/conflict, caveat về label noise và đánh giá project-aware.

## Các quyết định nghiên cứu còn mở

- kích thước class tối thiểu và tập CWE candidate
- chính sách single-label, multi-label, hierarchical hoặc xử lý ambiguous sample
- các ràng buộc cho project-aware split cuối cùng
- cách xử lý duplicate và conflict
- graph representation và thiết lập trích xuất Joern
- kiến trúc GNN cuối cùng và evaluation protocol
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def main() -> int:
    args = parse_args()
    config = load_config(args.config)["dataset"]
    raw_dir = resolve_from_root(*Path(config["local_raw_dir"]).parts)
    TABLE_DIR.mkdir(parents=True, exist_ok=True); FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        loaded = load_dataset(config["name"], raw_dir, args.dataset_file)
    except FileNotFoundError as error:
        if args.strict:
            print(f"BLOCKED: {error}", file=sys.stderr)
            return 2
        write_blocked_outputs(str(error), raw_dir)
        print(f"BLOCKED: {error}")
        return 0
    result = run_audit(loaded.frame, config)
    metadata, metadata_path = read_optional_metadata(raw_dir)
    result.tables["metadata_audit"] = metadata_audit(result.records, metadata)
    for name, table in result.tables.items():
        if name == "graph_sample_manifest":
            table.to_csv(MANIFEST_PATH, index=False)
        else:
            table.to_csv(TABLE_DIR / f"{name}.csv", index=False)
    write_figures(result)
    write_json(TABLE_DIR / "audit_status.json", {"status": "complete", "dataset_file": str(loaded.source_file), "fields": result.fields})
    write_report(result, loaded.source_file, metadata_path)
    print(f"EDA complete: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

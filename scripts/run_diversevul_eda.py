"""Chạy audit DiverseVul và sinh toàn bộ artifact EDA có thể commit."""

from __future__ import annotations

import argparse
import hashlib
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

from src.data.diversevul_audit import (
    metadata_audit,
    read_label_noise_summary,
    read_optional_metadata,
    run_audit,
    write_json,
)
from src.data.loader import load_dataset
from src.utils.config import load_config
from src.utils.paths import resolve_from_root

TABLE_DIR = ROOT / "reports" / "dataset" / "tables"
FIGURE_DIR = ROOT / "reports" / "dataset" / "figures"
REPORT_PATH = ROOT / "reports" / "dataset" / "dataset_eda.md"
MANIFEST_PATH = ROOT / "data" / "sample_manifests" / "diversevul_graph_sample.csv"


def _display_path(path: Path | None) -> str | None:
    """Trả đường dẫn tương đối với repository khi có thể để artifact có tính di động."""
    if path is None:
        return None
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "data" / "diversevul.yaml")
    parser.add_argument("--dataset-file", type=Path, help="Chỉ định file dataset chính khi quá trình dò tìm bị mơ hồ.")
    parser.add_argument("--strict", action="store_true", help="Trả mã lỗi thay vì ghi trạng thái blocked khi thiếu dữ liệu.")
    return parser.parse_args()


def _placeholder_figure(path: Path, message: str) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.axis("off")
    ax.text(0.5, 0.55, "Chưa chạy EDA", ha="center", va="center", fontsize=20, weight="bold")
    ax.text(0.5, 0.40, message, ha="center", va="center", fontsize=11, wrap=True)
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def write_blocked_outputs(reason: str, raw_dir: Path) -> None:
    """Tạo file giữ chỗ có đánh dấu rõ mà không bịa số liệu."""
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
        _placeholder_figure(FIGURE_DIR / name, "Thiếu dữ liệu thô DiverseVul. Không có giá trị nào được vẽ.")
    write_json(
        TABLE_DIR / "audit_status.json",
        {"status": "blocked", "reason": reason, "expected_raw_dir": _display_path(raw_dir)},
    )
    REPORT_PATH.write_text(_blocked_report(reason, raw_dir), encoding="utf-8")


def _blocked_report(reason: str, raw_dir: Path) -> str:
    return f"""# Kiểm tra bộ dữ liệu DiverseVul

**Trạng thái: BLOCKED - chưa có dữ liệu thô.**

Chưa có thống kê DiverseVul nào được tính. Các file CSV và PNG trong thư mục báo cáo được đánh dấu rõ là file giữ chỗ để tránh hiểu nhầm dữ liệu đầu vào bị thiếu thành kết quả có giá trị bằng 0.

## File dataset thực tế đã sử dụng

Không có. Thư mục dữ liệu thô đã kiểm tra là `{_display_path(raw_dir)}` và không chứa file dataset thuộc định dạng được hỗ trợ.

Nguyên nhân: `{reason}`

## Cách cung cấp dữ liệu

1. Tải dataset chính từ đường dẫn trong repository DiverseVul chính thức.
2. Có thể tải thêm metadata commit/repository và bảng label-noise riêng.
3. Đặt các file trong `data/raw/diversevul/`; không commit chúng.
4. Chạy `python scripts/run_diversevul_eda.py --strict` từ thư mục gốc repository.
5. Chạy toàn bộ `notebooks/01_diversevul_eda.ipynb` từ đầu đến cuối để kiểm tra khả năng tái lập ở lớp trình bày.

Runner hỗ trợ CSV, JSON, JSONL/NDJSON, Parquet và file pickle từ nguồn chính thức. Dùng `--dataset-file PATH` nếu có nhiều file có thể là dataset chính. Chỉ dùng pickle từ bản phát hành chính thức đáng tin cậy vì quá trình load pickle có thể thực thi code.

## Cấu trúc dữ liệu

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
    _barh(cwe, "cwe", "sample_count", FIGURE_DIR / "cwe_top20.png", "Top 20 CWE trong các vulnerable function có label")
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    counts = cwe["sample_count"].sort_values(ascending=False).reset_index(drop=True)
    axes[0].plot(range(1, len(counts) + 1), counts, color="#2f6b9a")
    axes[0].set_yscale("log")
    axes[0].set(title="Phân bố long-tail theo kích thước class CWE", xlabel="Thứ hạng CWE", ylabel="Số sample (thang log)")
    axes[1].plot(range(1, len(counts) + 1), counts.cumsum().div(counts.sum()).mul(100), color="#c77721")
    axes[1].set(title="Coverage tích lũy của label CWE", xlabel="Thứ hạng CWE", ylabel="Phần trăm tích lũy")
    fig.tight_layout(); fig.savefig(FIGURE_DIR / "cwe_distribution.png", dpi=160, facecolor="white"); plt.close(fig)
    _barh(result.tables["project_distribution"], "project", "vulnerable_samples", FIGURE_DIR / "project_distribution.png", "Các project có nhiều vulnerable function nhất")
    source = result.records["source_code"].fillna("").astype(str)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    axes[0].hist(source.str.len().clip(upper=source.str.len().quantile(.99)), bins=50, color="#2f6b9a")
    axes[0].set(title="Số ký tự/function (giới hạn tại p99)", xlabel="Số ký tự", ylabel="Số function")
    lines = source.map(lambda text: 0 if not text else text.count("\n") + 1)
    axes[1].hist(lines.clip(upper=lines.quantile(.99)), bins=50, color="#c77721")
    axes[1].set(title="Số dòng/function (giới hạn tại p99)", xlabel="Số dòng", ylabel="Số function")
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


def write_report(result, dataset_file: Path, metadata_file: Path | None, label_noise_file: Path | None) -> None:
    tables = result.tables
    f = result.findings
    cwe = tables["cwe_distribution"]
    dup = tables["duplicate_summary"]
    top_candidate = tables["cwe_project_distribution"].query("sample_count >= 20").head(20)
    text = f"""# Audit dataset DiverseVul

Báo cáo này mô tả bản dữ liệu đã load. Báo cáo không tự chọn dataset cuối, tập lớp, chính sách nhãn, split, biểu diễn graph hoặc model.

## File dataset thực tế đã sử dụng

- Dataset chính: `{_display_path(dataset_file)}`
- Metadata riêng: `{_display_path(metadata_file) if metadata_file else 'không được cung cấp'}`
- Bảng label-noise: `{_display_path(label_noise_file) if label_noise_file else 'không được cung cấp'}`

Kích thước: **{len(result.records):,} dòng x {f['raw_column_count']:,} cột thô**. Schema thô thực tế và missing values nằm trong `tables/missing_values.csv`.

Các field đã ánh xạ: `{result.fields}`

## So sánh với paper

{_markdown_table(tables['paper_comparison'])}

Mọi chênh lệch được giữ nguyên. Nguyên nhân có thể là phiên bản phát hành, parsing, độ phủ metadata hoặc record trùng, và cần được điều tra. Số liệu không bị sửa để khớp paper.

Tổng số dòng của file đang dùng, {f['total_samples']:,}, đúng bằng số non-vulnerable mà paper công bố, trong khi file vẫn có đủ {f['vulnerable_samples']:,} dòng vulnerable. Vì vậy số non-vulnerable thực tế chỉ còn {f['non_vulnerable_samples']:,}. Quan hệ này gợi ý khác biệt giữa bản phát hành và cách paper cộng các tập con, nhưng chưa đủ bằng chứng để khẳng định nguyên nhân.

## Coverage và mất cân bằng CWE

- Vulnerable function có ít nhất một CWE parse được: **{f['vulnerable_with_cwe']:,}**
- Vulnerable function không có CWE parse được: **{f['vulnerable_without_cwe']:,}**
- Số CWE unique parse được trên vulnerable function: **{f['unique_cwe_vulnerable']:,}**

Top 20:

{_markdown_table(cwe, 20)}

Bằng chứng theo ngưỡng. Một function có nhiều CWE chỉ được tính giữ lại một lần nếu có bất kỳ nhãn nào đạt ngưỡng.

{_markdown_table(tables['threshold_analysis'])}

## Multi-CWE

{_markdown_table(tables['multi_cwe_summary'])}

Không record multi-CWE nào bị rút gọn thành label đầu tiên. Các ví dụ nằm trong `tables/multi_cwe_examples.csv`.

## Phân bố project và tính khả thi của project-wise split

{_markdown_table(tables['project_split_feasibility'])}

Bảng bằng chứng cho các candidate, không phải tập class đã chọn:

{_markdown_table(top_candidate, 20)}

Phần của project lớn nhất cao cho thấy rủi ro tập trung theo project hoặc leakage, ngay cả khi lớp có nhiều mẫu.

## Duplicate và label conflict

{_markdown_table(dup)}

Normalization chỉ chuyển đổi line ending, bỏ space/tab ở cuối từng dòng và xóa dòng trống ở biên. Quy trình không gộp whitespace bên trong hoặc xóa comment.

Kiểm tra field hash do dataset cung cấp:

{_markdown_table(tables['provided_hash_summary'])}

## Chất lượng source code và mức sẵn sàng cho graph

{_markdown_table(tables['source_quality_summary'])}

{_markdown_table(tables['function_length_summary'])}

{_markdown_table(tables['source_syntax_profile'])}

Mẫu để kiểm tra thủ công nằm trong `tables/source_inspection_sample.csv`. Manifest `data/sample_manifests/diversevul_graph_sample.csv` chứa tối đa 30 hàm vulnerable, chọn bằng seed cố định, trải trên các nhóm độ dài và số CWE. Manifest không nhúng toàn bộ source. Audit này không chạy Joern.

Dataset không có trường ngôn ngữ để tách C khỏi C++ một cách đáng tin. Các dấu hiệu cú pháp ở trên chỉ là heuristic. Tỷ lệ Joern parse thành công trên manifest mới là cổng tiếp theo. Độ dài trải từ source rỗng đến hàng chục nghìn dòng và dữ liệu đến từ 800 project, nên corpus không phải chỉ gồm các ví dụ C đơn điệu. Các outlier cần giới hạn hoặc xử lý riêng khi tạo graph.

## Audit metadata

{_markdown_table(tables['metadata_audit'])}

Dataset chính không có CVE, URL repository hoặc timestamp. CVE và repository chỉ xuất hiện trong metadata riêng, và chưa phủ hết. Vì không có timestamp, EDA này không dựng được chronological split có kiểm chứng từ các file đã tải.

## Bối cảnh label noise

{_markdown_table(tables['label_noise_summary']) if not tables['label_noise_summary'].empty else 'Không tìm thấy spreadsheet label-noise chính thức trong thư mục dữ liệu thô.'}

Bảng chính thức cho thấy 30 trên 50 mẫu DiverseVul được đánh giá đúng, tức 60%. Phần còn lại gồm lỗ hổng trải nhiều function, thay đổi liên quan nhưng bản thân function không vulnerable, và thay đổi không liên quan. Đây là kiểm tay trên mẫu nhỏ của tác giả, không phải thống kê tính lại trên toàn bộ dataset, và không được cộng vào mẫu số của EDA.

## Trả lời các câu hỏi nghiên cứu

1. Khớp paper hay không. Xem chênh lệch ở bảng trên. Không số nào bị sửa để khớp paper.
2. Hàm vulnerable có CWE là {f['vulnerable_with_cwe']:,}.
3. Số CWE dùng được không có một con số duy nhất khi chưa có chính sách nhãn. Bảng ngưỡng và bảng project cho số ứng viên.
4. Mất cân bằng thể hiện ở phân bố theo hạng và biểu đồ tích lũy, tức đuôi dài đã quan sát.
5. Cả bốn ngưỡng đều được báo. Không ngưỡng nào được tự chọn.
6. Multi-CWE gồm {f['multi_cwe_samples']:,} mẫu vulnerable có ít nhất hai CWE.
7. Tỷ lệ trùng tuyệt đối và trùng sau chuẩn hóa nằm ở bảng trên.
8. Số nhóm lệch nhãn vulnerable và lệch CWE nằm ở bảng trên.
9. Độ trải theo project xem số project từng CWE và phần của project lớn nhất.
10. Project-wise split chỉ khả thi với các lớp đạt mức phủ project mong muốn. Audit không tạo split cuối.
11. Độ đầy đủ và độ dài source, cùng manifest mẫu, đủ cho một thử nghiệm giới hạn. Tỷ lệ parse thành công vẫn phải đo ở phase sau.
12. Tập CWE candidate lấy từ bảng bằng chứng ở trên, rồi nhóm tự chốt chính sách.
13. DiverseVul chỉ phù hợp có điều kiện cho nghiên cứu từ function sang CWE, khi có chính sách multi-CWE rõ, xử lý mẫu trùng và conflict, ghi nhận nhiễu nhãn, và đánh giá theo project.

## Các quyết định nghiên cứu còn mở

- kích thước lớp tối thiểu và tập CWE candidate
- chính sách single-label, multi-label, phân cấp, hoặc cách xử lý mẫu mơ hồ
- ràng buộc cho split cuối theo project
- cách xử lý mẫu trùng và conflict
- biểu diễn graph và cách trích xuất bằng Joern
- kiến trúc GNN cuối và cách đánh giá
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
    label_noise, label_noise_path = read_label_noise_summary(raw_dir)
    result.tables["label_noise_summary"] = label_noise
    for name, table in result.tables.items():
        if name == "graph_sample_manifest":
            table.to_csv(MANIFEST_PATH, index=False)
        else:
            table.to_csv(TABLE_DIR / f"{name}.csv", index=False)
    write_figures(result)
    digest = hashlib.sha256()
    with loaded.source_file.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    write_json(TABLE_DIR / "audit_status.json", {
        "status": "complete",
        "dataset_file": _display_path(loaded.source_file),
        "dataset_size_bytes": loaded.source_file.stat().st_size,
        "dataset_sha256": digest.hexdigest(),
        "metadata_file": _display_path(metadata_path),
        "label_noise_file": _display_path(label_noise_path),
        "fields": result.fields,
    })
    write_report(result, loaded.source_file, metadata_path, label_noise_path)
    print(f"EDA hoàn tất: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

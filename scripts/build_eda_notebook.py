"""Tạo notebook EDA DiverseVul có thể tái lập từ đặc tả cell ngắn gọn."""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "notebooks" / "01_diversevul_eda.ipynb"


def md(title: str, text: str) -> object:
    return nbf.v4.new_markdown_cell(f"## {title}\n\n{text}")


def code(source: str) -> object:
    return nbf.v4.new_code_cell(source.strip())


def build() -> None:
    notebook = nbf.v4.new_notebook()
    notebook["metadata"]["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
    notebook["metadata"]["language_info"] = {"name": "python", "version": "3.10+"}
    notebook["cells"] = [
        nbf.v4.new_markdown_cell(
            "# Kiểm tra bộ dữ liệu DiverseVul\n\n"
            "Kiểm tra các bản ghi C/C++ ở mức hàm để đánh giá mức phù hợp cho bài toán phân loại CWE. "
            "Notebook không tự chọn số CWE phổ biến nhất, chính sách nhãn, cách chia dữ liệu cuối cùng, "
            "biểu diễn đồ thị hoặc kiến trúc GNN."
        ),
        md("1. Thiết lập", "Xác định mọi đường dẫn từ thư mục gốc repository và cố định seed dùng để lấy mẫu."),
        code("""
from pathlib import Path
import sys
import pandas as pd
from IPython.display import display, Image

ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.loader import load_dataset
from src.data.diversevul_audit import run_audit, read_optional_metadata, metadata_audit, read_label_noise_summary, schema_table
from src.utils.config import load_config

SEED = 105
config = load_config(ROOT / "configs/data/diversevul.yaml")["dataset"]
raw_dir = ROOT / config["local_raw_dir"]
print("Repository:", ROOT)
print("Thư mục dữ liệu thô:", raw_dir)
"""),
        md("2. Nạp dữ liệu", "Nạp đầy đủ bản dữ liệu local thực tế. Nếu thiếu dữ liệu, trạng thái bị chặn phải được hiển thị tường minh."),
        code("""
dataset_available = False
blocked_reason = None
try:
    loaded = load_dataset(config["name"], raw_dir)
    raw = loaded.frame
    dataset_available = True
    print("File:", loaded.source_file)
    print("Shape:", raw.shape)
except FileNotFoundError as error:
    blocked_reason = str(error)
    print("BLOCKED:", blocked_reason)
"""),
        md("3. Cấu trúc dữ liệu", "In các cột, kiểu dữ liệu, kích thước, ánh xạ field, dữ liệu thiếu và ví dụ giới hạn từ dữ liệu thật. Không tự tạo field."),
        code("""
if dataset_available:
    result = run_audit(raw, config)
    print(raw.dtypes)
    print("Các field đã ánh xạ:", result.fields)
    display(result.tables["missing_values"])
else:
    print("Chưa quan sát được schema vì không có file dataset nào được load.")
"""),
        md("4. Xác minh thống kê trong paper", "Tính lại sáu metric chính và giữ nguyên mọi chênh lệch so với baseline trong paper."),
        code("display(result.tables['paper_comparison']) if dataset_available else print('Chưa tính được.')"),
        md("5. Dữ liệu bị thiếu", "Kiểm tra missingness của từng cột thô, bao gồm các semantic field không tồn tại."),
        code("display(result.tables['missing_values']) if dataset_available else print('Chưa tính được.')"),
        md("6. Mức bao phủ CWE của dữ liệu có lỗ hổng", "Phân tích cho bài toán phân loại CWE chỉ sử dụng các bản ghi có lỗ hổng."),
        code("display(result.tables['dataset_summary']) if dataset_available else print('Chưa tính được.')"),
        md("7. Phân bố CWE", "Tính mức bao phủ theo hàm, dự án, commit và dữ liệu có lỗ hổng đã gắn nhãn cho từng CWE. Bản ghi có nhiều CWE đóng góp vào từng CWE được gắn."),
        code("display(result.tables['cwe_distribution'].head(20)) if dataset_available else print('Chưa tính được.')"),
        md("8. Phân tích ngưỡng", "Đánh giá các ngưỡng 20/50/100/200 mẫu trên mỗi CWE mà không tự chọn ngưỡng."),
        code("display(result.tables['threshold_analysis']) if dataset_available else print('Chưa tính được.')"),
        md("9. Phân tích mẫu có nhiều CWE", "Đo số mẫu có 0, 1 hoặc từ 2 CWE trở lên mà không tự chuyển bài toán thành phân loại một nhãn."),
        code("""
if dataset_available:
    display(result.tables["multi_cwe_summary"])
    display(result.tables["cwe_count_distribution"])
    display(result.tables["multi_cwe_examples"])
else:
    print("Chưa tính được.")
"""),
        md("10. Phân bố dự án", "So sánh tổng số hàm, số hàm có lỗ hổng và độ rộng CWE trên từng dự án."),
        code("display(result.tables['project_distribution'].head(20)) if dataset_available else print('Chưa tính được.')"),
        md("11. Phân tích CWE theo dự án", "Đo số dự án hỗ trợ và mức tập trung vào dự án lớn nhất cho từng CWE."),
        code("""
if dataset_available:
    display(result.tables["cwe_project_distribution"].head(30))
    display(result.tables["project_split_feasibility"])
else:
    print("Chưa tính được.")
"""),
        md("12. Phân tích dữ liệu trùng lặp", "So sánh mã băm của mã nguồn nguyên bản với mã băm sau khi chuẩn hóa bảo thủ ký tự xuống dòng và khoảng trắng cuối dòng, đồng thời đếm xung đột nhãn."),
        code("display(result.tables['duplicate_summary']) if dataset_available else print('Chưa tính được.')"),
        md("13. Chất lượng mã nguồn", "Báo cáo mã nguồn bị thiếu/rỗng và các phân vị độ dài theo ký tự/dòng. Chủ động không tính token khi chưa chọn bộ tách token."),
        code("""
if dataset_available:
    display(result.tables["source_quality_summary"])
    display(result.tables["function_length_summary"])
    display(result.tables["source_syntax_profile"])
    display(result.tables["source_inspection_sample"])
else:
    print("Chưa tính được.")
"""),
        md("14. Mẫu kiểm tra mức sẵn sàng để tạo đồ thị", "Chỉ tạo danh mục nhỏ với seed cố định để thử Joern ở giai đoạn sau; không tạo CPG trong notebook này."),
        code("""
if dataset_available:
    display(result.tables["graph_sample_manifest"])
else:
    print("Không thể tạo manifest khi chưa có dataset thô.")
"""),
        md("15. Kết quả", "Sinh tất cả bảng, biểu đồ, danh mục mẫu, kết quả kiểm tra metadata, bảng label-noise và báo cáo Markdown từ cùng một kết quả đã tính."),
        code("""
import subprocess
completed = subprocess.run(
    [sys.executable, str(ROOT / "scripts/run_diversevul_eda.py")],
    cwd=ROOT,
    check=True,
    text=True,
    capture_output=True,
)
print(completed.stdout.strip())
if dataset_available:
    metadata, _ = read_optional_metadata(raw_dir)
    result.tables["metadata_audit"] = metadata_audit(result.records, metadata)
    label_noise, _ = read_label_noise_summary(raw_dir)
    result.tables["label_noise_summary"] = label_noise
    display(result.tables["metadata_audit"])
    display(result.tables["label_noise_summary"])
    print(result.findings)
else:
    print("Không có kết quả EDA nào được tuyên bố; các artifact được sinh đều ghi rõ trạng thái BLOCKED.")
"""),
        md("16. Các quyết định nghiên cứu còn mở", "Bằng chứng hỗ trợ nhưng không tự chốt các quyết định dưới đây."),
        code("""
decisions = [
    "Top-K hoặc số sample tối thiểu trên mỗi CWE",
    "cách xử lý single-label, multi-label, hierarchical hoặc ambiguous sample",
    "project-aware split cuối cùng",
    "chính sách xử lý duplicate và label conflict",
    "graph representation và cấu hình Joern",
    "kiến trúc GNN và evaluation protocol",
]
for decision in decisions:
    print("-", decision)
"""),
    ]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(notebook, OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    build()

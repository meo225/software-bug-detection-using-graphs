# Cấu trúc dữ liệu

Các file lớn trong cây thư mục này được Git bỏ qua. Chỉ commit `.gitkeep`, file README này và các danh sách ID split nhỏ.

| Thư mục | Nội dung | Chính sách Git |
| --- | --- | --- |
| `raw/` | Dataset gốc, không sửa | bỏ qua |
| `interim/` | Bản đã làm sạch hoặc biến đổi, chưa phải bản cuối | bỏ qua |
| `processed/` | Bản sau preprocessing và lọc CWE, khi nhóm đã quyết định | bỏ qua |
| `splits/` | Danh sách sample ID cho train, validation, test | commit |
| `graphs/` | Đồ thị trích từ source code | bỏ qua file nhị phân |

Một split chỉ là ba danh sách ID. Không nhân bản source code thành ba dataset.

Chiến lược cần hỗ trợ: random, project-wise, chronological. Cùng một project không được vừa nằm trong train vừa nằm trong test khi dùng project-wise split.

Đặt DiverseVul vào `raw/diversevul/`. Big-Vul và PrimeVul có thư mục riêng khi được thêm: `raw/bigvul/`, `raw/primevul/`.

Chi tiết thiết lập và định dạng file được hỗ trợ nằm ở `raw/README.md`. Chạy `python scripts/run_diversevul_eda.py --strict` sau khi đặt file. Pipeline sẽ báo lỗi nếu thiếu field bắt buộc, thay vì tự tạo schema.

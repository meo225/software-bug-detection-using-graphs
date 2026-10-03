# Data layout

Large files in this tree are gitignored. Commit only `.gitkeep`, this README, and small split ID lists.

| Directory | Contents | Git |
| --- | --- | --- |
| `raw/` | Dataset gốc, không sửa | ignore |
| `interim/` | Bản đã làm sạch hoặc biến đổi, chưa phải bản cuối | ignore |
| `processed/` | Bản sau preprocessing và lọc CWE, khi nhóm đã quyết định | ignore |
| `splits/` | Danh sách sample ID cho train, validation, test | commit |
| `graphs/` | Đồ thị trích từ source code | ignore binary |

Một split chỉ là ba danh sách ID. Không nhân bản source code thành ba dataset.

Chiến lược cần hỗ trợ: random, project-wise, chronological. Cùng một project không được vừa nằm trong train vừa nằm trong test khi dùng project-wise split.

Đặt DiverseVul vào `raw/diversevul/`. Big-Vul và PrimeVul có thư mục riêng khi được thêm: `raw/bigvul/`, `raw/primevul/`.

# Task 2.2: Candidate CWE và chính sách multi-CWE

**Quyết định:** thí nghiệm chính dùng **subset single-label, 23 CWE, 9.077 function**.

Mỗi function trong tập này có đúng một CWE, và CWE đó nằm trong danh sách bên dưới. Model dự đoán một nhãn. Metric chính vẫn là Macro-F1 như task 1.4.

## Căn cứ đã đọc

Sheet kế hoạch chỉ gắn hai link. Cả hai đã được dùng:

- [Ghi chép Phase 0](https://docs.google.com/document/d/1bxmiV-OPSb2Jot5LfVE0qR8GnxBAqQ3YajirxSRt6IA/edit?usp=sharing): bài toán được mô tả là multiclass, một function cho ra một CWE.
- [Repo](https://github.com/meo225/software-bug-detection-using-graphs): kết quả task 1.1–2.1 nằm ở đây, không nằm ở link riêng.

Ba tài liệu trong repo được lấy làm ràng buộc:

- `reports/research/task_1_3_1_4.md`: cấm lấy CWE đầu tiên; cấm nhân một function multi-CWE thành nhiều dòng trước khi split; chỉ được chọn single-label subset, multi-label, hoặc hierarchy có tài liệu.
- `reports/dataset/dataset_eda.md` và `reports/dataset/tables/cwe_project_distribution.csv`: số mẫu, số project và mức tập trung. Script đã đối chiếu lại và khớp bảng này, gồm 459 nhóm lệch nhãn vulnerable và 299 nhóm lệch CWE.
- `reports/dataset_comparison/megavul_vs_diversevul.md`: dataset chính vẫn là DiverseVul.

Multi-label và hierarchy không được chọn. Multi-label đổi loss và cách tính Macro-F1 của core experiment. Hierarchy chưa có bảng ánh xạ được task 1.4 thông qua. CWE-119, CWE-787 và CWE-125 vì vậy giữ là ba lớp riêng, dù CWE-119 là lớp bộ nhớ rất rộng. CWE-189, CWE-264, CWE-399 và CWE-703 cũng là lớp rộng và được giữ nguyên ID.

## Tiêu chí lọc

Một CWE được giữ khi đạt cả bốn điều kiện:

| Tiêu chí | Ngưỡng | Vì sao |
| --- | ---: | --- |
| Số function mang CWE này | ≥ 100 | Ngưỡng giữa trong EDA. Test khoảng 10% vẫn còn đủ mẫu để tính per-CWE F1. |
| Số project | ≥ 10 | Mức chặt nhất mà EDA đã đo. Split ba phía cần class xuất hiện ở nhiều project. |
| Phần trăm mẫu thuộc project lớn nhất | ≤ 50% | Một project không được chiếm đa số class. Nếu chiếm đa số, unseen-project test không còn đại diện cho class. |
| Số function đúng một CWE, sau khi loại conflict | ≥ 80 | Class phải còn đủ mẫu sau chính sách single-label. |

`sample_count` và `largest_project_share` tính như EDA: một function nhiều CWE được đếm ở từng CWE. Cột `single-label` là số function còn lại khi function đó chỉ có một CWE và source đã chuẩn hóa không nằm trong nhóm conflict.

## 23 CWE được giữ

| CWE | Tên MITRE | Mẫu EDA | Project | Project lớn nhất | Single-label |
| --- | --- | ---: | ---: | ---: | ---: |
| CWE-787 | Out-of-bounds Write | 2.896 | 277 | 13,85% | 1.368 |
| CWE-125 | Out-of-bounds Read | 1.869 | 176 | 16,59% | 1.101 |
| CWE-119 | Bounds of a Memory Buffer | 1.633 | 192 | 17,09% | 697 |
| CWE-20 | Improper Input Validation | 1.315 | 148 | 18,94% | 873 |
| CWE-703 | Exceptional Condition Check | 1.228 | 152 | 33,22% | 362 |
| CWE-416 | Use After Free | 1.005 | 79 | 43,18% | 751 |
| CWE-476 | NULL Pointer Dereference | 975 | 125 | 23,49% | 736 |
| CWE-190 | Integer Overflow | 783 | 96 | 16,22% | 441 |
| CWE-200 | Exposure of Sensitive Information | 747 | 102 | 28,65% | 500 |
| CWE-399 | Resource Management Errors | 509 | 59 | 28,88% | 329 |
| CWE-189 | Numeric Errors | 422 | 43 | 22,27% | 255 |
| CWE-264 | Permissions and Access Controls | 420 | 41 | 46,90% | 209 |
| CWE-400 | Uncontrolled Resource Consumption | 402 | 49 | 29,10% | 179 |
| CWE-401 | Missing Release of Memory | 366 | 30 | 30,87% | 184 |
| CWE-120 | Classic Buffer Overflow | 299 | 56 | 18,06% | 145 |
| CWE-415 | Double Free | 269 | 53 | 15,24% | 191 |
| CWE-369 | Divide By Zero | 261 | 31 | 37,93% | 136 |
| CWE-22 | Path Traversal | 201 | 40 | 20,40% | 129 |
| CWE-835 | Infinite Loop | 191 | 39 | 22,51% | 109 |
| CWE-617 | Reachable Assertion | 178 | 29 | 17,42% | 102 |
| CWE-59 | Link Following | 170 | 29 | 12,35% | 93 |
| CWE-295 | Improper Certificate Validation | 151 | 28 | 21,19% | 98 |
| CWE-770 | Allocation Without Limits | 112 | 28 | 21,43% | 89 |

Tên MITRE chỉ để đọc. Dataset không có cột tên.

CWE-416 (43,18%) và CWE-264 (46,90%) được giữ vì chưa quá một nửa và vẫn có nhiều project. Phase 0 cũng lấy CWE-416 làm ví dụ C/C++.

## CWE có ít nhất 100 mẫu nhưng bị loại

| CWE | Mẫu | Project | Project lớn nhất | Single-label | Lý do |
| --- | ---: | ---: | ---: | ---: | --- |
| CWE-362 | 458 | 32 | 60,70% | 306 | một project chiếm đa số |
| CWE-284 | 432 | 66 | 55,32% | 97 | một project chiếm đa số |
| CWE-310 | 361 | 25 | 50,97% | 339 | một project chiếm đa số |
| CWE-269 | 196 | 28 | 37,76% | 67 | còn dưới 80 function single-label |
| CWE-94 | 140 | 26 | 29,29% | 67 | còn dưới 80 function single-label |
| CWE-772 | 139 | 14 | 40,29% | 75 | còn dưới 80 function single-label |
| CWE-19 | 112 | 9 | 44,64% | 44 | dưới 10 project |
| CWE-287 | 108 | 24 | 24,07% | 53 | còn dưới 80 function single-label |

Mọi CWE dưới 100 mẫu đều ra khỏi thí nghiệm chính.

## Cách xử lý mẫu không vào tập 23 lớp

| Nhóm | Số function | Cách xử lý |
| --- | ---: | --- |
| Vulnerable không parse được CWE | 2.836 | Loại. Không điền nhãn. |
| Vulnerable có từ hai CWE | 4.215 | Loại cả function. Không lấy CWE đầu. Không tách thành nhiều dòng. |
| Vulnerable đúng một CWE ngoài 23 lớp | phần còn lại của 11.894 | Loại. |
| Đúng một CWE trong 23 lớp, nhưng source chuẩn hóa nằm trong nhóm conflict | 316 trên 9.393 | Loại khỏi mọi split. |
| Non-vulnerable | 311.547 | Không thuộc bài toán phân loại CWE. |

Chuẩn hóa source chỉ đổi line ending, xóa whitespace cuối dòng và dòng trống ở biên. Đây là quy ước của EDA. Conflict là các nhóm source đó không thống nhất nhãn vulnerable hoặc không thống nhất tập CWE. Có 737 hash rơi vào ít nhất một trong hai loại: 459 nhóm lệch vulnerable và 299 nhóm lệch CWE.

Tập đưa vào task 2.3 là **9.077 function, 23 CWE**.

# DiverseVul dataset audit

Trạng thái: **chưa chạy**. File này là mẫu báo cáo. Mọi ô "Pending" phải được thay bằng số liệu tính từ bản dataset đã tải. Không điền số từ paper. Không sửa dữ liệu cho khớp paper.

Nếu số đếm khác paper, ghi ở mục phiên bản: số của file đang dùng, tên file, ngày tải, checksum, và mô tả chỗ khác.

DiverseVul vẫn là candidate. Báo cáo này không được kết luận đây là dataset cuối cùng khi các mục dưới còn Pending.

## Dataset version

| Mục | Giá trị |
| --- | --- |
| Config | `configs/data/diversevul.yaml` |
| Đường dẫn local | `data/raw/diversevul/` |
| Tên file đã tải | Pending |
| Ngày tải | Pending |
| Checksum | Pending |
| Khác biệt so với paper hoặc metadata | Pending |

## A. Dataset overview

| Câu hỏi | Kết quả |
| --- | --- |
| Số records | Pending |
| Số vulnerable | Pending |
| Số non-vulnerable | Pending |
| Tỷ lệ vulnerable | Pending |
| Danh sách cột | Pending |
| Missing value từng cột | Pending |
| Source code missing | Pending |
| Project metadata missing | Pending |
| Commit metadata missing | Pending |
| CWE metadata missing | Pending |

## B. CWE analysis

Chỉ tính các CWE thật sự có trong file đã tải.

| Câu hỏi | Kết quả |
| --- | --- |
| Số CWE unique | Pending |
| Vulnerable functions có CWE | Pending |
| Vulnerable functions không có CWE | Pending |
| Top 10 CWE | Pending |
| Top 20 CWE | Pending |
| Dạng long-tail | Pending |

Bảng đầy đủ xuất ra `tables/cwe_distribution.csv` với cột `CWE`, `sample_count`, `percentage`, `project_count`.

### Ngưỡng tần suất

Không chọn ngưỡng trong báo cáo này. Chỉ ghi phần dữ liệu còn lại.

| Ngưỡng | Số CWE còn lại | Số vulnerable functions còn lại | Phần trăm dữ liệu giữ lại |
| --- | --- | --- | --- |
| >= 20 samples | Pending | Pending | Pending |
| >= 50 samples | Pending | Pending | Pending |
| >= 100 samples | Pending | Pending | Pending |
| >= 200 samples | Pending | Pending | Pending |

## C. Multi-CWE analysis

Không lấy CWE đầu tiên làm ground-truth.

| Câu hỏi | Kết quả |
| --- | --- |
| Function có đúng 1 CWE | Pending |
| Function có >= 2 CWE | Pending |
| Tỷ lệ multi-CWE | Pending |
| Phân bố số CWE trên một sample | Pending |
| Ví dụ multi-CWE | Pending |

## D. Project analysis

| Câu hỏi | Kết quả |
| --- | --- |
| Số project | Pending |
| Samples / project | Pending |
| Vulnerable samples / project | Pending |
| Số CWE / project | Pending |
| Số project / CWE | Pending |
| Random split có khả thi không | Pending |
| Project-wise split có khả thi không | Pending |
| Metadata thời gian có đủ cho chronological split không | Pending |

`tables/project_distribution.csv`: `project`, `sample_count`, `vulnerable_count`, `cwe_count`.

`tables/cwe_project_distribution.csv`: `CWE`, `sample_count`, `project_count`.

Một CWE nhiều sample nhưng chỉ xuất hiện ở một project là rủi ro cho project-wise split. Ghi các trường hợp đó khi bảng đã có số.

## E. Duplicate analysis

Không xóa bản ghi trong pha EDA.

| Kiểm tra | Kết quả |
| --- | --- |
| Trùng source code chính xác | Pending |
| Trùng hash sẵn có của dataset | Pending |
| Cùng source code, khác nhãn | Pending |
| Cùng function, nhiều records | Pending |
| Trùng sau chuẩn hóa whitespace và line ending | Pending |
| Trùng sau khi bỏ comment, nếu làm an toàn | Pending |

## F. Source code quality

| Kiểm tra | Kết quả |
| --- | --- |
| Empty function | Pending |
| Function cực ngắn | Pending |
| Function cực dài | Pending |
| Phân bố số dòng | Pending |
| Phân bố độ dài ký tự hoặc token | Pending |
| Mẫu trông như malformed | Pending |

Ghi nhận một vài function vulnerable đã xem thủ công. Không dán toàn bộ dataset vào báo cáo.

## G. Graph readiness

| Câu hỏi | Kết quả |
| --- | --- |
| Đủ source code để thử trích graph | Pending |
| Manifest 20–50 function | Pending |
| Đường dẫn manifest | Pending |

Chưa sinh CPG cho toàn bộ dữ liệu.

## Kết luận

Chỉ điền khi notebook đã chạy trên dữ liệu thật.

1. DiverseVul có phù hợp với CWE classification hay không: Pending.
2. Có bao nhiêu CWE thực sự usable: Pending. Usable phụ thuộc ngưỡng nhóm chưa chọn.
3. Class imbalance nghiêm trọng tới mức nào: Pending.
4. Multi-CWE có phải vấn đề đáng kể không: Pending.
5. Duplicate có nghiêm trọng không: Pending.
6. Project-wise split có khả thi không: Pending.
7. Source code có đủ điều kiện để thử graph extraction không: Pending.
8. Quyết định nhóm cần đưa ra tiếp theo: xem mục dưới. Chưa đủ bằng chứng để chọn dataset cuối cùng.

## Quyết định còn mở

- Có giữ DiverseVul làm dataset chính hay không.
- Ngưỡng số sample tối thiểu của một CWE.
- Chính sách multi-CWE.
- Có loại duplicate hay không, và định nghĩa duplicate nào.
- Random split, project-wise split, hay chronological split.
- Biểu diễn đồ thị. CPG vẫn chỉ là candidate.

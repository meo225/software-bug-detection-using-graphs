# Đặc tả giao diện dữ liệu (Data Interface Specification)

Phiên bản: 1.0
Phạm vi: dữ liệu xử lý do Task 4.0 bàn giao cho Task 4.1a, 4.1b, 4.1c, 4.2 và 5.3.
Tài liệu liên quan: `docs/3_1_graph_schema.md`, `configs/graph/schema_spec.yaml`, `docs/2_3_split.md`, `reports/graph/3_3_extraction.md`.

Mọi thay đổi đối với tài liệu này phải tăng số phiên bản và báo cho bên còn lại trước khi áp dụng.

## 1. Mẫu và nhãn

- Mỗi mẫu là một hàm, khóa là `sample_id` (dạng `row-N`).
- Nhãn `y` nằm trong [0, 22], theo `cwe_mapping` trong `configs/graph/schema_spec.yaml`.
- Chính sách nhãn: một nhãn duy nhất cho mỗi hàm (`single_label_multiclass`).
- Tập mẫu hợp lệ: 7.799 mẫu cho mỗi loại graph (gồm cả graph vượt ngưỡng kích thước). 1.278 mẫu bị loại nằm trong `reports/graph/3_3_failed_samples.csv` và không đưa vào train, validation, test.

## 2. Chia dữ liệu

- Hai protocol: `project_wise` (đánh giá chính trên project chưa thấy) và `seen_project` (đối chứng).
- Lấy đúng cột `project_wise_split` và `seen_project_split` trong `data/splits/diversevul_experiment_manifest.csv`. Không chia lại, không tách thêm theo project hoặc commit.

## 3. Biểu diễn graph

Mỗi mẫu là một đối tượng PyTorch Geometric `Data` với các trường:

| Trường | Kiểu | Ý nghĩa |
| :--- | :--- | :--- |
| `x_type` | LongTensor [N] | id loại node (`node_type`) |
| `x_tok` | LongTensor [N, K] | id token của node, cắt hoặc đệm về độ dài K, đệm bằng 0 |
| `edge_index` | LongTensor [2, E] | cạnh, giữ chiều gốc của dữ liệu trích xuất |
| `edge_type` | LongTensor [E] | 0 = AST, 1 = CFG, 2 = DATA_DEP (Graph A chỉ có 0) |
| `y` | LongTensor [1] | nhãn trong [0, 22] |
| `sample_id` | str | khóa mẫu |
| `is_oversized` | bool | vượt ngưỡng kích thước theo `schema_spec.yaml` |

Quy ước:
- Cạnh ngược (nếu cần truyền tin hai chiều) do model thêm khi train, không lưu sẵn trong dữ liệu.
- Không đưa project, commit, CVE hoặc CWE vào đặc trưng.

## 4. Token và vocabulary

- Token lấy từ trường `code_token` của từng node, tách theo khoảng trắng. Nguồn dữ liệu đã chuẩn hóa chữ thường và thay chuỗi ký tự bằng `<STR>`.
- Vocabulary của `node_type` và của token được fit **chỉ trên tập train** của từng protocol. Mỗi protocol một tệp vocabulary.
- Token ngoài vocabulary ánh xạ về `<UNK>`, đệm dùng id 0.

## 5. Graph quá lớn

- Dữ liệu giữ nguyên mọi graph, chỉ gắn cờ `is_oversized`. Số liệu: 554 graph A và 997 graph B vượt ngưỡng (ngưỡng trong schema: 1.000 node hoặc 3.000 cạnh, chỉ để cảnh báo).
- Việc giữ, cắt hay bỏ do **cấu hình lúc train** quyết định, không quyết định ở bước tiền xử lý.

## 6. Tệp bàn giao

- Một tệp `.pt` cho mỗi tổ hợp (graph, protocol, split), chứa danh sách `Data`.
- Tệp vocabulary và manifest cho mỗi protocol.
- Bảng số mẫu theo CWE và theo split.
- Bộ 30 graph pilot đã chuyển sang cùng định dạng để kiểm thử sớm. Nhãn pilot chỉ dùng để kiểm tra chạy được, không dùng để đánh giá.
- Output của notebook chỉ chứa các tệp bàn giao. Tệp tạm đặt ngoài thư mục output để New Dataset không lấy thừa.
- Lưu thành Kaggle Dataset riêng tư `DiverseVul 9077 - Processed Graph Data`, chia sẻ cho cả nhóm. Không commit dữ liệu graph lên git.

## 7. Các quyết định và giá trị mặc định

| Quyết định | Giá trị mặc định | Người quyết định | Ghi chú |
| :--- | :--- | :--- | :--- |
| Độ dài token K | 16 | Hoàng, đo lại trên tập train | Mặc định chọn theo mẫu 25 graph pilot: K = 8 phủ 83% node, K = 16 phủ 92%, K = 32 phủ 97% (không tính node Method, vốn chứa toàn bộ hàm và luôn bị cắt). Quy tắc chốt: K bằng phân vị 95 của số token mỗi node trên tập train, tối đa 32. |
| Xử lý graph quá lớn lúc train | Giữ nguyên, không cắt | Mai, qua tham số `max_nodes` trong cấu hình train | Chạy thêm một cấu hình `max_nodes = 1000` (ngưỡng của schema 3.1) để so sánh độ nhạy. Tiền lệ: Vul-LMGNNs loại graph trên 500 node. |
| Cạnh ngược | Thêm lúc train | Mai | Không lưu sẵn |
| Seed | 3 seed, chốt danh sách trước khi chạy | Cả hai | Ghi vào cấu hình |

## 8. Kiểm tra trước khi bàn giao

- Số mẫu mỗi (graph, protocol, split) khớp báo cáo 3.3 và manifest.
- Vocabulary không đọc validation hoặc test.
- Đọc lại được 30 graph pilot và số node, số cạnh khớp báo cáo 3.2.
- Không mẫu nào xuất hiện ở hai split của cùng một protocol.

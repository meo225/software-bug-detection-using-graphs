# Đặc tả giao diện dữ liệu (Data Interface Specification)

Phiên bản: 1.2
Phạm vi: dữ liệu xử lý do Task 4.0 bàn giao cho Task 4.1a, 4.1b, 4.1c, 4.2 và 5.3.
Tài liệu liên quan: `docs/3_1_graph_schema.md`, `configs/graph/schema_spec.yaml`, `docs/2_3_split.md`, `reports/graph/3_3_extraction.md`.

Mọi thay đổi đối với tài liệu này phải tăng số phiên bản và báo cho bên còn lại trước khi áp dụng.

Lịch sử thay đổi:
- 1.2: Task 4.0 hoàn tất, bổ sung cấu trúc `validation_report.json` và `pilot/`, bổ sung kiểm tra input trùng. Định dạng dữ liệu không đổi so với 1.1.
- 1.1: đổi đối tượng PyTorch Geometric `Data` thành `dict` các tensor thuần (không cần cài thêm thư viện, đọc bằng `torch.load`), thêm trường `x_rel` (vị trí dòng tương đối, thuộc danh sách feature cho phép trong `schema_spec.yaml`), chốt cấu trúc thư mục bàn giao, chốt tham số vocabulary theo `schema_spec.yaml`. Mã chuyển đổi tối thiểu nằm ở `src/graph/processed.py` và `scripts/build_processed_data.py`.
- 1.0: bản đầu.

## 1. Mẫu và nhãn

- Mỗi mẫu là một hàm, khóa là `sample_id` (dạng `row-N`).
- Nhãn `y` nằm trong [0, 22], theo `cwe_mapping` trong `configs/graph/schema_spec.yaml`.
- Chính sách nhãn: một nhãn duy nhất cho mỗi hàm (`single_label_multiclass`).
- Tập mẫu hợp lệ: 7.799 mẫu cho mỗi loại graph (gồm cả graph vượt ngưỡng kích thước). 1.278 mẫu bị loại nằm trong `reports/graph/3_3_failed_samples.csv` và không đưa vào train, validation, test.

## 2. Chia dữ liệu

- Hai protocol: `project_wise` (đánh giá chính trên project chưa thấy) và `seen_project` (đối chứng).
- Lấy đúng cột `project_wise_split` và `seen_project_split` trong `data/splits/diversevul_experiment_manifest.csv`. Không chia lại, không tách thêm theo project hoặc commit.

## 3. Biểu diễn graph

Mỗi mẫu là một `dict` với các trường:

| Trường | Kiểu | Ý nghĩa |
| :--- | :--- | :--- |
| `x_type` | LongTensor [N] | id loại node (`node_type`) |
| `x_tok` | LongTensor [N, K] | id token của node, cắt hoặc đệm về độ dài K, đệm bằng 0 |
| `x_rel` | FloatTensor [N] | `rel_line_number` trong [0, 1], thiếu thì 0 |
| `edge_index` | LongTensor [2, E] | cạnh, giữ chiều gốc của dữ liệu trích xuất |
| `edge_type` | LongTensor [E] | 0 = AST, 1 = CFG, 2 = DATA_DEP (Graph A chỉ có 0) |
| `y` | LongTensor [1] | nhãn trong [0, 22] |
| `sample_id` | str | khóa mẫu |
| `is_oversized` | bool | `status` của bản ghi 3.3 bằng `OVERSIZED_GRAPH` (ngưỡng 1.000 node hoặc 3.000 cạnh trong `schema_spec.yaml`) |

Thứ tự node giữ nguyên thứ tự trong JSON. Cạnh có đầu mút không thuộc tập node bị bỏ. Graph A và Graph B của cùng một mẫu có cùng số node, mã chuyển đổi báo lỗi nếu khác.

Quy ước:
- Cạnh ngược (nếu cần truyền tin hai chiều) do model thêm khi train, không lưu sẵn trong dữ liệu.
- Không đưa project, commit, CVE hoặc CWE vào đặc trưng.

## 4. Token và vocabulary

- Token lấy từ trường `code_token` của từng node, tách theo khoảng trắng. Nguồn dữ liệu đã chuẩn hóa chữ thường và thay chuỗi ký tự bằng `<STR>`.
- Vocabulary token: tần suất tối thiểu 2 (`vocabulary_policy.min_token_frequency` trong `schema_spec.yaml`), token đặc biệt `<PAD>`=0, `<UNK>`=1, `<MASK>`=2, các token còn lại xếp theo tần suất giảm dần rồi theo bảng chữ cái. Vocabulary loại node: tần suất tối thiểu 1, gồm `<PAD>`=0 và `<UNK>`=1.
- Vocabulary của `node_type` và của token được fit **chỉ trên tập train** của từng protocol. Mỗi protocol một tệp `vocab.json`, tính trên Graph A vì node Graph B trùng node Graph A.
- Token ngoài vocabulary ánh xạ về `<UNK>`, đệm dùng id 0.

## 5. Graph quá lớn

- Dữ liệu giữ nguyên mọi graph, chỉ gắn cờ `is_oversized`. Số liệu: 554 graph A và 997 graph B vượt ngưỡng (ngưỡng trong schema: 1.000 node hoặc 3.000 cạnh, chỉ để cảnh báo).
- Việc giữ, cắt hay bỏ do **cấu hình lúc train** quyết định, không quyết định ở bước tiền xử lý.

## 6. Tệp bàn giao

Cấu trúc thư mục `processed/`:
- `<protocol>/graph_a_<split>.pt` và `<protocol>/graph_b_<split>.pt` với split thuộc `train`, `validation`, `test`: danh sách `dict` ở mục 3, lưu bằng `torch.save`.
- `<protocol>/vocab.json`: `node_type`, `token`, `k`.
- `<protocol>/manifest.csv`: `sample_id`, `split`, `y` của các mẫu hợp lệ.
- `cwe_counts.csv`: số mẫu theo protocol, split và CWE.
- `metadata.json`: phiên bản đặc tả, tham số, số mẫu bị bỏ và lý do, số mẫu và số graph quá lớn theo từng tệp, K và phân vị 95 thô.

Task 4.0 gồm, và đã được mã hóa trong `scripts/build_processed_data.py`:
- Chuyển bộ 30 graph pilot của Task 3.2 sang cùng định dạng (`processed/pilot/`, kèm `pilot_report.json`). Chỉ các mẫu có status hợp lệ (25 mẫu) được chuyển, nhãn `y = -1` vì pilot giữ chuỗi CWE thô. Chỉ dùng kiểm tra chạy được.
- Kiểm tra tự động (`validation_report.json`, mục 8), thống kê số node, số cạnh theo loại, tỷ lệ node chạm giới hạn K, và số mẫu có input mô hình trùng giữa train và validation hoặc test.
- Lưu thành Kaggle Dataset riêng tư `DiverseVul 9077 - Processed Graph Data`, chia sẻ cho cả nhóm. Output của notebook chỉ chứa thư mục `processed`, tệp tạm đặt ngoài thư mục output. Không commit dữ liệu graph lên git.

## 7. Các quyết định và giá trị mặc định

| Quyết định | Giá trị mặc định | Người quyết định | Ghi chú |
| :--- | :--- | :--- | :--- |
| Độ dài token K | Tính tự động | Mã chuyển đổi | K bằng phân vị 95 (nearest-rank) của số token mỗi node trên tập train của từng protocol, không tính node Method vì node này chứa cả hàm và luôn bị cắt, chặn trên 32, tối thiểu 1. Giá trị cụ thể được ghi trong `metadata.json`. Tham khảo từ mẫu 25 graph pilot: K = 8 phủ 83% node, K = 16 phủ 92%, K = 32 phủ 97%. Hoàng có thể đổi tham số `--k-percentile`, `--k-cap` hoặc ép `--k` sau khi xem thống kê, nhưng phải báo Mai. |
| Xử lý graph quá lớn lúc train | Giữ nguyên, không cắt | Mai, qua tham số `max_nodes` trong cấu hình train | Chạy thêm một cấu hình `max_nodes = 1000` (ngưỡng của schema 3.1) để so sánh độ nhạy. Tiền lệ: Vul-LMGNNs loại graph trên 500 node. |
| Cạnh ngược | Thêm lúc train | Mai | Không lưu sẵn |
| Seed | 3 seed, chốt danh sách trước khi chạy | Cả hai | Ghi vào cấu hình |

## 8. Kiểm tra trước khi bàn giao

`validation_report.json` do `src/graph/processed_checks.py` tạo, đọc lại các tệp `.pt` đã lưu. Mọi kiểm tra phải đạt:
- Tổng số mẫu hợp lệ bằng 7.799 và số graph quá lớn bằng 554 (A) và 997 (B), khớp báo cáo 3.3.
- Danh sách mẫu của từng (graph, protocol, split) khớp `manifest.csv`, Graph A và Graph B cùng danh sách và cùng node.
- Không mẫu nào xuất hiện ở hai split của cùng một protocol, split khớp manifest gốc.
- `vocab.json` ghi băm danh sách id train (`train_ids_sha256`) khớp tập train, tức vocabulary chỉ được fit trên train. Kiểm tra này xác nhận tập id đã dùng, không đọc lại dữ liệu thô.
- Chỉ số token và loại node nằm trong vocabulary, hình dạng tensor đúng, loại cạnh trong {0,1,2} (Graph A chỉ 0), nhãn trong [0, 22], `x_rel` trong [0, 1].
- Bộ pilot chuyển được và số node, số cạnh khớp JSON gốc.

Số mẫu trùng input giữa train và validation hoặc test (băm loại node, token, cạnh và loại cạnh) được báo cáo riêng, không làm kiểm tra thất bại. Cần xét trước khi diễn giải kết quả, nhất là khi hai bản sao có nhãn khác nhau (`n_label_conflict`).

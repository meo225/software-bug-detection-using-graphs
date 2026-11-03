# Báo cáo Task 4.1a. Baseline không dùng graph và GCN, GGNN mặc định

Dữ liệu: [DiverseVul 9077 - Processed Graph Data](https://www.kaggle.com/datasets/vtnmai/diversevul-9077-processed-graph-data/data) (đặc tả `docs/4_0_data_interface_spec.md` v1.2, báo cáo `reports/graph/4_0_processed_data.md`)
Mã nguồn: `src/models/gnn.py`, `src/training/gnn_trainer.py`, `scripts/train_gnn.py`, `scripts/run_baselines_4_1a.py`
Notebook đã chạy (có log): `reports/graph/4_1a_baselines_run.ipynb`, `reports/graph/4_1a_gnn_run.ipynb`
Số liệu đầy đủ: `reports/graph/4_1a_results/` (kết quả từng seed, per-CWE, confusion matrix, lịch sử huấn luyện)
Mã chạy từ `main`, commit f7e0629. GPU Tesla T4, tổng thời gian train khoảng 70 phút.

## 1. Cấu hình

- Mô hình: GCN (đối xứng hóa, bỏ qua loại cạnh) và GGNN (6 phép biến đổi cho 3 loại cạnh × 2 chiều, GRU). 3 lớp hoặc 3 bước, dim 128, dropout 0,2, đọc ra mean và max, đầu MLP.
- Loss: cross-entropy có trọng số lớp. AdamW lr 1e-3, weight decay 1e-4, batch 32, tối đa 40 epoch, early stopping kiên nhẫn 8 theo Macro-F1 validation, seed 42, 43, 44.
- Graph quá lớn được giữ nguyên (`--max-nodes` không đặt). Tất cả siêu tham số là mặc định, chưa tinh chỉnh.
- Baseline: majority, random theo phân bố lớp, TF-IDF cộng hồi quy logistic có trọng số lớp trên token của node Method (`token_method`) và của mọi node (`token_nodes`).
- Macro-F1 tính trên cả 23 nhãn, nhãn không có mẫu dự đoán tính là 0.

## 2. Kết quả trên test (Macro-F1, trung bình 3 seed)

| Protocol | random | token_nodes | token_method | GCN A | GCN B | GGNN A | GGNN B |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| project_wise | 0,039 | **0,100** | 0,088 | 0,066 | 0,055 | 0,066 | 0,071 |
| seen_project | 0,038 | 0,154 | **0,170** | 0,103 | 0,090 | 0,101 | 0,098 |

Độ lệch chuẩn giữa seed của GNN khoảng 0,005 đến 0,012. Hai baseline token cho cùng kết quả với mọi seed. Bảng đầy đủ (weighted-F1, MCC, accuracy, validation) nằm trong `4_1a_results/`.

## 3. Nhận xét

- GNN hơn random nhưng thua cả hai baseline token ở cả hai protocol.
- Graph B (thêm CFG, DATA_DEP) không tốt hơn Graph A. Chênh lệch lớn nhất là GGNN project_wise (0,071 so với 0,066), nằm trong độ lệch chuẩn. Graph B chậm hơn 1,5 đến 2 lần (khoảng 130 đến 280 giây mỗi seed so với 90 đến 170) và dùng VRAM gấp khoảng 1,7 lần (đỉnh khoảng 1,9 GB so với 1,1 GB).
- GGNN không hơn GCN rõ ràng.
- Với project_wise, GGNN trên Graph A có F1 test từng lớp tương đối cao hơn ở CWE-787 (0,19), CWE-190, CWE-59, CWE-20 và CWE-125, bằng 0 ở CWE-120, CWE-369, CWE-400, CWE-401, CWE-415, CWE-617. Số mẫu test của nhiều lớp chỉ 4 đến 13 nên F1 từng lớp nhiễu.
- Mô hình học thuộc rất sớm: loss train giảm từ 3,1 xuống dưới 0,5 trong khi Macro-F1 validation dao động quanh 0,03 đến 0,06. Epoch tốt nhất thường là 6 đến 30.
- Validation của project_wise gần mức ngẫu nhiên với mọi mô hình (CWE-787 chiếm 31%, CWE-703 chỉ 3 mẫu). Khi so sánh nên dựa vào test và nêu rõ điều này.

## 4. Giới hạn của kết luận

- Chưa thể kết luận graph không giúp ích: mới chạy một cấu hình mặc định, chưa tinh chỉnh.
- Early stopping theo Macro-F1 validation nhiễu, kết quả từng seed lệch nhau nhiều.
- Chưa có thí nghiệm giữ so với bỏ hoặc cắt graph quá lớn.
- Seen_project có mẫu input trùng giữa train và held-out (5 validation, 6 test), project_wise thì không.
- Chưa chạy baseline văn bản mạnh như CodeBERT (tùy chọn trong plan).
- Chỉ so sánh trên một lần chia dữ liệu và 3 seed, chưa có kiểm định thống kê.

## 5. Ghi chú cho 4.1b, 4.1c, 4.2

Chạy chung mã, dữ liệu, metric với 4.1a để kết quả so sánh được.

Quy ước bắt buộc:
- Input: Kaggle Dataset `DiverseVul 9077 - Processed Graph Data`. Không dùng bản xử lý riêng.
- Mã: `scripts/train_gnn.py` và `src/` trên nhánh `main`, notebook clone `main` như `notebooks/4_1a_gnn.ipynb`. Không nhúng mã vào notebook.
- Seed 42, 43, 44, báo cáo trung bình ± độ lệch chuẩn, đủ hai protocol, chọn epoch theo validation và báo cáo test.
- Báo Macro-F1 (chính), weighted-F1, MCC, accuracy, per-CWE, confusion matrix, thời gian, VRAM, số tham số.
- So sánh với `4_1a_results/` và baseline token ở mục 2. Thay đổi nào cũng đặt cạnh mốc mặc định.

Việc đáng thử, đổi một thứ mỗi lần để biết thay đổi nào có tác dụng:
1. Tiêu chí early stopping: dùng validation loss hoặc làm mượt Macro-F1, vì Macro-F1 validation nhiễu.
2. Chống học thuộc: tăng dropout và weight decay, giảm dim, thêm bước giảm lr.
3. `--max-nodes` (ví dụ ngưỡng quanh P95 là 1.239 node) và so sánh giữ, cắt graph quá lớn như plan 4.0 yêu cầu.
4. Số lớp hoặc số bước, và cách đọc ra (mean, max, tổng).
5. Dùng loại cạnh cho GCN hoặc để GGNN học riêng ba loại cạnh, nhằm tách tác động của graph khỏi tác động của mô hình.
6. Sửa biểu diễn node: mặc định là trung bình embedding token, có thể thử trọng số theo loại node.
7. Tùy chọn: CodeBERT làm baseline văn bản mạnh.

Các baseline token đang đạt 0,100 (project_wise) và 0,170 (seen_project). Mốc này nên vượt trước khi kết luận về giá trị của graph.

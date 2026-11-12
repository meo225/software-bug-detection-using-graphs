# Báo cáo Task 4.2: Tinh chỉnh GGNN trên Graph B

Dữ liệu: [DiverseVul 9077 - Processed Graph Data](https://www.kaggle.com/datasets/vtnmai/diversevul-9077-processed-graph-data/data), version 1 (`vtnmai/diversevul-9077-processed-graph-data/versions/1`), theo [Task 4.0](4_0_processed_data.md).
Mã thực nghiệm: commit `ba5656eb2ea93b8ea31a066d16128b5c3bd63cc7`.
Notebook nguồn: [4_2_ggnn_tuning.ipynb](../../notebooks/4_2_ggnn_tuning.ipynb). Notebook đã thực thi: [bản chạy đầy đủ trên Kaggle](4_2_ggnn_tuning_run.ipynb), gồm tinh chỉnh, đánh giá test và phân tích độ nhạy trong cùng một phiên.
Kết quả: [giai đoạn tinh chỉnh](4_2_results/tuning/), [đánh giá test cuối](4_2_results/final/), [phân tích độ nhạy](4_2_results/sensitivity/) và [bảng, biểu đồ](4_2_results/figures/).
Checkpoint được lưu trên Kaggle và không được đưa vào Git.
Kết quả tham chiếu: [báo cáo Task 4.1a](4_1a_baselines_gnn.md) và [báo cáo Task 4.1b](4_1b_gcn_tuning.md).

## 1. Cấu hình

GGNN-B là mô hình Gated Graph Neural Network sử dụng Graph B, gồm cả ba loại cạnh AST, CFG và DATA_DEP. Khác với GCN ở Task 4.1b, GGNN phân biệt loại cạnh: mỗi bước lan truyền sử dụng 3 loại cạnh × 2 chiều, tổng hợp bằng GRUCell. Cấu hình được lựa chọn dựa trên validation; test chỉ được đánh giá sau khi cấu hình đã cố định. Protocol `project_wise` là đánh giá chính, còn `seen_project` là đối chứng.

- Biểu diễn node giống Task 4.1a và 4.1b: tổng của embedding loại node, trung bình embedding các token không tính padding và phép chiếu vị trí dòng mã nguồn tương đối. Mô hình tổng hợp biểu diễn graph bằng mean và max; đầu phân loại MLP dự đoán một trong 23 nhãn CWE.
- B0 là cấu hình cơ sở: dim 128, 3 bước lan truyền và dropout 0,2. Hàm mất mát là cross-entropy có trọng số lớp tính từ tập train. Bộ tối ưu AdamW sử dụng learning rate 1e-3 và weight decay 1e-4. Batch size là 32, ngưỡng gradient clipping là 5,0, số epoch tối đa là 40 và patience là 8.
- Bảy cấu hình được huấn luyện trên train và chỉ đánh giá trên validation trong giai đoạn tinh chỉnh, ở hai protocol với các seed **42, 43, 44**: 7 cấu hình × 2 protocol × 3 seed = **42 lần huấn luyện**. B0 được huấn luyện lại trong cùng môi trường với các biến thể; kết quả GGNN-B của Task 4.1a được sử dụng riêng làm tham chiếu. Sau khi lựa chọn và cố định L1, sáu checkpoint tương ứng được sử dụng cho sáu lần đánh giá test.
- Checkpoint được chọn tại epoch có **Macro-F1 validation chưa làm tròn cao nhất**; nếu bằng nhau, mô hình giữ checkpoint ở epoch sớm nhất. E1 sử dụng **validation loss có trọng số** làm tiêu chí early stopping, nhưng vẫn chọn checkpoint theo Macro-F1 validation.
- Bảy cấu hình giữ đúng như Task 4.1b để hai task so sánh được với nhau. Mỗi biến thể chỉ thay đổi một yếu tố so với B0.

| ID | Thay đổi so với B0 | Giả thuyết |
| :--- | :--- | :--- |
| B0 | Giữ nguyên mặc định | Tái lập cấu hình mặc định trong môi trường tinh chỉnh |
| E1 | Early stopping: Macro-F1 → validation loss | Validation loss ít nhiễu hơn Macro-F1 |
| D1 | Dropout: 0,2 → 0,4 | Giảm hiện tượng học thuộc sớm của GGNN mặc định |
| W1 | Weight decay: 1e-4 → 1e-3 | Tăng khả năng tổng quát hóa |
| H1 | Dim: 128 → 64 | Giảm ghi nhớ và VRAM trên Graph B |
| L1 | Số bước lan truyền: 3 → 2 | Giảm over-smoothing và chi phí trên Graph B lớn hơn |
| N1 | `max_nodes`: không giới hạn → 1.000 | Giới hạn chi phí Graph B, có cắt các graph quá lớn |

### Dữ liệu và phân chia tập

Thí nghiệm sử dụng nguyên trạng dữ liệu đã xử lý của Task 4.0, cách phân chia tập, vocabulary và 23 nhãn; không trích xuất lại graph.

| Protocol | Train | Validation | Test | K (token/node) | Vocabulary token |
| :--- | ---: | ---: | ---: | ---: | ---: |
| project_wise | 6.101 | 762 | 936 | 23 | 25.151 |
| seen_project | 6.272 | 764 | 763 | 24 | 25.750 |

Graph B có **997 đồ thị bị gắn cờ quá lớn**, nhiều hơn 554 của Graph A. Quy tắc gắn cờ ở `schema_spec.yaml` là `num_nodes > 1.000` **hoặc** `num_edges > 3.000`; Graph A và Graph B có cùng tập node, nên phần chênh lệch đến từ các cạnh CFG và DATA_DEP làm vượt ngưỡng cạnh. Theo [báo cáo 4.0](4_0_processed_data.md), số graph B bị gắn cờ theo thứ tự train/validation/test là 711/82/204 ở project_wise và 785/115/97 ở seen_project. Riêng ở project_wise, test có tỷ lệ bị gắn cờ 21,8% so với 11,7% ở train, nên test nặng hơn train về kích thước đồ thị.

**Lưu ý về N1 trên Graph B.** Tham số `max_nodes` chỉ cắt theo số node, giữ 1.000 node đầu và các cạnh có cả hai đầu mút trong tập đó. Vì vậy N1 chỉ tác động lên các đồ thị có hơn 1.000 node, tức đúng 554 đồ thị cũng bị gắn cờ ở Graph A (420/32/102 ở project_wise và 445/61/48 ở seen_project, theo kiểm chứng tại Task 4.1b). Các đồ thị bị gắn cờ chỉ vì vượt ngưỡng cạnh **không** bị N1 cắt. Nói cách khác, N1 ở Task 4.2 cắt đúng cùng tập đồ thị như N1 ở Task 4.1b, nhưng mỗi đồ thị bị cắt mất nhiều cạnh hơn vì Graph B dày cạnh hơn.

## 2. Kết quả

### Kết quả validation của bảy cấu hình

Macro-F1 validation, trung bình ± độ lệch chuẩn qua 3 seed. Cột Δ là chênh lệch so với B0 trong cùng protocol.

| ID | project_wise | Δ so với B0 | seen_project | Δ so với B0 | weighted-F1 (pw) | MCC (pw) | Epoch tốt nhất | Giây/lần | VRAM (MB) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **L1** | **0,0616 ± 0,0119** | **+0,0001** | **0,1603 ± 0,0014** | **+0,0092** | 0,1025 | 0,0221 | 20,7 | 207 | 1.408 |
| B0 | 0,0615 ± 0,0115 | 0,0000 | 0,1511 ± 0,0058 | 0,0000 | 0,1171 | 0,0402 | 22,8 | 291 | 1.989 |
| H1 | 0,0608 ± 0,0066 | −0,0007 | 0,1351 ± 0,0386 | −0,0161 | 0,1052 | 0,0164 | 18,7 | 167 | 1.029 |
| N1 | 0,0570 ± 0,0087 | −0,0045 | 0,1595 ± 0,0040 | +0,0084 | 0,1194 | 0,0296 | 19,8 | 209 | 930 |
| W1 | 0,0568 ± 0,0069 | −0,0047 | 0,1583 ± 0,0003 | +0,0072 | 0,0933 | 0,0193 | 22,7 | 287 | 1.989 |
| D1 | 0,0509 ± 0,0023 | −0,0106 | 0,1406 ± 0,0111 | −0,0106 | 0,1030 | 0,0055 | 22,0 | 283 | 1.989 |
| E1 | 0,0488 ± 0,0121 | −0,0127 | 0,1051 ± 0,0216 | −0,0460 | 0,0914 | 0,0270 | 8,2 | 101 | 1.963 |

### Xếp hạng validation và lựa chọn đã cố định

Tiêu chí lựa chọn được khai báo trước: trung bình Macro-F1 validation chưa làm tròn của `project_wise` qua 3 seed. Thứ hạng là L1 > B0 > H1 > N1 > W1 > D1 > E1. Cấu hình **L1** (2 bước lan truyền) được cố định trong `frozen_selection.json` trước khi chạm vào tập test.

**Khoảng cách giữa L1 và B0 chỉ là 0,00012, trong khi độ lệch chuẩn giữa các seed là ±0,0119 và ±0,0115.** Đây thực chất là một thế hòa: thay đổi seed có thể đảo ngược thứ hạng. Việc lựa chọn vẫn được giữ nguyên theo đúng quy tắc đã cố định, nhưng không thể coi L1 là cấu hình tốt hơn B0 trên validation.

Ba cấu hình đứng đầu (L1, B0, H1) chênh nhau 0,0008, nhỏ hơn một phần mười độ lệch chuẩn. Chỉ D1 và E1 kém rõ rệt, vượt độ lệch chuẩn. E1 kém nhất ở cả hai protocol, dừng rất sớm (trung bình epoch 8,2 so với 18,7 đến 22,8 của các cấu hình khác): dừng theo validation loss có trọng số khiến mô hình dừng trước khi Macro-F1 đạt đỉnh.

### Kết quả test của cấu hình L1 đã cố định

Sáu checkpoint đã lưu được nạp lại và chấm trên test, không huấn luyện lại.

| Protocol | Macro-F1 | Weighted-F1 | MCC | Accuracy | Tham số | Giây/seed | VRAM (MB) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| project_wise | 0,0579 ± 0,0106 | 0,1043 ± 0,0090 | 0,0292 ± 0,0039 | 0,1075 ± 0,0048 | 3.456.407 | 167 | 1.380 |
| seen_project | 0,0930 ± 0,0130 | 0,1324 ± 0,0166 | 0,0686 ± 0,0194 | 0,1354 ± 0,0181 | 3.533.079 | 247 | 1.408 |

### So sánh trên test với các mốc tham chiếu

Macro-F1 test, trung bình ± độ lệch chuẩn qua 3 seed. Cột kết luận so sánh trị tuyệt đối của chênh lệch với độ lệch chuẩn lớn hơn trong hai nhóm được so.

| Phương pháp | project_wise | seen_project |
| :--- | ---: | ---: |
| token_nodes (4.1a) | 0,1000 ± 0,0000 | 0,1541 ± 0,0000 |
| token_method (4.1a) | 0,0875 ± 0,0000 | 0,1701 ± 0,0000 |
| **GGNN-B mặc định (4.1a)** | **0,0712 ± 0,0049** | 0,0977 ± 0,0047 |
| GCN-A mặc định (4.1a) | 0,0664 ± 0,0088 | 0,1033 ± 0,0051 |
| GGNN-A mặc định (4.1a) | 0,0663 ± 0,0075 | 0,1010 ± 0,0066 |
| GGNN-B tinh chỉnh L1 (4.2) | 0,0579 ± 0,0106 | 0,0930 ± 0,0130 |
| GCN-A tinh chỉnh L1 (4.1b) | 0,0552 ± 0,0051 | 0,1000 ± 0,0054 |
| GCN-B mặc định (4.1a) | 0,0551 ± 0,0121 | 0,0897 ± 0,0078 |
| random (4.1a) | 0,0393 ± 0,0039 | 0,0383 ± 0,0033 |
| majority (4.1a) | 0,0100 ± 0,0000 | 0,0102 ± 0,0000 |

Kết luận từng cặp so sánh với GGNN-B tinh chỉnh L1:

| So với | project_wise | Kết luận | seen_project | Kết luận |
| :--- | ---: | :--- | ---: | :--- |
| token_nodes | −0,0421 | thấp hơn | −0,0611 | thấp hơn |
| token_method | −0,0296 | thấp hơn | −0,0771 | thấp hơn |
| GGNN-B mặc định | −0,0134 | **thấp hơn** | −0,0047 | trong độ lệch chuẩn |
| GCN-A mặc định | −0,0085 | trong độ lệch chuẩn | −0,0103 | trong độ lệch chuẩn |
| GGNN-A mặc định | −0,0085 | trong độ lệch chuẩn | −0,0080 | trong độ lệch chuẩn |
| GCN-A tinh chỉnh (4.1b) | +0,0027 | trong độ lệch chuẩn | −0,0070 | trong độ lệch chuẩn |
| GCN-B mặc định | +0,0028 | trong độ lệch chuẩn | +0,0033 | trong độ lệch chuẩn |
| random | +0,0186 | cao hơn | +0,0547 | cao hơn |

### Phân tích độ nhạy: test của cả bảy cấu hình

Phần này chạy **sau** khi lựa chọn đã cố định và kết quả test chính thức đã ghi. Sáu cấu hình không được chọn được nạp từ checkpoint đã lưu và chấm trên test, không huấn luyện lại và không dùng để đổi lựa chọn. Mục đích là đo xem thứ hạng validation có chuyển sang test hay không.

| ID | pw validation | pw test | sp validation | sp test |
| :--- | ---: | ---: | ---: | ---: |
| **L1** (được chọn) | **0,0616** | **0,0579 ± 0,0106** | **0,1603** | **0,0930 ± 0,0130** |
| B0 | 0,0615 | 0,0604 ± 0,0172 | 0,1511 | 0,0937 ± 0,0033 |
| H1 | 0,0608 | 0,0642 ± 0,0083 | 0,1351 | 0,0894 ± 0,0148 |
| N1 | 0,0570 | **0,0647 ± 0,0094** | 0,1595 | 0,0902 ± 0,0132 |
| W1 | 0,0568 | 0,0623 ± 0,0122 | 0,1583 | **0,1083 ± 0,0034** |
| D1 | 0,0509 | 0,0512 ± 0,0126 | 0,1406 | 0,0945 ± 0,0096 |
| E1 | 0,0488 | 0,0561 ± 0,0011 | 0,1051 | 0,0896 ± 0,0069 |

| Protocol | Spearman validation-test | Test của cấu hình được chọn | Test cao nhất | Cấu hình có test cao nhất | Khoảng dao động test |
| :--- | ---: | ---: | ---: | :--- | ---: |
| project_wise | 0,357 | 0,0579 | 0,0647 | N1 | 0,0135 |
| seen_project | 0,393 | 0,0930 | 0,1083 | W1 | 0,0189 |

Tương quan hạng giữa validation và test chỉ ở mức 0,36 đến 0,39, chủ yếu do D1 và E1 kém ở cả hai tập. Trong năm cấu hình còn lại, thứ hạng gần như bị xáo trộn hoàn toàn: **cấu hình được chọn L1 đứng thứ 5 trên 7 ở test project_wise**, còn N1 đứng áp chót trên validation lại cao nhất trên test. Khoảng dao động Macro-F1 test giữa bảy cấu hình là 0,0135 ở project_wise, tương đương 23% giá trị của cấu hình được chọn.

## 3. Nhận xét

### Tinh chỉnh một yếu tố không cải thiện test

GGNN-B tinh chỉnh L1 đạt 0,0579 trên test project_wise, **thấp hơn** GGNN-B mặc định của Task 4.1a (0,0712) một khoảng 0,0134, vượt độ lệch chuẩn. Ở seen_project, chênh lệch −0,0047 nằm trong độ lệch chuẩn.

Đây là lần thứ hai hiện tượng này lặp lại: Task 4.1b cũng chọn L1 trên validation rồi thu được kết quả test thấp hơn GCN-A mặc định. Hai task độc lập, hai mô hình khác nhau, cùng một kết quả. Kết hợp với phân tích độ nhạy ở trên, lời giải thích hợp lý là **validation của protocol project_wise không đủ tin cậy để xếp hạng cấu hình**: tập validation gồm các project khác với test, nên thứ hạng học được trên validation không chuyển sang test.

Hệ quả cho báo cáo chung: không thể khẳng định cấu hình nào là tối ưu, và cũng không thể khẳng định việc tinh chỉnh có ích. Mốc tốt nhất của GNN trên test project_wise vẫn là **GGNN-B mặc định của Task 4.1a (0,0712)**, thu được mà không cần tinh chỉnh.

### Trả lời RQ1 và RQ2

**RQ1 — GGNN có hơn GCN không?** Không có bằng chứng. GGNN-B tinh chỉnh (0,0579) so với GCN-A tinh chỉnh (0,0552) chênh +0,0027 ở project_wise và −0,0070 ở seen_project, cả hai đều nằm trong độ lệch chuẩn. Ở cấu hình mặc định của Task 4.1a, GGNN-B (0,0712) có nhỉnh hơn GCN-A (0,0664) nhưng chênh lệch 0,0048 vẫn nhỏ hơn độ lệch chuẩn 0,0088 của GCN-A.

**RQ2 — Graph B (thêm CFG, DATA_DEP) có hơn Graph A không?** Không có bằng chứng. Ở cấu hình mặc định, GGNN-B (0,0712) so với GGNN-A (0,0663) chênh +0,0049, nhỏ hơn độ lệch chuẩn 0,0075 của GGNN-A; GCN-B (0,0551) lại thấp hơn GCN-A (0,0664). Hai chiều trái ngược nhau cho thấy việc thêm cạnh ngữ nghĩa không mang lại cải thiện ổn định, dù chi phí cao hơn đáng kể.

**So với baseline không dùng graph.** Tất cả cấu hình GNN đều thua baseline token ở cả hai protocol với khoảng cách vượt xa độ lệch chuẩn: −0,0421 so với token_nodes ở project_wise và −0,0771 so với token_method ở seen_project. Mọi cấu hình GNN đều cao hơn random, nên mô hình có học được tín hiệu, nhưng tín hiệu đó yếu hơn so với việc chỉ dùng túi token.

### Per-CWE và mất cân bằng lớp

Trên test project_wise, GGNN-B L1 có **7 trên 23 CWE đạt F1 bằng 0**, so với 6 của GGNN-B mặc định. Phân theo kích thước lớp:

| Nhóm lớp | Số CWE | F1 trung bình, L1 (4.2) | F1 trung bình, mặc định (4.1a) |
| :--- | ---: | ---: | ---: |
| Lớp đầu, support ≥ 50 | 7 | 0,1255 | 0,1208 |
| Lớp đuôi, support ≤ 15 | 11 | 0,0265 | 0,0433 |

Cấu hình L1 nhích lên ở các lớp nhiều mẫu nhưng tụt ở các lớp ít mẫu. Vì Macro-F1 lấy trung bình đều trên 23 lớp, phần mất ở đuôi chiếm ưu thế và kéo Macro-F1 tổng thể xuống. Các lớp có F1 bằng 0 đều có support rất thấp: CWE-400 (5 mẫu), CWE-401 (4), CWE-770 (4), CWE-264 (6), CWE-59 (9), CWE-617 (10), CWE-835 (10).

Một vài lớp nhiều mẫu có cải thiện rõ: CWE-119 từ 0,097 lên 0,143 và CWE-399 từ 0,008 lên 0,081. Ngược lại CWE-20 giảm từ 0,143 xuống 0,096 và CWE-189 giảm từ 0,116 xuống 0,034.

### Học thuộc sớm

Ở cuối quá trình huấn luyện, loss train giảm sâu trong khi Macro-F1 validation vẫn rất thấp:

| Cấu hình | Protocol | Loss train cuối | Macro-F1 validation tốt nhất |
| :--- | :--- | ---: | ---: |
| B0 | project_wise | 0,6811 | 0,0615 |
| B0 | seen_project | 0,3211 | 0,1511 |
| L1 | project_wise | 0,5267 | 0,0616 |
| L1 | seen_project | 0,2897 | 0,1603 |

Hiện tượng này giống Task 4.1a. Hai cấu hình chống học thuộc trực tiếp là D1 (dropout 0,4) và W1 (weight decay 1e-3) đều **không** cải thiện Macro-F1 validation, thậm chí D1 còn kém nhất sau E1. Như vậy khoảng cách giữa train và validation nhiều khả năng không chỉ do dung lượng mô hình, mà do khác biệt phân phối giữa các project.

### Thời gian, bộ nhớ và số tham số

Tổng thời gian huấn luyện của giai đoạn tinh chỉnh là **2,58 giờ GPU** cho 42 lần huấn luyện trên Kaggle T4. Cộng thêm đánh giá test và phân tích độ nhạy, toàn bộ notebook chạy trong một phiên.

Cấu hình L1 rẻ hơn B0 rõ rệt: 207 giây mỗi lần huấn luyện so với 291 giây, và VRAM đỉnh 1.408 MB so với 1.989 MB. N1 có VRAM thấp nhất (930 MB) vì cắt graph, còn H1 rẻ nhất về thời gian (167 giây) vì dim nhỏ hơn. E1 chỉ mất 101 giây nhưng do dừng quá sớm, không phải do hiệu quả.

So với Graph A ở Task 4.1b, GGNN trên Graph B tốn hơn đáng kể: VRAM đỉnh 1.989 MB của B0 so với 710 đến 889 MB của GCN-A ở cùng cấu hình B0. Chi phí này không đổi lại cải thiện đo được.

## 4. Giới hạn

- Tiêu chí lựa chọn chỉ dựa trên validation của một protocol, trong khi phân tích độ nhạy cho thấy tiêu chí này tương quan yếu với test. Kết quả chính thức của task vẫn là cấu hình L1, nhưng không nên diễn giải là cấu hình tốt nhất.
- Ngân sách tinh chỉnh là 7 cấu hình, mỗi cấu hình chỉ đổi một yếu tố. Không khảo sát tương tác giữa các yếu tố, không tinh chỉnh learning rate hay batch size.
- Mỗi cấu hình chỉ có 3 seed, nên độ lệch chuẩn ước lượng thô và chưa có kiểm định thống kê hay khoảng tin cậy bootstrap. Phần này để sang Task 5.1.
- Chưa so sánh với GCN-B đã tinh chỉnh, vì Task 4.1c chưa được hợp nhất vào repo. Bảng so sánh hiện chỉ có GCN-B ở cấu hình mặc định.
- Nhãn của DiverseVul có nhiễu, theo PrimeVul chỉ khoảng 60% hàm được gán nhãn đúng trong mẫu kiểm tra thủ công. Phần kiểm tra trùng lặp đã chuẩn hóa để sang Task 4.4.
- Các số liệu của task này không so trực tiếp được với các bài báo chia tập ngẫu nhiên và báo accuracy hoặc weighted-F1 trên tập CWE khác.

## 5. Kết luận

Task 4.2 hoàn tất đúng quy ước: 7 cấu hình, 2 protocol, 3 seed, chọn bằng validation, test chỉ chấm sau khi cố định cấu hình.

Kết quả là **âm tính và nhất quán**:

1. Tinh chỉnh một yếu tố không cải thiện Macro-F1 test. L1 (0,0579) thấp hơn GGNN-B mặc định (0,0712) ở project_wise.
2. Phân tích độ nhạy cho thấy nguyên nhân là tiêu chí lựa chọn: tương quan hạng validation-test chỉ 0,36, và cấu hình được chọn đứng thứ 5 trên 7 ở test.
3. GGNN không hơn GCN, Graph B không hơn Graph A, cả hai chênh lệch đều nằm trong độ lệch chuẩn.
4. Mọi cấu hình GNN đều thua baseline token với khoảng cách vượt độ lệch chuẩn, nhưng đều hơn random.

Kết luận này cùng chiều với các nghiên cứu đã đọc: LIVABLE ghi nhận nhánh token đóng góp nhiều hơn nhánh graph, Vul-LMGNNs ghi nhận CodeBERT một mình hơn Devign và ReVeal trên DiverseVul, còn PrimeVul cho thấy điểm số rơi mạnh khi chia tập nghiêm ngặt.

Hướng tiếp theo là Task 4.3, thử hai can thiệp lấy từ bài báo thay vì tiếp tục tinh chỉnh siêu tham số: khởi tạo embedding token bằng CodeBERT, và loss thích nghi kiểu LIVABLE cho các lớp đuôi. Vì cấu hình L1 không hơn mặc định trên test, cần chốt lại mốc để so ở Task 4.3 trước khi chạy.

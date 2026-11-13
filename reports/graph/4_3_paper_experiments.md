# Báo cáo Task 4.3: Thử nghiệm hai ý tưởng từ bài báo trên GGNN và Graph B

Dữ liệu: [DiverseVul 9077 - Processed Graph Data](https://www.kaggle.com/datasets/vtnmai/diversevul-9077-processed-graph-data/data), version 1 (`vtnmai/diversevul-9077-processed-graph-data/versions/1`), theo [Task 4.0](4_0_processed_data.md).
Mã thực nghiệm: commit `793411a7326d4fff5eaaaacc1f4e177788d28455`, cây làm việc sạch.
Notebook nguồn: [4_3_paper_experiments.ipynb](../../notebooks/4_3_paper_experiments.ipynb). Notebook đã thực thi: [bản chạy đầy đủ trên Kaggle](4_3_paper_experiments_run.ipynb).
Kết quả: [ba nhánh](4_3_results/arms/), [bảng và biểu đồ](4_3_results/figures/), [dấu vân tay bảng khởi tạo CodeBERT](4_3_results/token_init/).
Kết quả tham chiếu: [Task 4.1a](4_1a_baselines_gnn.md), [Task 4.1b](4_1b_gcn_tuning.md), [Task 4.2](4_2_ggnn_tuning.md).

## 1. Thiết kế thí nghiệm

Task 4.3 **đo tác động của từng can thiệp**, không phải chọn cấu hình tốt nhất. Vì vậy test được báo cáo cho cả ba nhánh, và không nhánh nào được chọn dựa trên test. Thiết kế được đăng ký trước trong `src/training/paper_experiments.py` và được ghi ra [`experiment_plan.json`](4_3_results/arms/experiment_plan.json) trước khi chạy.

Nền chung của cả ba nhánh là cấu hình **L1** đã cố định ở Task 4.2: GGNN trên Graph B, dim 128, 2 bước lan truyền, dropout 0,2, AdamW lr 1e-3 weight decay 1e-4, batch 32, tối đa 40 epoch, patience 8, dừng sớm theo Macro-F1 validation.

| Nhánh | Can thiệp | Giả thuyết | Nguồn ý tưởng |
| :--- | :--- | :--- | :--- |
| C0 | không | Nhóm đối chứng, huấn luyện lại L1 trong cùng phiên | Task 4.2 |
| P1 | `token_init` | Khởi tạo embedding token bằng CodeBERT cấp ngữ nghĩa mã nguồn mà vocabulary tự học không có | Vul-LMGNNs |
| P2 | `loss: adaptive` | Loss thích nghi nâng F1 của các lớp CWE ít mẫu, nhờ đó nâng Macro-F1 | LIVABLE |

Mỗi nhánh chỉ khác C0 **đúng một yếu tố**, nên chênh lệch quan sát được quy cho yếu tố đó. C0 được huấn luyện lại trong cùng phiên thay vì lấy lại số của Task 4.2, vì kết quả Task 4.2 cho thấy cùng mã và cùng seed vẫn cho kết quả khác nhau giữa hai phiên GPU.

Quy mô: 3 nhánh × 2 protocol × 3 seed (42, 43, 44) = **18 lần huấn luyện**, tổng 60,3 phút trên Tesla T4, đỉnh VRAM 1408 MB.

P2 là **cách diễn giải** mô tả trong LIVABLE, không phải bản cài đặt chính thức: trọng số lớp cân bằng, lớp đầu dùng cross-entropy có label smoothing 0,1, lớp đuôi dùng focal loss với `gamma` tăng dần từ 0 đến 2 theo epoch, ngưỡng đầu/đuôi lấy ở 50% số mẫu train.

## 2. Kết quả

### Tổng hợp ba nhánh

Trung bình ± độ lệch chuẩn theo 3 seed. Các cột weighted-F1, MCC, accuracy là của test `project_wise`.

| Nhánh | val pw | val sp | **test pw** | test sp | wF1 | MCC | Acc | giây/lần |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| C0 đối chứng (L1) | 0,0603 ± 0,0108 | 0,1585 ± 0,0043 | **0,0520 ± 0,0099** | 0,1026 ± 0,0065 | 0,0796 | 0,0178 | 0,0819 | 227 |
| P1 khởi tạo CodeBERT | 0,0637 ± 0,0028 | 0,1676 ± 0,0037 | **0,0532 ± 0,0025** | 0,1188 ± 0,0155 | 0,0939 | 0,0413 | 0,0994 | 179 |
| P2 loss thích nghi | 0,0668 ± 0,0167 | 0,1475 ± 0,0005 | **0,0532 ± 0,0097** | 0,1045 ± 0,0009 | 0,0948 | 0,0296 | 0,1015 | 197 |

Macro-F1 test `project_wise` của P1 và P2 chỉ bằng nhau khi làm tròn: giá trị thật là 0,053244 và 0,053171.

### Tác động so với nhóm đối chứng

Quy tắc đọc: chênh lệch nhỏ hơn độ lệch chuẩn seed lớn hơn trong hai nhánh được coi là nằm trong nhiễu.

| Protocol | Nhánh | Macro-F1 test | C0 | Δ | Độ lệch chuẩn lớn hơn | Kết luận |
| :--- | :--- | ---: | ---: | ---: | ---: | :--- |
| project_wise | P1 | 0,0532 | 0,0520 | +0,0012 | 0,0099 | trong độ lệch chuẩn |
| project_wise | P2 | 0,0532 | 0,0520 | +0,0012 | 0,0099 | trong độ lệch chuẩn |
| seen_project | P1 | 0,1188 | 0,1026 | +0,0162 | 0,0155 | cao hơn C0 |
| seen_project | P2 | 0,1045 | 0,1026 | +0,0019 | 0,0065 | trong độ lệch chuẩn |

Macro-F1 test từng seed:

| Nhánh | project_wise | seen_project |
| :--- | :--- | :--- |
| C0 | 0,0524 / 0,0397 / 0,0639 | 0,0943 / 0,1101 / 0,1033 |
| P1 | 0,0499 / 0,0539 / 0,0559 | 0,1025 / 0,1141 / 0,1396 |
| P2 | 0,0415 / 0,0526 / 0,0654 | 0,1033 / 0,1055 / 0,1047 |

Trên `seen_project`, mức tăng của P1 chủ yếu đến từ một seed (0,1396), và Δ = 0,0162 chỉ vừa vượt độ lệch chuẩn 0,0155. Đây là tín hiệu yếu, không phải kết luận chắc chắn.

### Kiểm chứng trực tiếp giả thuyết của P2

P2 được thiết kế để nâng F1 của các lớp CWE ít mẫu. Bảng dưới chia 23 CWE theo số mẫu test `project_wise` và lấy F1 trung bình trong mỗi nhóm.

| Nhóm | Số CWE | C0 | P1 | P2 |
| :--- | ---: | ---: | ---: | ---: |
| đầu (≥50 mẫu) | 7 | 0,0904 | 0,1108 | 0,1107 |
| giữa (16-49 mẫu) | 5 | 0,0357 | 0,0379 | 0,0350 |
| **đuôi (≤15 mẫu)** | 11 | **0,0350** | **0,0236** | **0,0248** |

**Giả thuyết của P2 bị bác bỏ**: F1 nhóm đuôi giảm từ 0,0350 xuống 0,0248, trong khi nhóm đầu tăng. P1 cũng cho đúng một dạng chuyển dịch như vậy. Cả hai can thiệp đều **dồn năng lực dự đoán về các lớp nhiều mẫu**, nên weighted-F1 và accuracy tăng rõ (0,0796 → 0,0939 và 0,0948; 0,0819 → 0,0994 và 0,1015) nhưng Macro-F1 gần như không đổi, vì Macro-F1 tính đều 23 lớp.

Số CWE có F1 test bằng 0 giữ nguyên 5 trên 23 ở cả ba nhánh.

Chi tiết từng CWE trên test `project_wise` (trung bình 3 seed, sắp theo số mẫu giảm dần):

| CWE | Mẫu | C0 | P1 | P2 |
| :--- | ---: | ---: | ---: | ---: |
| CWE-476 | 125 | 0,090 | 0,129 | 0,095 |
| CWE-787 | 122 | 0,137 | 0,140 | 0,197 |
| CWE-119 | 109 | 0,077 | 0,048 | 0,124 |
| CWE-20 | 94 | 0,075 | 0,057 | 0,106 |
| CWE-190 | 92 | 0,134 | 0,253 | 0,129 |
| CWE-125 | 87 | 0,095 | 0,130 | 0,068 |
| CWE-399 | 57 | 0,025 | 0,018 | 0,056 |
| CWE-703 | 46 | 0,006 | 0,030 | 0,073 |
| CWE-416 | 32 | 0,070 | 0,101 | 0,016 |
| CWE-200 | 30 | 0,014 | 0,000 | 0,007 |
| CWE-189 | 27 | 0,060 | 0,033 | 0,059 |
| CWE-120 | 24 | 0,028 | 0,025 | 0,021 |
| CWE-369 | 13 | 0,083 | 0,026 | 0,017 |
| CWE-415 | 13 | 0,055 | 0,014 | 0,000 |
| CWE-617 | 10 | 0,005 | 0,000 | 0,000 |
| CWE-835 | 10 | 0,000 | 0,028 | 0,000 |
| CWE-295 | 9 | 0,083 | 0,016 | 0,039 |
| CWE-59 | 9 | 0,000 | 0,056 | 0,013 |
| CWE-22 | 8 | 0,137 | 0,104 | 0,158 |
| CWE-264 | 6 | 0,022 | 0,000 | 0,014 |
| CWE-400 | 5 | 0,000 | 0,000 | 0,032 |
| CWE-401 | 4 | 0,000 | 0,000 | 0,000 |
| CWE-770 | 4 | 0,000 | 0,016 | 0,000 |

### Bảng khởi tạo CodeBERT

Bảng khởi tạo được xuất riêng cho từng protocol vì vocabulary khác nhau: `project_wise` 25.151 token, `seen_project` 25.750 token. Hai file có sha256 khác nhau và log huấn luyện xác nhận mỗi protocol nạp đúng ma trận của nó.

Kiểm tra láng giềng gần nhất theo cosine trong không gian khởi tạo cho thấy quan hệ thu được **nghiêng về hình thái chuỗi ký tự hơn là ngữ nghĩa**:

```
malloc -> malloc64, malloc0, mallocs, malloced, xmalloc
free   -> tofree, firstfree, freegap, lastfree, freeblocks
if     -> ififo, notif, findif, ifelse, elseif
len    -> lenlen (1.00), linlen, bodylen, doclen, litlen
```

Đây là hệ quả của cách xuất: token của ta được tách thành sub-token rồi lấy trung bình embedding tĩnh của CodeBERT, không chạy qua các lớp transformer có ngữ cảnh. Vì vậy P1 trong báo cáo này chỉ là **một phiên bản rút gọn** của ý tưởng Vul-LMGNNs, không phải bản đầy đủ.

### Đường học và chi phí

| Nhánh | Protocol | Epoch tốt nhất | Epoch đã chạy | Tổng giây |
| :--- | :--- | :--- | :--- | ---: |
| C0 | project_wise | 27 / 6 / 25 | 35 / 14 / 33 | 588 |
| C0 | seen_project | 22 / 24 / 32 | 30 / 32 / 40 | 772 |
| P1 | project_wise | 9 / 6 / 14 | 17 / 14 / 22 | 379 |
| P1 | seen_project | 25 / 21 / 22 | 33 / 29 / 30 | 696 |
| P2 | project_wise | 5 / 18 / 18 | 13 / 26 / 26 | 474 |
| P2 | seen_project | 20 / 28 / 20 | 28 / 36 / 28 | 710 |

P1 đạt điểm validation tốt nhất **sớm hơn hẳn** trên `project_wise`: epoch 9/6/14 so với 27/6/25 của C0, nên tiết kiệm khoảng một phần ba thời gian. Khởi tạo có sẵn giúp mô hình hội tụ nhanh hơn, nhưng không đưa nó tới điểm tốt hơn.

Cả ba nhánh vẫn giữ dấu hiệu học thuộc sớm đã thấy ở Task 4.1a và 4.2: train loss giảm đều về dưới 0,5 trong khi Macro-F1 validation dao động quanh mức thấp.

### Đặt cạnh các task trước

| Mốc | project_wise | seen_project |
| :--- | :--- | :--- |
| token_nodes (4.1a) | 0,1000 | 0,1541 |
| token_method (4.1a) | 0,0875 | 0,1701 |
| random (4.1a) | 0,0393 ± 0,0039 | 0,0383 ± 0,0033 |
| GGNN-B mặc định (4.1a) | 0,0712 ± 0,0049 | 0,0977 ± 0,0047 |
| GGNN-B tinh chỉnh L1 (4.2) | 0,0579 ± 0,0106 | 0,0930 ± 0,0130 |
| C0 đối chứng (4.3) | 0,0520 ± 0,0099 | 0,1026 ± 0,0065 |
| P1 khởi tạo CodeBERT (4.3) | 0,0532 ± 0,0025 | 0,1188 ± 0,0155 |
| P2 loss thích nghi (4.3) | 0,0532 ± 0,0097 | 0,1045 ± 0,0009 |

**Hai baseline đếm token của Task 4.1a vẫn cao hơn mọi nhánh GNN**, kể cả sau hai can thiệp theo bài báo. Đây là kết quả quan trọng nhất của toàn bộ Phase 4 cho tới nay.

## 3. Đánh giá so với yêu cầu

Chạy thực tế khớp với thiết kế đã đăng ký. Hàm `validate_arm` được chạy lại trên cả ba thư mục kết quả và cả ba đều hợp lệ:

- C0: `loss=weighted_ce`, 2 lớp, dim 128, dropout 0,2, wd 1e-4, dừng sớm theo macro_f1, không khởi tạo CodeBERT.
- P1: giống C0, chỉ bật khởi tạo CodeBERT.
- P2: giống C0, chỉ đổi `loss=adaptive`.
- Cả ba: commit `793411a7326d`, cây sạch, đúng dataset version 1, đủ 2 protocol × 3 seed.

Mỗi nhánh chỉ lệch C0 một yếu tố, test được báo cáo cho cả ba nhánh, nhóm đối chứng chạy cùng phiên. Không có bước nào chọn nhánh theo test.

## 4. Điểm bất thường và cách xử lý

1. **Tiêu đề `summary.md` của ba nhánh ghi nhầm "Task 4.1a"**. Nguyên nhân: tiêu đề chỉ được sinh động khi chạy ở chế độ `--validation-only` hoặc `--frozen-selection`, còn ba nhánh của 4.3 chạy ở chế độ thường nên rơi vào nhánh mặc định. Đây là lỗi nhãn, không ảnh hưởng số liệu. Đã sửa trong commit của task này: tiêu đề luôn sinh theo mô hình, graph và `config_id`. Các file `summary.md` trong `4_3_results/` giữ nguyên như lúc chạy.
2. **P1 và P2 cùng cho 0,0532 trên test `project_wise`**. Đã kiểm tra số từng seed: hai giá trị thật là 0,053244 và 0,053171, chỉ trùng nhau khi làm tròn bốn chữ số. Không phải lỗi sao chép kết quả.
3. **Độ lệch chuẩn của P2 trên `seen_project` rất nhỏ (0,0009)** trong khi C0 là 0,0065. Ba seed cho 0,1033 / 0,1055 / 0,1047. Loss thích nghi có vẻ đưa mô hình về cùng một lời giải bất kể seed, nhưng với 3 seed thì chưa đủ cơ sở để khẳng định.
4. **Nhiễu seed vẫn lớn hơn mọi tác động đo được** trên `project_wise`: khoảng dao động của C0 là 0,0397 đến 0,0639, rộng hơn nhiều so với Δ = 0,0012. Điều này lặp lại phát hiện ở Task 4.2 về tính không tất định của GPU.

## 5. Giới hạn

- Ba seed cho mỗi ô là quá ít để kiểm định thống kê. Các kết luận ở đây là so sánh mô tả, không phải kiểm định giả thuyết.
- P1 chỉ dùng embedding tĩnh của CodeBERT, không dùng biểu diễn có ngữ cảnh, nên không đại diện cho Vul-LMGNNs đầy đủ.
- P2 là cách diễn giải LIVABLE theo mô tả trong bài báo, các tham số `gamma` 2,0, smoothing 0,1 và ngưỡng đầu/đuôi 50% không được tinh chỉnh.
- Nền chung là L1 của Task 4.2. Nếu đổi nền sang B0 thì tác động của hai can thiệp có thể khác.
- Chỉ thử trên GGNN và Graph B, chưa thử trên GCN hoặc Graph A.

## 6. Kết luận

1. Trên protocol chính `project_wise`, **cả hai can thiệp đều không cải thiện Macro-F1** so với nhóm đối chứng. Δ = 0,0012 nằm sâu trong nhiễu seed 0,0099.
2. Trên `seen_project`, P1 cho tín hiệu dương yếu (Δ = 0,0162 so với độ lệch chuẩn 0,0155), P2 thì không.
3. **Giả thuyết của P2 bị bác bỏ bằng chính dữ liệu của nó**: loss thích nghi làm F1 nhóm CWE ít mẫu giảm từ 0,0350 xuống 0,0248.
4. Cả hai can thiệp đều chuyển năng lực dự đoán về các lớp nhiều mẫu, nâng weighted-F1 và accuracy nhưng không nâng Macro-F1.
5. P1 có một lợi ích thực tế là hội tụ nhanh hơn khoảng một phần ba trên `project_wise`.
6. Hai baseline đếm token đơn giản vẫn vượt mọi biến thể GNN đã thử. Kết hợp với Task 4.1b và 4.2, bằng chứng tích lũy cho thấy **nút thắt không nằm ở kiến trúc hay loss mà nằm ở biểu diễn node và quy mô dữ liệu cho bài toán 23 lớp**. Task 4.4 và 4.5 nhắm đúng vào hai điểm này.

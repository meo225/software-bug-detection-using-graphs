# Báo cáo Task 4.5: Baseline mô hình text pretrained trên văn bản hàm

Dữ liệu: [DiverseVul 7799 Function Text](https://www.kaggle.com/datasets/vtnmai/diversevul-7799-function-text), dựng bằng `scripts/build_text_dataset.py` từ jsonl DiverseVul gốc, manifest split của [Task 2.3](../../docs/2_3_split.md) và danh sách mẫu lỗi của [Task 3.3](3_3_extraction.md).
Mã thực nghiệm: commit `b18dfa31cff1`, cây làm việc sạch.
Notebook nguồn: [4_5_text_baseline.ipynb](../../notebooks/4_5_text_baseline.ipynb). Notebook đã thực thi: [bản chạy đầy đủ trên Kaggle](4_5_text_baseline_run.ipynb).
Kết quả: [thư mục chạy](4_5_results/runs/codebert/), [bảng và biểu đồ](4_5_results/figures/).
Kết quả tham chiếu: [4.1a](4_1a_baselines_gnn.md), [4.1b và 4.1c](4_1b_gcn_tuning.md), [4.2](4_2_ggnn_tuning.md), [4.3](4_3_paper_experiments.md).

## 1. Thiết kế

Task 4.5 là một **baseline**, không phải bài toán chọn cấu hình như 4.1b với 4.2, cũng không phải bài toán đo tác động như 4.3. Cấu hình được chốt một lần từ bài báo trong `src/training/text_experiments.py` trước khi chạy, chạy đủ hai protocol với ba seed, và test được báo cáo cho đúng cấu hình đó. Không dò siêu tham số, vì câu hỏi là "mô hình text pretrained mạnh tới đâu trên split của nhóm", không phải "cấu hình text nào tốt nhất".

| Lựa chọn | Giá trị | Nguồn |
| :--- | :--- | :--- |
| Model | CodeBERT base, 124,7 triệu tham số | Bài 1 báo CodeBERT tốt nhất trong ba model họ thử |
| Cắt đoạn | 2 đoạn × 512 token, max-pooling | EMNLP 2024, bài 1 |
| Learning rate, số epoch | 2e-5, tối đa 10 | PrimeVul, bài 3 |
| Loss | class-weighted cross-entropy | Quy ước Task 4.1a |
| Seed, protocol, nhãn | 42 43 44, hai protocol, 23 CWE | Quy ước Task 4.1a |

Batch size 8, warmup tuyến tính 10%, weight decay 0,01 không áp lên bias với LayerNorm, gradient clipping 1,0, dừng sớm theo Macro-F1 validation với patience 3. **Những giá trị này là thông lệ fine-tune transformer, không trích từ bài báo nào.** Bài 1 không công bố learning rate, batch size hay optimizer.

Dữ liệu khác mọi task trước: mô hình text cần mã nguồn gốc, mà Kaggle Dataset của Task 4.0 chỉ chứa id token theo vocabulary tự học. Tập văn bản được dựng riêng và script dừng hẳn nếu số mẫu từng split lệch khỏi 4.0. Lần chạy này báo `split_size_problems` rỗng, tức **trùng đúng 7.799 mẫu mà mọi model graph đã dùng**.

## 2. Ngân sách token: giới hạn lớn nhất của baseline này

Đây là số phải đọc trước mọi kết quả khác.

| | |
| :--- | ---: |
| Độ dài hàm trung vị | **673 token** |
| p90 | 3.805 |
| p99 | 17.032 |
| Dài nhất | 77.521 |
| Hàm cần nhiều hơn một đoạn | **58,4%** |
| Hàm bị cắt bỏ một phần ở 2 đoạn | **38,0%** |
| **Tỷ lệ token mô hình thực sự đọc** | **37,4%** |

**Ngay cả hàm trung vị cũng không vừa một đoạn 510 token.** Hàm C trong DiverseVul dài hơn nhiều so với giả định của các code model 512 token.

Hệ quả cho việc so sánh: baseline token của Task 4.1a đọc toàn bộ hàm, còn CodeBERT ở đây chỉ đọc 37,4% lượng token. Hai bên **không ở cùng điều kiện**, và điều này phải được nhớ ở mọi so sánh bên dưới.

Nếu tăng lên 4 đoạn thì tỷ lệ bị cắt giảm còn 20,8% và độ phủ token lên 54,1%, đổi lại chi phí tăng khoảng 1,4 lần.

## 3. Kết quả

Trung bình ± độ lệch chuẩn tổng thể theo ba seed, `ddof = 0`, tính từ CSV chưa làm tròn.

| Split | project_wise | seen_project |
| :--- | ---: | ---: |
| validation | 0,0677 ± 0,0105 | 0,1868 ± 0,0095 |
| **test** | **0,0813 ± 0,0269** | **0,1458 ± 0,0153** |

Macro-F1 test từng seed:

| Protocol | seed 42 | seed 43 | seed 44 |
| :--- | ---: | ---: | ---: |
| project_wise | 0,1060 | 0,0940 | **0,0439** |
| seen_project | 0,1398 | 0,1668 | 0,1309 |

Các chỉ số khác trên test `project_wise`: weighted-F1 0,1316, MCC 0,0690, accuracy 0,1578. Cả ba đều **cao hơn hẳn** mọi biến thể GNN, nơi weighted-F1 chưa bao giờ vượt 0,11 và MCC chưa bao giờ vượt 0,042.

Chi phí: 3,46 giờ GPU trên Tesla T4 cho 6 lần huấn luyện, đỉnh VRAM 4.907 MB. Để so sánh, 18 lần chạy GGNN của Task 4.3 chỉ mất 1,0 giờ và 1,4 GB.

## 4. Đặt cạnh mọi mốc của Phase 4

Quy tắc đọc giống Task 4.3: chênh lệch nhỏ hơn độ lệch chuẩn lớn hơn trong hai bên được coi là nằm trong nhiễu.

| Mốc | pw | Δ | Kết luận pw | sp | Δ | Kết luận sp |
| :--- | ---: | ---: | :--- | ---: | ---: | :--- |
| token_method (4.1a) | 0,0875 | −0,0062 | trong nhiễu | 0,1701 | −0,0243 | **thấp hơn** |
| token_nodes (4.1a) | 0,1000 | −0,0187 | trong nhiễu | 0,1541 | −0,0083 | trong nhiễu |
| GGNN-B mặc định (4.1a) | 0,0712 | +0,0101 | trong nhiễu | 0,0977 | +0,0481 | **cao hơn** |
| GCN-B tinh chỉnh (4.1c) | 0,0650 | +0,0163 | trong nhiễu | 0,1026 | +0,0432 | **cao hơn** |
| P1 khởi tạo CodeBERT (4.3) | 0,0532 | +0,0281 | **cao hơn** | 0,1188 | +0,0270 | **cao hơn** |
| C0 đối chứng (4.3) | 0,0520 | +0,0293 | **cao hơn** | 0,1026 | +0,0432 | **cao hơn** |
| **CodeBERT fine-tune (4.5)** | **0,0813** | | | **0,1458** | | |

Hai bức tranh khác hẳn nhau:

**Trên `seen_project` kết quả sạch.** CodeBERT cao hơn mọi biến thể GNN với khoảng cách vượt độ lệch chuẩn, và thấp hơn `token_method` cũng với khoảng cách vượt độ lệch chuẩn. Thứ tự rõ ràng: baseline token > mô hình text pretrained > mọi GNN.

**Trên `project_wise` không kết luận được gì chắc chắn.** Trung bình của CodeBERT là cao nhất trong nhóm mô hình học được, nhưng độ lệch chuẩn 0,0269 nuốt trọn mọi khoảng cách. Chỉ tách được khỏi hai nhánh yếu nhất của Task 4.3. Nguyên nhân là seed 44, mục 6 phân tích riêng.

So với Task 4.3, kết quả này có ý nghĩa riêng: ở 4.3, **khởi tạo** embedding token bằng CodeBERT cho P1 chỉ 0,0532, trong khi **fine-tune** cả CodeBERT ở đây cho 0,0813. Cùng một mô hình nguồn, chênh lệch đến từ việc dùng nó như bảng tra cứu tĩnh hay như một bộ mã hóa có ngữ cảnh.

## 5. Phân bố theo lớp

F1 trung bình ba seed trên test `project_wise`, chia nhóm theo số mẫu test giống Task 4.3:

| Nhóm lớp | Số CWE | C0 đối chứng (4.3) | CodeBERT (4.5) | Δ |
| :--- | ---: | ---: | ---: | ---: |
| đầu (≥50 mẫu) | 7 | 0,0904 | **0,1507** | +0,0603 |
| giữa (16-49 mẫu) | 5 | 0,0357 | 0,0370 | +0,0013 |
| đuôi (≤15 mẫu) | 11 | 0,0350 | 0,0572 | +0,0222 |

Nhìn bảng thì CodeBERT hơn ở cả ba nhóm. **Nhưng con số nhóm đuôi gây hiểu nhầm.** Trong 11 CWE của nhóm đuôi, CodeBERT chỉ ghi điểm ở ba lớp, và hai lớp trong đó chiếm 91% giá trị trung bình của cả nhóm:

| CWE | Mẫu test | C0 | CodeBERT |
| :--- | ---: | ---: | ---: |
| CWE-59 Link Following | 9 | 0,000 | **0,344** |
| CWE-22 Path Traversal | 8 | 0,137 | **0,228** |
| CWE-295 Certificate Validation | 9 | 0,083 | 0,057 |
| 8 CWE đuôi còn lại | 4 đến 13 | 0,000 đến 0,083 | **0,000** |

Đây là quan sát đáng chú ý nhất về mặt định tính của cả Phase 4. CWE-59 và CWE-22 là hai lớp có **dấu hiệu từ vựng rất đặc trưng** trong mã nguồn: `symlink`, `readlink`, `realpath`, chuỗi đường dẫn, `../`. Mô hình text bắt được, còn graph thì không, vì Task 4.0 đã hạ chữ thường và thay chuỗi ký tự bằng `<STR>` nên chính dấu hiệu đó bị xóa trước khi vào mô hình.

Ở nhóm đầu, CodeBERT hơn đều và rõ: CWE-476 từ 0,090 lên 0,216, CWE-119 từ 0,077 lên 0,187, CWE-190 từ 0,134 lên 0,224.

Số CWE có F1 test bằng 0 là **11, 11 và 16 trên 23** theo từng seed, so với 5 của các nhánh GNN ở Task 4.3. CodeBERT bỏ hẳn nhiều lớp hơn nhưng giỏi hơn nhiều trên số lớp nó chịu dự đoán. Đó cũng là lý do weighted-F1 và accuracy tăng mạnh hơn Macro-F1.

## 6. Điểm bất thường

### 6.1. Seed 44 trên project_wise không học được

Macro-F1 validation qua từng epoch: 0,0528 → 0,0470 → 0,0525 → 0,0484. **Không epoch nào vượt được epoch 1**, nên dừng sớm với patience 3 cắt ở epoch 4 và điểm test 0,0439 là của một mô hình huấn luyện đúng một epoch. Hai seed kia đạt validation 0,0746 và 0,0756 ở epoch 4 với 5.

Đây **không phải lỗi của cơ chế dừng sớm**. Train loss của seed 44 vẫn giảm bình thường từ 3,07 xuống 1,22, tức mô hình vẫn học thuộc tập train. Cả đường validation của nó nằm bẹt quanh 0,05 trong suốt bốn epoch. Seed này học kém thật, không phải dừng nhầm chỗ.

Một mình seed 44 tạo ra gần như toàn bộ độ lệch chuẩn 0,0269. Bỏ nó ra thì hai seed còn lại cho 0,1060 và 0,0940, tức là vượt cả `token_nodes`. Nhưng **không được phép bỏ**, vì như vậy là chọn seed theo test.

Trên `seen_project` thì cả ba seed đều ổn định, cùng đi lên trơn tru tới 0,17 đến 0,195. Bất ổn chỉ xuất hiện ở protocol khó hơn.

### 6.2. Học thuộc rất nhanh

Train loss từ 3,07 xuống 0,24 trong 8 epoch, trong khi Macro-F1 validation ngừng tăng từ epoch 4 đến 5. Cùng bệnh đã thấy ở Task 4.1a, 4.2 và 4.3, nhưng diễn ra nhanh hơn hẳn vì mô hình có 124,7 triệu tham số trên 6.101 mẫu train.

### 6.3. Hai lỗi trình bày của notebook, đã sửa

- Ô tổng hợp dùng `std` mặc định của pandas là `ddof = 1`, ra 0,0329, trong khi mọi bảng khác của đồ án dùng `ddof = 0`. Số đi vào báo cáo này là **0,0269**, lấy từ ô so sánh vốn đã dùng đúng quy ước. Notebook đã sửa.
- Biểu đồ đường học vẽ train loss thang 0 đến 3 chung trục với Macro-F1 thang 0 đến 0,2, nên đường Macro-F1 bẹt sát đáy. Notebook đã chuyển sang trục kép, và [hình trong thư mục kết quả](4_5_results/figures/learning_curves.png) được vẽ lại từ chính `learning_curves.csv` của lần chạy, không đổi dữ liệu.

## 7. Đánh giá so với yêu cầu

`validate_run` chạy lại trên thư mục kết quả: **đạt**. Cụ thể:

- Đúng model `codebert`, đủ ba seed 42 43 44, đủ hai protocol, không phải lần chạy rút gọn.
- Cả 11 siêu tham số khớp tuyệt đối với `text_experiments.BASELINE` đã đăng ký.
- Commit `b18dfa31cff1`, cây sạch, dataset `diversevul-7799-function-text`, 7.799 mẫu, `split_size_problems` rỗng.
- Đủ 12 dòng kết quả cho validation với test.

Không có bước nào chọn cấu hình hay chọn epoch theo test.

## 8. Giới hạn

- **Chỉ đọc 37,4% lượng token.** Đây là giới hạn nặng nhất. So sánh với baseline token, vốn đọc toàn bộ hàm, vì thế không hoàn toàn công bằng.
- **Ba seed là quá ít**, nhất là khi một trong ba hỏng. Mọi kết luận ở `project_wise` chỉ là mô tả, không phải kiểm định.
- Chỉ thử CodeBERT, chưa thử UniXcoder.
- Siêu tham số không được dò. Có thể một learning rate thấp hơn hoặc warmup dài hơn sẽ cứu được seed 44, nhưng dò sẽ phá vỡ tính chất baseline đăng ký trước của task này.
- Số của task này không so trực tiếp được với bài báo EMNLP 2024: họ dùng Big-Vul, chia ngẫu nhiên, và báo accuracy với weighted-F1 chứ không phải Macro-F1.

## 9. Kết luận

1. **Mô hình text pretrained là mô hình học được mạnh nhất trong toàn bộ Phase 4.** Trên `seen_project`, CodeBERT đạt 0,1458, cao hơn mọi biến thể GNN với khoảng cách vượt độ lệch chuẩn. Trên `project_wise`, trung bình 0,0813 cũng cao nhất, nhưng độ lệch chuẩn quá lớn để khẳng định.
2. **Baseline đếm token vẫn chưa bị vượt.** `token_method` đạt 0,1701 trên `seen_project`, cao hơn CodeBERT với khoảng cách vượt độ lệch chuẩn. Trên `project_wise`, `token_nodes` đạt 0,1000 so với 0,0813, nhưng chênh lệch nằm trong nhiễu.
3. **Nút thắt là biểu diễn đầu vào, không phải kiến trúc mô hình.** Chuỗi bằng chứng đã khép lại: tinh chỉnh siêu tham số không giúp (4.1b, 4.2), đổi kiến trúc không giúp (4.2), thêm cạnh ngữ nghĩa không giúp ổn định (4.1c), hai can thiệp từ bài báo không giúp (4.3). Nhưng **đổi hẳn cách biểu diễn đầu vào từ graph sang văn bản thì cải thiện rõ rệt**, nâng Macro-F1 `seen_project` từ 0,1026 lên 0,1458 và weighted-F1 `project_wise` từ 0,0796 lên 0,1316.
4. **Bằng chứng định tính mạnh nhất nằm ở CWE-59 và CWE-22.** Hai lớp này có dấu hiệu từ vựng rõ trong mã nguồn, và chính hai lớp này mô hình text ghi điểm còn graph thì bằng không. Nó chỉ thẳng vào chỗ mất mát: Task 4.0 hạ chữ thường và thay chuỗi ký tự bằng `<STR>`, xóa mất đúng loại tín hiệu đó.
5. **Hai việc cần làm tiếp để kết luận đứng vững.** Một là chạy lại với 4 đoạn để tách câu hỏi "thua vì bản chất hay thua vì bị cắt mất 63% token", ước tính 4,8 giờ GPU. Hai là Task 5.1 cần xử lý tình trạng bất ổn theo seed, bằng khoảng tin cậy bootstrap thay vì chỉ độ lệch chuẩn của ba seed.

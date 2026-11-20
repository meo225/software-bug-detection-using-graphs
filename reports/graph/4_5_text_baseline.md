# Báo cáo Task 4.5: Baseline mô hình text pretrained trên văn bản hàm

Dữ liệu: [DiverseVul 7799 Function Text](https://www.kaggle.com/datasets/vtnmai/diversevul-7799-function-text), dựng bằng `scripts/build_text_dataset.py` từ jsonl DiverseVul gốc, manifest split của [Task 2.3](../../docs/2_3_split.md) và danh sách mẫu lỗi của [Task 3.3](3_3_extraction.md).
Mã thực nghiệm: commit `b18dfa31cff1` cho lần chạy đã đăng ký, `158e02e3bbfe` cho lần chạy độ nhạy. Cả hai cây làm việc đều sạch.
Notebook nguồn: [4_5_text_baseline.ipynb](../../notebooks/4_5_text_baseline.ipynb). Notebook đã thực thi: [bản chạy đầy đủ trên Kaggle](4_5_text_baseline_run.ipynb).
Kết quả: [2 đoạn](4_5_results/runs/codebert/), [4 đoạn](4_5_results/runs/codebert_chunks4/), [bảng và biểu đồ](4_5_results/figures/).
Kết quả tham chiếu: [4.1a](4_1a_baselines_gnn.md), [4.1b và 4.1c](4_1b_gcn_tuning.md), [4.2](4_2_ggnn_tuning.md), [4.3](4_3_paper_experiments.md).

## 1. Thiết kế

Task 4.5 là một **baseline**, không phải bài toán chọn cấu hình như 4.1b với 4.2, cũng không phải bài toán đo tác động như 4.3. Cấu hình được chốt một lần từ bài báo trong `src/training/text_experiments.py` trước khi chạy, chạy đủ hai protocol với ba seed, và test được báo cáo cho đúng cấu hình đó.

| Lựa chọn | Giá trị | Nguồn |
| :--- | :--- | :--- |
| Model | CodeBERT base, 124,7 triệu tham số | Bài 1 báo CodeBERT tốt nhất trong ba model họ thử |
| Cắt đoạn | 2 đoạn × 512 token, max-pooling | EMNLP 2024, bài 1 |
| Learning rate, số epoch | 2e-5, tối đa 10 | PrimeVul, bài 3 |
| Loss | class-weighted cross-entropy | Quy ước Task 4.1a |
| Seed, protocol, nhãn | 42 43 44, hai protocol, 23 CWE | Quy ước Task 4.1a |

Batch size 8, warmup tuyến tính 10%, weight decay 0,01 không áp lên bias với LayerNorm, gradient clipping 1,0, dừng sớm theo Macro-F1 validation với patience 3. **Những giá trị này là thông lệ fine-tune transformer, không trích từ bài báo nào.** Bài 1 không công bố learning rate, batch size hay optimizer.

Sau khi có kết quả của cấu hình đã đăng ký, một **lần chạy độ nhạy theo ngân sách đoạn** được thêm vào, nâng `max_chunks` từ 2 lên 4 và giữ nguyên mọi thứ khác. Quyết định chạy nó được đặt ra **trước** khi nhìn kết quả: nếu CodeBERT thua baseline token thì bắt buộc phải tách câu hỏi "thua vì bản chất hay thua vì bị cắt mất token". Lần chạy này đổi đúng một yếu tố nên quy cho yếu tố đó được.

Dữ liệu khác mọi task trước: mô hình text cần mã nguồn gốc, mà Kaggle Dataset của Task 4.0 chỉ chứa id token theo vocabulary tự học. Tập văn bản được dựng riêng, và cả hai lần chạy đều báo `split_size_problems` rỗng, tức **trùng đúng 7.799 mẫu mà mọi model graph đã dùng**.

## 2. Ngân sách token

Đây là số phải đọc trước mọi kết quả khác.

| | |
| :--- | ---: |
| Độ dài hàm trung vị | **673 token** |
| p90 | 3.805 |
| p99 | 17.032 |
| Dài nhất | 77.521 |
| Hàm cần nhiều hơn một đoạn | **58,4%** |

**Ngay cả hàm trung vị cũng không vừa một đoạn 510 token.** Hàm C trong DiverseVul dài hơn nhiều so với giả định của các code model 512 token.

| Ngân sách | Sức chứa | Hàm bị cắt | Token mô hình đọc được |
| :--- | ---: | ---: | ---: |
| 1 đoạn | 510 | 58,4% | 23,4% |
| **2 đoạn, bản đăng ký** | 1.020 | 38,0% | **37,4%** |
| **4 đoạn, độ nhạy** | 2.040 | 20,8% | **54,1%** |

Baseline token của Task 4.1a đọc toàn bộ hàm. Vì thế mọi so sánh với nó phải nhớ rằng CodeBERT bị bịt mất một phần đầu vào.

## 3. Kết quả

Trung bình ± độ lệch chuẩn tổng thể theo ba seed, `ddof = 0`, tính từ CSV chưa làm tròn.

| | 2 đoạn (đã đăng ký) | 4 đoạn (độ nhạy) |
| :--- | ---: | ---: |
| validation project_wise | 0,0677 ± 0,0105 | 0,0709 ± 0,0108 |
| validation seen_project | 0,1868 ± 0,0095 | 0,2037 ± 0,0067 |
| **test project_wise** | **0,0813 ± 0,0269** | **0,1008 ± 0,0042** |
| **test seen_project** | **0,1458 ± 0,0153** | **0,1358 ± 0,0038** |

Macro-F1 test từng seed:

| Protocol | Ngân sách | seed 42 | seed 43 | seed 44 |
| :--- | :--- | ---: | ---: | ---: |
| project_wise | 2 đoạn | 0,1060 | 0,0940 | **0,0439** |
| project_wise | 4 đoạn | 0,1052 | 0,0951 | **0,1022** |
| seen_project | 2 đoạn | 0,1398 | 0,1668 | 0,1309 |
| seen_project | 4 đoạn | 0,1349 | 0,1409 | 0,1318 |

Các chỉ số khác trên test `project_wise`:

| | 2 đoạn | 4 đoạn | GNN tốt nhất trong cả Phase 4 |
| :--- | ---: | ---: | ---: |
| weighted-F1 | 0,1316 | **0,1637** | 0,1099 |
| MCC | 0,0690 | **0,0930** | 0,0413 |
| accuracy | 0,1578 | **0,1788** | 0,1129 |

Chi phí: 3,46 giờ GPU và đỉnh VRAM 4,9 GB cho 2 đoạn; 5,21 giờ và 8,2 GB cho 4 đoạn. Để so sánh, 18 lần chạy GGNN của Task 4.3 chỉ mất 1,0 giờ và 1,4 GB.

### Tác động của ngân sách đoạn

Trên `project_wise`, trung bình tăng 0,0195 và **độ lệch chuẩn co lại 6,4 lần**, từ 0,0269 xuống 0,0042. Theo đúng quy tắc so Δ với độ lệch chuẩn lớn hơn thì mức tăng trung bình vẫn nằm trong nhiễu của chính lần chạy 2 đoạn. **Bằng chứng mạnh hơn nằm ở phương sai**, không ở trung bình: ba seed của bản 4 đoạn cho 0,1052, 0,0951 và 0,1022, một dải rộng 0,0101, so với dải 0,0621 của bản 2 đoạn.

Trên `seen_project`, trung bình giảm 0,0100, nằm trong độ lệch chuẩn 0,0153 của bản 2 đoạn, và phương sai cũng co lại tương tự. Thêm ngữ cảnh **không giúp** ở protocol dễ hơn.

Hai chiều trái ngược này hợp lý: `seen_project` cho phép project lặp lại giữa các split nên mô hình có thể dựa vào đặc trưng riêng của project, thứ xuất hiện ngay ở đầu hàm. `project_wise` buộc phải tổng quát sang mã nguồn chưa từng thấy, và ở đó phần thân hàm bị cắt mới thực sự có giá trị.

## 4. Đặt cạnh mọi mốc của Phase 4

Quy tắc đọc giống Task 4.3: chênh lệch nhỏ hơn độ lệch chuẩn lớn hơn trong hai bên được coi là nằm trong nhiễu. Bảng dưới so với bản **4 đoạn**, độ lệch chuẩn 0,0042 trên `project_wise` và 0,0038 trên `seen_project`.

| Mốc | pw | Δ | Kết luận pw | sp | Δ | Kết luận sp |
| :--- | ---: | ---: | :--- | ---: | ---: | :--- |
| token_method (4.1a) | 0,0875 | +0,0133 | **cao hơn** | 0,1701 | −0,0343 | **thấp hơn** |
| token_nodes (4.1a) | 0,1000 | +0,0008 | **ngang bằng** | 0,1541 | −0,0183 | **thấp hơn** |
| GGNN-B mặc định (4.1a) | 0,0712 | +0,0296 | **cao hơn** | 0,0977 | +0,0381 | **cao hơn** |
| GCN-B tinh chỉnh (4.1c) | 0,0650 | +0,0358 | **cao hơn** | 0,1026 | +0,0332 | **cao hơn** |
| P1 khởi tạo CodeBERT (4.3) | 0,0532 | +0,0476 | **cao hơn** | 0,1188 | +0,0170 | **cao hơn** |
| C0 đối chứng (4.3) | 0,0520 | +0,0488 | **cao hơn** | 0,1026 | +0,0332 | **cao hơn** |
| **CodeBERT 4 đoạn (4.5)** | **0,1008** | | | **0,1358** | | |

Hai bức tranh khác nhau rõ rệt:

**Trên `project_wise`, mô hình text bắt kịp baseline token.** 0,1008 so với 0,1000 của `token_nodes`, chênh lệch 0,0008 nằm sâu trong nhiễu, nên hai bên **ngang nhau**. Và nó cao hơn `token_method` cùng mọi biến thể GNN với khoảng cách vượt độ lệch chuẩn.

**Trên `seen_project`, baseline token vẫn thắng rõ.** 0,1358 so với 0,1701 của `token_method` và 0,1541 của `token_nodes`, cả hai khoảng cách đều vượt độ lệch chuẩn. CodeBERT vẫn cao hơn mọi GNN.

So với Task 4.3, kết quả này có ý nghĩa riêng: ở 4.3, **khởi tạo** embedding token bằng CodeBERT cho P1 chỉ 0,0532, trong khi **fine-tune** cả CodeBERT ở đây cho 0,1008. Cùng một mô hình nguồn, chênh lệch gần gấp đôi, đến từ việc dùng nó như bảng tra cứu tĩnh hay như một bộ mã hóa có ngữ cảnh.

## 5. Phân bố theo lớp

F1 trung bình ba seed trên test `project_wise`, chia nhóm theo số mẫu test giống Task 4.3:

| Nhóm lớp | Số CWE | C0 (4.3) | 2 đoạn | 4 đoạn |
| :--- | ---: | ---: | ---: | ---: |
| đầu (≥50 mẫu) | 7 | 0,0904 | 0,1507 | **0,1951** |
| giữa (16-49 mẫu) | 5 | 0,0357 | 0,0370 | 0,0385 |
| đuôi (≤15 mẫu) | 11 | 0,0350 | 0,0572 | 0,0692 |

**Con số nhóm đuôi gây hiểu nhầm.** Trong 11 CWE của nhóm này, bản 4 đoạn chỉ ghi điểm ở ba lớp, và hai lớp chiếm **97%** giá trị trung bình của cả nhóm:

| CWE | Mẫu test | C0 | 2 đoạn | 4 đoạn |
| :--- | ---: | ---: | ---: | ---: |
| CWE-59 Link Following | 9 | 0,000 | 0,344 | **0,426** |
| CWE-22 Path Traversal | 8 | 0,137 | 0,228 | **0,311** |
| CWE-295 Certificate Validation | 9 | 0,083 | 0,057 | 0,024 |
| 8 CWE đuôi còn lại | 4 đến 13 | 0,000 đến 0,083 | 0,000 | **0,000** |

Đây là quan sát đáng chú ý nhất về mặt định tính của cả Phase 4. CWE-59 và CWE-22 là hai lớp có **dấu hiệu từ vựng rất đặc trưng** trong mã nguồn: `symlink`, `readlink`, `realpath`, chuỗi đường dẫn, `../`. Mô hình text bắt được, còn graph thì không, vì Task 4.0 đã hạ chữ thường và thay chuỗi ký tự bằng `<STR>` nên chính dấu hiệu đó bị xóa trước khi vào mô hình.

Ở nhóm đầu, bản 4 đoạn hơn đều và rõ: CWE-787 từ 0,137 của C0 lên 0,274, CWE-476 lên 0,227, CWE-190 lên 0,236, CWE-119 lên 0,207.

Số CWE có F1 test bằng 0 là **11 trên 23**, so với 5 của các nhánh GNN ở Task 4.3. CodeBERT bỏ hẳn nhiều lớp hơn nhưng giỏi hơn nhiều trên số lớp nó chịu dự đoán. Đó cũng là lý do weighted-F1 và accuracy tăng mạnh hơn Macro-F1.

## 6. Điểm bất thường và cách xử lý

### 6.1. Seed 44 hỏng ở bản 2 đoạn, lần chạy độ nhạy giải thích được

Ở bản 2 đoạn, Macro-F1 validation của seed 44 trên `project_wise` qua từng epoch là 0,0528 → 0,0470 → 0,0525 → 0,0484. **Không epoch nào vượt được epoch 1**, nên dừng sớm cắt ở epoch 4 và điểm test 0,0439 là của một mô hình huấn luyện đúng một epoch. Một mình seed này tạo ra gần như toàn bộ độ lệch chuẩn 0,0269.

**Lần chạy 4 đoạn trả lời dứt điểm**: cùng seed đó chạy hết 10 epoch, điểm tốt nhất rơi vào epoch 10, và test đạt 0,1022 ngang hai seed kia.

| Seed 44, project_wise | Epoch tốt nhất | Epoch đã chạy | Macro-F1 test |
| :--- | ---: | ---: | ---: |
| 2 đoạn | 1 | 4 | 0,0439 |
| 4 đoạn | 10 | 10 | 0,1022 |

Nguyên nhân là **thiếu ngữ cảnh, không phải bất ổn của fine-tune**. Với 37,4% token, tín hiệu validation quá nhiễu để dừng sớm bám vào; với 54,1% token, tín hiệu đủ mạnh để mô hình cải thiện liên tục suốt 10 epoch.

Hệ quả cho cách đọc báo cáo: **con số chính của Task 4.5 nên lấy từ bản 4 đoạn**, còn bản 2 đoạn giữ lại vì đó là cấu hình đã đăng ký trước và vì nó chứng minh được tác động của ngân sách đoạn.

### 6.2. Học thuộc nhanh

Train loss từ 3,07 xuống 0,24 trong 8 epoch ở bản 2 đoạn, trong khi Macro-F1 validation ngừng tăng từ epoch 4 đến 5. Cùng bệnh đã thấy ở Task 4.1a, 4.2 và 4.3, nhưng diễn ra nhanh hơn vì mô hình có 124,7 triệu tham số trên 6.101 mẫu train. Bản 4 đoạn đỡ hơn: nhiều lần chạy đi hết 10 epoch mà validation vẫn còn cải thiện, tức **giới hạn ngân sách epoch chứ không phải giới hạn mô hình**.

### 6.3. Hai lỗi trình bày của notebook, đã sửa

- Ô tổng hợp dùng `std` mặc định của pandas là `ddof = 1`, trong khi mọi bảng khác của đồ án dùng `ddof = 0`. Số trong báo cáo này lấy theo `ddof = 0`. Notebook đã sửa.
- Biểu đồ đường học vẽ train loss thang 0 đến 3 chung trục với Macro-F1 thang 0 đến 0,2, nên đường Macro-F1 bẹt sát đáy. Notebook đã chuyển sang trục kép, và [hình trong thư mục kết quả](4_5_results/figures/learning_curves.png) được vẽ lại từ chính `learning_curves.csv` của lần chạy, không đổi dữ liệu.

## 7. Đánh giá so với yêu cầu

`validate_run` chạy lại trên thư mục kết quả của bản đã đăng ký: **đạt**. Cụ thể cho cả hai lần chạy:

- Đúng model `codebert`, đủ ba seed 42 43 44, đủ hai protocol, không phải lần chạy rút gọn.
- Bản đã đăng ký khớp tuyệt đối cả 11 siêu tham số với `text_experiments.BASELINE`.
- Bản độ nhạy **chỉ lệch đúng một yếu tố** `max_chunks` từ 2 thành 4, mọi tham số còn lại giữ nguyên.
- Cây làm việc sạch, dataset `diversevul-7799-function-text`, 7.799 mẫu, `split_size_problems` rỗng ở cả hai.
- Lần chạy độ nhạy dùng lại nguyên vẹn kết quả của bản đã đăng ký thay vì huấn luyện lại. Đối chiếu sha256 cho thấy `results.csv`, `per_class.csv` và `metadata.json` **giống hệt từng byte**, nên hai lần chạy đặt cạnh nhau được.

Không có bước nào chọn cấu hình hay chọn epoch theo test. Lần chạy độ nhạy được quyết định trước khi nhìn kết quả, theo một quy tắc viết sẵn.

## 8. Giới hạn

- **Rò rỉ giữa validation và test của `seen_project`.** Task 4.4 kiểm tra trùng lặp theo cách chuẩn hóa của PrimeVul và tìm được một cặp hàm trùng nhau nằm ở hai tập, gồm `row-4156` ở validation và `row-4152` ở test, cùng nhãn CWE-125 và chỉ khác cách thụt lề. Tương đương 1 trên 763 mẫu test, tức 0,13 phần trăm. Protocol `project_wise` không bị ảnh hưởng. Nhóm giữ nguyên kết quả đã chạy và ghi nhận đây là giới hạn. Chi tiết ở mục 8 của [báo cáo Task 4.0](4_0_processed_data.md).
- **Vẫn chỉ đọc 54,1% lượng token** ở bản tốt nhất. So sánh với baseline token, vốn đọc toàn bộ hàm, vì thế vẫn chưa hoàn toàn công bằng. Đường cong độ phủ cho thấy phải lên 6 đoạn mới đạt khoảng 87% số hàm không bị cắt.
- **Ba seed là quá ít.** Mọi kết luận ở đây là mô tả, không phải kiểm định thống kê.
- **Ngân sách epoch chặn bản 4 đoạn.** Nhiều lần chạy chạm trần 10 epoch mà validation vẫn đang lên, nên 0,1008 là chặn dưới chứ chưa phải trần của cấu hình này.
- Chỉ thử CodeBERT, chưa thử UniXcoder.
- Siêu tham số không được dò, để giữ tính chất baseline đăng ký trước.
- Số của task này không so trực tiếp được với bài báo EMNLP 2024: họ dùng Big-Vul, chia ngẫu nhiên, và báo accuracy với weighted-F1 chứ không phải Macro-F1.

## 9. Kết luận

1. **Mô hình text pretrained là mô hình học được mạnh nhất trong toàn bộ Phase 4.** Với 4 đoạn, CodeBERT đạt 0,1008 trên `project_wise` và 0,1358 trên `seen_project`, cao hơn mọi biến thể GNN ở cả hai protocol với khoảng cách vượt độ lệch chuẩn. weighted-F1 0,1637 và MCC 0,0930 so với mức trần 0,1099 và 0,0413 của GNN.
2. **Trên `project_wise`, mô hình text đã bắt kịp baseline đếm token.** 0,1008 so với 0,1000, chênh lệch nằm sâu trong nhiễu. Đây là lần đầu trong cả đồ án một mô hình học được sánh ngang baseline đơn giản trên protocol khó.
3. **Trên `seen_project`, baseline đếm token vẫn thắng rõ.** 0,1701 so với 0,1358, khoảng cách vượt độ lệch chuẩn. Protocol này cho phép project lặp lại giữa các split, nên một bộ đếm token bắt được đặc trưng riêng của project dễ hơn là một mô hình phải học biểu diễn.
4. **Nút thắt là biểu diễn đầu vào, không phải kiến trúc mô hình.** Chuỗi bằng chứng đã khép lại: tinh chỉnh siêu tham số không giúp (4.1b, 4.2), đổi kiến trúc không giúp (4.2), thêm cạnh ngữ nghĩa không giúp ổn định (4.1c), hai can thiệp từ bài báo không giúp (4.3). Nhưng **đổi hẳn cách biểu diễn đầu vào từ graph sang văn bản thì cải thiện rõ rệt**, nâng Macro-F1 `project_wise` từ 0,0520 của nhóm đối chứng lên 0,1008.
5. **Lượng ngữ cảnh đọc được là một yếu tố thật, và nó quan trọng nhất ở protocol khó.** Nâng ngân sách từ 2 lên 4 đoạn làm độ lệch chuẩn `project_wise` co lại 6,4 lần và cứu hẳn một seed đã hỏng, trong khi trên `seen_project` thì không giúp gì. Điều này cho thấy phần thân hàm bị cắt chỉ thực sự có giá trị khi mô hình buộc phải tổng quát sang project chưa từng thấy.
6. **Bằng chứng định tính mạnh nhất nằm ở CWE-59 và CWE-22.** Hai lớp này có dấu hiệu từ vựng rõ trong mã nguồn, và chính hai lớp này mô hình text ghi điểm 0,426 với 0,311 còn graph thì bằng không. Nó chỉ thẳng vào chỗ mất mát: Task 4.0 hạ chữ thường và thay chuỗi ký tự bằng `<STR>`, xóa mất đúng loại tín hiệu đó. **Đây là đề xuất cụ thể nhất cho công việc tiếp theo**: giữ lại nội dung chuỗi và phân biệt chữ hoa chữ thường trong biểu diễn node.
7. **Task 5.1 cần dùng khoảng tin cậy bootstrap**, không chỉ độ lệch chuẩn của ba seed. Chênh lệch giữa bản 2 đoạn và 4 đoạn trên `project_wise` cho thấy ba seed có thể che giấu hoàn toàn một tác động thật.

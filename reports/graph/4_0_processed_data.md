# Báo cáo Task 4.0. Dữ liệu đồ thị đã xử lý

Dataset: [DiverseVul 9077 - Processed Graph Data](https://www.kaggle.com/datasets/vtnmai/diversevul-9077-processed-graph-data/data) (riêng tư, 3,06 GB, 22 tệp)
Đầu vào: [DiverseVul 9077 - Joern Code Graphs](https://www.kaggle.com/datasets/vtnmai/diversevul-9077-joern-code-graphs/data)
Đặc tả định dạng: `docs/4_0_data_interface_spec.md`
Mã nguồn: `src/graph/processed.py`, `src/graph/processed_checks.py`, `scripts/build_processed_data.py`
Notebook chạy: `notebooks/4_0_build_processed.ipynb` (mã lấy từ nhánh `main`, commit f7e0629)
Nhật ký chạy đầy đủ: `reports/graph/4_0_build_processed_run.ipynb`

## 1. Chuyển đổi gì sang gì

Graph JSON của Task 3.3 (node có `node_type`, `code_token` dạng chuỗi, cạnh có `src`, `dst`, `type`, nhãn CWE dạng chuỗi) được chuyển thành tensor: id loại node, id token mỗi node (độ dài cố định K), vị trí dòng tương đối, `edge_index`, `edge_type` (0 AST, 1 CFG, 2 DATA_DEP), nhãn trong [0, 22] và cờ `is_oversized`.

Quy tắc:
- Mẫu hợp lệ là mẫu có status `SUCCESS` hoặc `OVERSIZED_GRAPH` ở cả Graph A và Graph B.
- Vocabulary token (tần suất tối thiểu 2) và vocabulary loại node chỉ fit trên tập train của từng protocol.
- K bằng phân vị 95 của số token mỗi node trên tập train, không tính node Method, chặn trên 32.
- Graph quá lớn chỉ gắn cờ, không bỏ và không cắt ở bước này. Cắt lúc train bằng tham số `--max-nodes`.
- Cạnh có đầu mút ngoài tập node bị bỏ, token ngoài vocabulary thành `<UNK>`.

## 2. Kết quả

| Protocol | Split | Số mẫu | Graph A quá lớn | Graph B quá lớn |
| :--- | :--- | ---: | ---: | ---: |
| project_wise | train | 6.101 | 420 | 711 |
| project_wise | validation | 762 | 32 | 82 |
| project_wise | test | 936 | 102 | 204 |
| seen_project | train | 6.272 | 445 | 785 |
| seen_project | validation | 764 | 61 | 115 |
| seen_project | test | 763 | 48 | 97 |

- Tổng 7.799 mẫu hợp lệ, 1.278 mẫu bị bỏ, khớp báo cáo 3.3. Tổng số mẫu từng CWE khớp báo cáo 3.3 cho cả hai protocol.
- Không lớp CWE nào có 0 mẫu ở validation hoặc test.
- K bằng 23 cho project_wise và 24 cho seen_project. Khoảng 5,4% node bị cắt token. Vocabulary: 22 loại node, 25.151 token (project_wise) và 25.750 token (seen_project).
- Graph B train của project_wise có 6,0 triệu cạnh DATA_DEP, 2,13 triệu cạnh AST, 1,91 triệu cạnh CFG. Số node mỗi graph: trung vị 156, P95 là 1.239, lớn nhất 9.514.
- Bộ pilot 3.2: 25 trên 30 mẫu chuyển được, 5 mẫu còn lại là mẫu lỗi hoặc không hỗ trợ từ 3.2. Số node và cạnh khớp JSON gốc.

## 3. Kiểm tra

26 kiểm tra tự động đều đạt (`validation_report.json`): số mẫu và số graph quá lớn khớp 3.3, không mẫu nào ở hai split, split khớp manifest gốc, vocabulary ghi nhận đúng tập train, Graph A và Graph B cùng node, chỉ số và hình dạng tensor hợp lệ, pilot khớp.

Đối chiếu tay mẫu `row-3` giữa JSON gốc và tensor: 267 node, 1.372 cạnh (AST 266, CFG 246, DATA_DEP 860) khớp hoàn toàn, CWE-787 ra `y = 21`, token giải mã ngược khớp `code_token`. Tỷ lệ `<UNK>` ở tập test project_wise là 6,9%.

## 4. Mẫu trùng input

Băm gồm loại node, token, cạnh và loại cạnh.

| Protocol | Trùng trong train | Trùng với train ở validation | Trùng với train ở test |
| :--- | ---: | :--- | :--- |
| project_wise | 81 | 0 | 0 |
| seen_project | 74 | 5 mẫu, 1 mẫu khác nhãn | 6 mẫu, 2 mẫu khác nhãn |

Protocol chính project_wise không bị ảnh hưởng. Với seen_project cần nêu rõ khi báo kết quả.

## 5. Hạn chế đã biết

- Manifest chỉ có `sample_id`, split, nhãn. Số node và số cạnh từng mẫu không nằm trong manifest, chỉ có thống kê tổng hợp trong `validation_report.json`.
- Lớp nhỏ nên F1 từng lớp nhiễu: project_wise validation CWE-703 chỉ 3 mẫu, test CWE-401 và CWE-770 chỉ 4 mẫu.
- Phân bố lệch giữa split của project_wise: CWE-787 chiếm 31% validation nhưng 13% train. Test nặng hơn train: graph B quá lớn chiếm 21,8% test và 11,7% train, số node trung bình 466 so với 351.
- Lần chạy này ghi `spec_version` là 1.1 trong `metadata.json`. Định dạng dữ liệu của spec v1.1 và v1.2 giống nhau, mã nguồn đã sửa thành 1.2 cho các lần chạy sau.
- Dữ liệu lưu `int64` nên nặng 3,06 GB. Có thể nén xuống `int16` hoặc `int32` nếu cần.
- So sánh giữ hay bỏ graph quá lớn chưa làm, để sang 4.1 và 4.2.

## 6. Tái tạo

Chạy `notebooks/4_0_build_processed.ipynb` trên Kaggle (CPU, bật Internet) với Input là dataset graph gốc. Notebook tự kiểm các giá trị kỳ vọng 7.799, 554 và 997.

## 7. Kết luận

Task 4.0 bàn giao dữ liệu đầu vào dùng chung cho toàn bộ Phase 4 và Phase 5: **7.799 mẫu hợp lệ** đã chuyển từ JSON đồ thị sang tensor, đúng đặc tả `docs/4_0_data_interface_spec.md` phiên bản 1.2, lưu thành Kaggle Dataset `vtnmai/diversevul-9077-processed-graph-data` version 1.

Kết quả nghiệm thu: 26 kiểm tra tự động đều đạt, số mẫu và số graph quá lớn khớp báo cáo 3.3, không mẫu nào nằm ở hai split, vocabulary chỉ fit trên train, Graph A và Graph B dùng chung tập node. Đối chiếu tay mẫu `row-3` khớp hoàn toàn với JSON gốc.

Mọi task từ 4.1a đến 4.3 đọc đúng dataset version 1 này, nên kết quả giữa các task đặt cạnh nhau so sánh được trực tiếp. Riêng Task 4.5 không dùng được dữ liệu này, vì mô hình text cần mã nguồn gốc còn ở đây chỉ có id token theo vocabulary tự học; tập văn bản cho 4.5 được dựng riêng từ cùng 7.799 mẫu đó.

Ba giới hạn cần mang theo khi diễn giải mọi kết quả sau:

- **1.278 mẫu bị loại** ở Task 3.3 không nằm trong bất kỳ thực nghiệm nào. Tỷ lệ loại không đều giữa các CWE, nên phân bố lớp của tập thực nghiệm lệch nhẹ so với tập 9.077 ban đầu.
- **`seen_project` có 5 mẫu validation và 6 mẫu test trùng input với train.** Đây là hệ quả của việc protocol này cho phép project lặp lại, không phải lỗi chia split. Mọi con số `seen_project` phải đọc kèm điểm này.
- **Graph quá lớn vẫn được giữ nguyên**, 554 mẫu ở Graph A và 997 ở Graph B chỉ bị đánh dấu `is_oversized`. Việc cắt hay giữ để các task sau quyết định, và cấu hình N1 của 4.1b với 4.2 là nơi thử cắt.

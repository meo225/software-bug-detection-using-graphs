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
## 8. Task 4.4 — Audit trùng hàm theo PrimeVul

**COMPLETED — LEAKAGE DETECTED.** Audit thực thi PASS; source review COMPLETE.

### 8.1. Mục tiêu và dữ liệu đầu vào

Kiểm tra duplicate Raw/Legacy/PrimeVul và source leakage trên hai protocol, đối chiếu Task 2.3 và xác định ảnh hưởng đến Task 4.1a–4.3. Snapshot tham chiếu là main `2f2638a6e7328c8d5ff67417bf9464d0e080a7be`: 286 tệp dữ liệu/tài liệu/kết quả, gồm 8 notebook đã chạy. Các artifact cũ cung cấp cohort, split và provenance; không chứa đủ source để thay raw JSONL.

Đầu vào gồm [manifest 9.077 mẫu](../../data/splits/diversevul_experiment_manifest.csv), sáu file ID split, [1.278 failed samples](3_3_failed_samples.csv) và JSONL gốc. Có **7.799 ID hợp lệ**, không ID failed ngoài manifest hoặc metadata mismatch; split khớp manifest:

| Protocol | Train | Validation | Test |
| --- | ---: | ---: | ---: |
| project_wise | 6.101 | 762 | 936 |
| seen_project | 6.272 | 764 | 763 |

Raw `diversevul_20230702.json` được nhận diện từ nguồn tải do [repository DiverseVul](https://github.com/wagner-group/diversevul) công bố: **736.915.162 byte**, SHA-256 `7937c26003c4c24a396747432487e8abdd1c4622b5547ae93855bee15266bd57`, **330.492 object JSON**, 0 dòng trống. Join đủ 9.077 ID với source/project/commit/nhãn/CWE, không missing ID; `row-0` là object không trống đầu tiên, tại dòng vật lý 1. [Download verification](4_4_download_verification.json) lưu nguồn tải và fingerprint; raw dataset được Git ignore.

### 8.2. Phương pháp kiểm toán

[CLI](../../scripts/audit_function_leakage.py) gọi [module audit](../../src/data/function_leakage_audit.py), giữ nguyên dữ liệu và split. So sánh hai cohort: toàn manifest 9.077 mẫu và 7.799 mẫu sau loại failed; không đánh số lại ID.

| Phương pháp | Normalization trước hash |
| --- | --- |
| Raw | Giữ nguyên chuỗi source mà pipeline đọc được. |
| Legacy — Task 2.3 | Đổi CRLF/CR thành LF, bỏ space/TAB cuối dòng và dòng trống ở hai biên; giữ thụt lề và khoảng trắng bên trong. Dùng lại `normalize_whitespace()` trong [preprocessing.py](../../src/data/preprocessing.py). |
| PrimeVul — Task 4.4 | Xóa ASCII space, TAB, LF, CR ở mọi vị trí, kể cả literal; không dùng `\s`, không xóa comment hoặc đổi tên biến. |

Phép đo áp dụng normalization theo [PrimeVul v2 §III-A](https://arxiv.org/html/2403.18624v2#S3.SS1), không tái triển khai pipeline xây dataset của bài báo. Encode UTF-8 nghiêm ngặt; lưu MD5 để đối chiếu phương pháp và dùng SHA-256 để nhóm. Các source trong cùng bucket phải có chuỗi chuẩn hóa bằng nhau, nếu không báo collision. Fingerprint raw được đối chiếu [provenance EDA](../dataset/tables/audit_status.json); kết quả Legacy được đối chiếu [split report Task 2.3](../../data/splits/diversevul_split_report.json).

Với nhóm n mẫu: n mẫu ảnh hưởng, n−1 mẫu dư, n(n−1)/2 cặp không thứ tự. Nếu nhóm có t/v/e mẫu ở train/validation/test thì số cặp xuyên split là tv/te/ve. Tổng nhóm/mẫu xuyên split dùng hợp duy nhất; tổng cặp nội bộ + xuyên split phải bằng tổng cặp. Không cộng hai protocol hoặc so trực tiếp hai cohort khác nhau.

### 8.3. Kết quả duplicate và leakage

Trên **7.799 mẫu hợp lệ**, hai protocol dùng cùng tập source:

| Phương pháp | project_wise: nhóm / mẫu ảnh hưởng / cặp | seen_project: nhóm / mẫu ảnh hưởng / cặp |
| --- | ---: | ---: |
| Raw | 0 / 0 / 0 | 0 / 0 / 0 |
| Legacy | 3 / 6 / 3 | 3 / 6 / 3 |
| PrimeVul | 6 / 12 / 6 | 6 / 12 / 6 |

Sáu nhóm PrimeVul đều có hai thành viên, tổng 6 mẫu dư, không xung đột CWE; so Legacy tăng 3 nhóm/6 mẫu/3 cặp. Có **3 nhóm `legacy_subgroups=2`**: mỗi nhóm chứa hai lớp source Legacy riêng biệt, mỗi lớp có một mẫu, không phải hợp nhất hai nhóm duplicate Legacy. Trên manifest **9.077 mẫu**, Legacy có 6 nhóm/12 mẫu/6 cặp, khớp Task 2.3 và không xuyên split; PrimeVul có 10 nhóm/20 mẫu/10 cặp, trong đó có **hai nhóm xuyên split ở seen_project**, một cặp train–validation và một cặp validation–test. Nhóm train–validation không còn ở cohort 7.799 mẫu vì một thành viên bị loại ở Task 3.3, nên không mẫu nào của nhóm đó từng vào thực nghiệm.

| Protocol / loại cặp PrimeVul | Nhóm xuyên split | Mẫu ảnh hưởng | Cặp |
| --- | ---: | ---: | ---: |
| project_wise: train–validation | 0 | 0 | 0 |
| project_wise: train–test | 0 | 0 | 0 |
| project_wise: validation–test | 0 | 0 | 0 |
| seen_project: train–validation | 0 | 0 | 0 |
| seen_project: train–test | 0 | 0 | 0 |
| seen_project: validation–test | 1 | 2 | 1 |

**PW** = `project_wise`; **SP** = `seen_project`. Raw và Legacy không có cặp xuyên split. PrimeVul trên PW có 3 cặp nội bộ train, 3 validation, 0 test và 0 xuyên split, tổng 6 cặp. Trên SP: **4 cặp nội bộ train + 0 validation + 1 test + 1 validation–test = 6 cặp**. Không cộng số của hai protocol.

Cặp source đã xác nhận là `_gdContributionsCalc`, hash PrimeVul `9ba58fa85fe03bfd8a5abadbb2dc46d953f4aefbe5e41a84dae1ff7a617f0655`:

| ID | Project | CWE | project_wise | seen_project | Dòng JSONL vật lý |
| --- | --- | --- | --- | --- | ---: |
| row-4152 | libgd | CWE-125 | validation | test | 4.153 |
| row-4156 | php-src | CWE-125 | validation | validation | 4.157 |

Hai mẫu cùng thuộc validation trong PW nên không tạo leakage xuyên split; trong SP, `row-4152` thuộc test và `row-4156` thuộc validation, tạo một cặp validation–test.

Hai source có 56 dòng, 37 dòng khác nhau nhưng bằng nhau khi chỉ bỏ space/TAB đầu dòng; token, literal, comment và macro không đổi. Phân loại: **confirmed_formatting_only_duplicate**. Metadata local của php-src mô tả fix được port từ commit libgd; chưa xác minh độc lập upstream. Tỷ lệ ảnh hưởng là **1/763 = 0,1311% test SP**, **1/764 = 0,1309% validation SP**; đây không phải ước lượng sai lệch metric.

Held-out ID trùng **train** theo PrimeVul, chỉ trên cohort 7.799:

| Protocol | Validation ID trùng train | Test ID trùng train |
| --- | ---: | ---: |
| project_wise | 0/762 (0%) | 0/936 (0%) |
| seen_project | 0/764 (0%) | 0/763 (0%) |

Bằng chứng cấp nhóm/mẫu và các mẫu số nằm trong [duplicate groups](4_4_leakage_audit_full/duplicate_groups.csv), [cross-split leakage](4_4_leakage_audit_full/cross_split_leakage.csv) và [source review](4_4_leakage_audit_full/source_review_evidence.json). Không khái quát kết luận train–held-out này sang cohort 9.077 hoặc mọi loại code clone.

### 8.4. Phân tích ảnh hưởng đến thực nghiệm

**Impact Matrix:** PW = `project_wise`, SP = `seen_project`, V = validation, T = test. Mọi nhóm dùng cả hai protocol; `n_eval` V/T là **762/936 (PW)** và **764/763 (SP)**. Metadata GNN 4.1b–4.3 ghi processed dataset version 1.

Phát hiện chung theo PrimeVul: **PW không có duplicate xuyên split; SP có một cặp V–T, không có cặp train–V hoặc train–T**. Chưa có bằng chứng định lượng hướng hoặc mức sai lệch metric. Đối chiếu CSV/metadata xác định phạm vi ảnh hưởng, không thay thế prediction cấp mẫu.

| Task / thực nghiệm | Protocol và cách lựa chọn | Ảnh hưởng hoặc giới hạn riêng | Bằng chứng |
| --- | --- | --- | --- |
| **4.1a baseline:** Majority, random, token_method, token_nodes | PW/SP; fit từ train, báo V/T; không chọn cấu hình bằng V/T. | SP V/T chưa hoàn toàn độc lập; không quy phát hiện này thành leakage từ train hoặc sai lựa chọn baseline. | [CSV](4_1a_results/baselines_results.csv), [script](../../scripts/run_baselines_4_1a.py) |
| **4.1a GNN:** GCN/GGNN × Graph A/B | PW/SP; cấu hình mặc định, chọn checkpoint bằng Macro-F1 V, patience 8. | SP dùng V để chọn epoch trong khi có source trùng T; chưa đo ảnh hưởng lên checkpoint/metric. | [CSV](4_1a_results/gnn_results.csv), [thiết lập](4_1a_baselines_gnn.md) |
| **4.1b GCN-A tuning** | PW/SP; chọn epoch theo V; chọn cấu hình toàn cục bằng Macro-F1 PW V: cấu hình được lựa chọn (L1 của Task 4.1b). | Cặp SP V–T không phải bằng chứng chọn sai cấu hình dựa trên PW; checkpoint SP vẫn mang giới hạn V–T. | [Kế hoạch](4_1b_results/tuning/experiment_plan.json), [lựa chọn cố định](4_1b_results/tuning/frozen_selection.json) |
| **4.1b GCN-A final test** | PW/SP; chấm T với cấu hình được lựa chọn (L1 của Task 4.1b), đã cố định trước test. | SP có 1/763 test ID trùng V; kết quả T không dùng chọn lại cấu hình. | [CSV](4_1b_results/final/results.csv), [metadata](4_1b_results/final/metadata.json) |
| **4.1c GCN-B** | PW/SP; dùng L1 của Task 4.1b, không tuning mới; chọn checkpoint bằng Macro-F1 V, chấm V/T. | So sánh Graph A/B trên SP có cùng giới hạn V–T; không suy ra hướng hoặc độ lớn ảnh hưởng. | [CSV](4_1c_results/L1/results.csv), [kế hoạch](4_1c_results/experiment_plan.json) |
| **4.2 GGNN-B tuning** | PW/SP; chọn epoch theo V; chọn cấu hình toàn cục bằng Macro-F1 PW V: cấu hình được lựa chọn (L1 của Task 4.2). | Không quy cặp SP thành nguyên nhân chọn sai cấu hình; checkpoint SP có giới hạn V–T. | [Lựa chọn cố định](4_2_results/tuning/frozen_selection.json), [CSV L1](4_2_results/tuning/L1/results.csv) |
| **4.2 GGNN-B final** | PW/SP; chấm T với cấu hình được lựa chọn (L1 của Task 4.2), không đổi lựa chọn theo T. | SP T chưa độc lập hoàn toàn với V; chưa lượng hóa sai lệch metric. | [CSV](4_2_results/final/results.csv), [metadata](4_2_results/final/metadata.json) |
| **4.2 GGNN-B sensitivity** | PW/SP; sau khi cố định L1 của Task 4.2, nạp checkpoint các cấu hình còn lại để chấm T; không dùng T đổi lựa chọn. | Thứ hạng/tương quan V–T của SP cần đọc kèm giới hạn chung; không quy toàn bộ hiện tượng cho cặp duplicate. | [Tổng hợp](4_2_results/figures/sensitivity_test_all_configs.csv), [quy trình](4_2_ggnn_tuning.md) |
| **4.3 GGNN-B C0/P1/P2** | PW/SP; nền L1 của Task 4.2; C0 đối chứng, P1 token initialization, P2 adaptive loss; chọn epoch bằng Macro-F1 V, chấm cả ba nhánh. | Không chọn nhánh thắng bằng T; so sánh các nhánh SP cùng mang giới hạn V–T. | [Kế hoạch](4_3_results/arms/experiment_plan.json), [thiết kế và kết quả](4_3_paper_experiments.md) |

Không yêu cầu chạy lại toàn bộ thực nghiệm chỉ từ phát hiện này; đánh giá bổ sung hoặc thay benchmark cần phạm vi được duyệt riêng.

### 8.5. Phương án xử lý và quyết định

**A — Retain & Document đã được lựa chọn và áp dụng trong báo cáo Task 4.4:** giữ nguyên benchmark v1, split, frozen selection và kết quả thực nghiệm cũ; giới hạn SP validation–test được ghi nhận trong Impact Matrix ở mục 8.4. Chưa xác nhận các báo cáo Task 4.1a–4.3 đã cập nhật riêng theo phát hiện này. A bảo toàn khả năng so sánh, không chứng minh leakage vô hại. **B0/B1/C là đề xuất chưa triển khai**, cần phê duyệt riêng và không phải điều kiện còn thiếu để hoàn tất audit.

| Phương án | Cách thực hiện và đầu ra dự kiến | Dependencies, chi phí và giới hạn |
| --- | --- | --- |
| **B0 — Sensitivity Bounds** | Từ confusion matrix test SP seed 42: tái lập metric gốc, rồi giảm một count tại mỗi ô có count dương của hàng CWE-125; tổng 763 xuống 762. Báo min/max metric và delta vào `reports/graph/4_4_sensitivity/sensitivity_bounds_seed42.csv`, kèm provenance. | Matrix 23 × 23 có ở GNN 4.1a, 4.1b/4.1c, 4.2 final/sensitivity và các nhánh 4.3; không có matrix baseline hoặc seed 43/44 trong bộ đã bàn giao. Chỉ evaluation từ count, không cần inference/training. Đây là bound theo giả định, không phải delta thực tế của row-4152, tác động nhân quả hoặc trung bình ba seed. |
| **B1 — Exact Sensitivity** | Tái lập metric trên đủ 763 ID, sau đó bỏ riêng test ID `row-4152` và tính lại trên 762 ID; giữ train/validation và checkpoint selection. Output dự kiến `reports/graph/4_4_sensitivity/metrics_excluding_row4152.csv` và provenance riêng. | Cần prediction gắn ID/label mapping/provenance cho từng run; CSV/matrix tổng hợp không đủ. Có prediction thì chỉ evaluation; chỉ có checkpoint thì cần đúng tensor v1, vocabulary, cấu hình và code/môi trường để inference. Chưa đủ dependencies cho toàn bộ run; không đo được tác động lên chọn epoch nếu validation sạch từ đầu. |
| **C — Clean Benchmark v2** | Tạo manifest/split/processed provenance v2 riêng, audit lại và báo kết quả v2 tách biệt. Gom thành phần liên thông theo group cũ và PrimeVul hash; bảo toàn nhãn và ràng buộc project PW, kiểm tra commit/CVE và phân bố lớp. | Là thay đổi benchmark chính thức, chi phí cao nhất; source-clean không đồng nghĩa sạch graph-input overlap hoặc mọi leakage. Không ghép metric v1/v2 như cùng benchmark. |

B0 dùng đúng key protocol/graph/model/seed/split và thứ tự 23 lớp; [schema](../../configs/graph/schema_spec.yaml) ánh xạ CWE-125 sang class index 2. Phải tái lập metric gốc từ matrix và CSV, giữ định nghĩa/`zero_division` của [classification_report](../../src/evaluation/metrics.py); không công bố bound nếu mapping, tổng count hoặc metric không khớp. Tham chiếu matrix: [4.1a](4_1a_results/gnn_confusion_matrices.json), [4.1b](4_1b_results/final/confusion_matrices.json), [4.1c](4_1c_results/L1/confusion_matrices.json), [4.2](4_2_results/final/confusion_matrices.json). [Script GNN](../../scripts/train_gnn.py) chỉ xuất matrix cho seed đầu tiên.

B1 chưa có prediction cấp mẫu trong output local: [predict()](../../src/training/gnn_trainer.py) trả nhãn/prediction nhưng exporter không lưu mapping ID; [evaluate_run()](../../src/evaluation/evaluator.py) còn là stub. [Metadata 4.1c](4_1c_results/L1/metadata.json) có `save_checkpoints=true`, nhưng chưa xác minh checkpoint ngoài nguồn lưu của đợt thiết kế; `save_checkpoints=false` ở final 4.1b/4.2 và 4.3 không chứng minh mọi checkpoint đã mất. Baseline token chưa bàn giao model đã fit; fit lại là thực nghiệm mới. Không mặc định CPU tái tạo chính xác metric GPU. Bộ shard local `data/processed/task40_handoff/` là DRAFT `strict_pairs_6802_v1`, 6.802 mẫu, feature dense `x`, không thay thế tensor v1 7.799 mẫu dùng `x_type/x_tok`.

Với C, ứng viên tối thiểu là giữ PW, chuyển singleton `row-4152` từ SP test sang validation cùng `row-4156`, cho số mẫu SP **6.272/765/762**. Đây chưa phải split được tạo hoặc nghiệm thu; cần kiểm tra support 23 CWE, phân bố project–CWE, group/commit/CVE và mọi cặp xuyên split, không chọn split theo test metric. Nếu cần sạch graph-input overlap, phải có policy collision riêng, nhất là nhóm lệch nhãn.

| Task / tài nguyên | Ảnh hưởng dự kiến nếu triển khai C |
| --- | --- |
| 3.3 — graph extraction | Đổi split tự nó không yêu cầu chạy lại Joern. Tái sử dụng graph hoặc tensor tương thích nếu khôi phục được đúng artifact; chỉ khi thiếu/hỏng và không thể khôi phục mới đề xuất regeneration riêng. |
| 4.0 — processed data | Cần manifest/tensor split và provenance v2. Nếu giữ train nguyên trạng, chỉ tái sử dụng vocabulary/K sau khi xác minh train fingerprint; đóng gói lại validation/test riêng. Nếu train đổi, phải fit lại vocabulary/K và preprocessing tương ứng. Pipeline hiện tại fit từ train trong [processed.py](../../src/graph/processed.py). |
| 4.1a baseline/GNN | Nếu công bố kết quả v2 theo quy trình chuẩn, phải lập kế hoạch đánh giá lại các baseline và chọn epoch/đánh giá GNN trên split v2 liên quan; baseline token cần model/TF-IDF tương thích hoặc fit lại được phê duyệt. |
| 4.1b GCN-A, 4.1c GCN-B, 4.2 GGNN-B | PW có thể giữ kết quả nếu chứng minh input/quy trình giữ nguyên. SP validation đổi thì checkpoint v1 không mặc nhiên là checkpoint đã chọn bằng validation v2; thực nghiệm v2 chính thức cần kế hoạch retraining/chọn epoch/evaluation riêng. Giữ provenance riêng của cấu hình được lựa chọn (L1 của Task 4.1b và L1 của Task 4.2) theo PW validation; không ghi đè frozen selection. |
| 4.3 GGNN-B C0/P1/P2 | Nếu đánh giá can thiệp trên benchmark v2, dùng cùng dữ liệu/quy trình v2 cho các nhánh để giữ so sánh nội bộ; lập kế hoạch chạy lại các nhánh SP liên quan, không ghép metric v1 và v2 như cùng một benchmark. |

### 8.6. Giới hạn, nghiệm thu và kết luận

Xóa whitespace có thể gộp source khác nghĩa: literal (`"a b"`/`"ab"`), token (`a + +b`/`a++b`), comment hoặc macro. Cặp xuyên split đã được review, nhưng các nhóm nội bộ chưa được kiểm tra ngữ nghĩa toàn bộ. Phương pháp không phát hiện đầy đủ clone đổi tên biến, đổi comment, gần giống hoặc tương đương ngữ nghĩa.

Source duplicate khác **graph-input duplicate** của Task 4.0: 5 validation và 6 test SP trùng input train, trong đó lần lượt 1 và 2 mẫu khác nhãn. Không cộng hai phép đo, không coi source-clean là đã xử lý graph-input overlap; project lặp lại tự nó không giải thích hoặc loại trừ trùng input.

| Hạng mục | Kết luận |
| --- | --- |
| Audit execution / source review | **PASS / COMPLETE** |
| Tiêu chí không có source duplicate xuyên split theo PrimeVul | **FAIL — LEAKAGE DETECTED**: một cặp SP validation–test |
| Impact Matrix và remediation proposal | **COMPLETE**; A được chọn, B0/B1/C chưa thực hiện |
| Task 4.4 | **COMPLETED — LEAKAGE DETECTED** |

Bằng chứng kiểm thử trong [acceptance](4_4_leakage_audit_full/acceptance.json): **61 test PASS, 0 failed/skip, 6,76 giây**, gồm 14 test mới trên dữ liệu tổng hợp và regression `tests/test_data`, Python 3.14.5. Bao phủ normalization/false positive, đếm cặp, hai protocol, ID/dòng trống, input lỗi, collision và CLI; đây là kết quả lịch sử, không phải lần chạy mới khi biên tập tài liệu.

### 8.7. Artifact và hướng dẫn tái lập

| Nội dung | Bằng chứng |
| --- | --- |
| Input, code/môi trường và nghiệm thu full audit | [input_validation.json](4_4_leakage_audit_full/input_validation.json), [provenance.json](4_4_leakage_audit_full/provenance.json), [acceptance.json](4_4_leakage_audit_full/acceptance.json) |
| Hash từng ID và thành viên nhóm | [sample_hashes.csv](4_4_leakage_audit_full/sample_hashes.csv), [duplicate_groups.csv](4_4_leakage_audit_full/duplicate_groups.csv), [duplicate_members.csv](4_4_leakage_audit_full/duplicate_members.csv) |
| Thống kê duplicate, leakage và đối chiếu Legacy | [duplicate_summary.csv](4_4_leakage_audit_full/duplicate_summary.csv), [cross_split_leakage.csv](4_4_leakage_audit_full/cross_split_leakage.csv), [legacy_comparison.csv](4_4_leakage_audit_full/legacy_comparison.csv) |
| Phân loại cặp source | [cross_split_review.csv](4_4_leakage_audit_full/cross_split_review.csv), [source_review_evidence.json](4_4_leakage_audit_full/source_review_evidence.json) |
| Download và lịch sử code cleanup | [download verification](4_4_download_verification.json), [cleanup provenance addendum](4_4_cleanup_provenance_addendum.json) |

Artifact không chứa toàn bộ source DiverseVul. Addendum cho phép khôi phục nguyên byte source lịch sử và đối chiếu với code hiện tại; [redaction manifest](4_4_public_redaction_manifest.json) phân biệt fingerprint gốc với bản công khai.

Dùng raw đúng fingerprint, dependencies dự án và input/split được provenance chỉ định. Chạy từ repository root với thư mục output mới hoặc rỗng:

```powershell
python scripts/audit_function_leakage.py --output-dir reports/graph/4_4_leakage_audit_recheck
python -m pytest tests/test_data -ra
```

Mã thoát CLI: **0** không có cặp xuyên split theo phép đo; **1** có cặp PrimeVul xuyên split; **2** BLOCKED, không kết luận sạch. File có trước lỗi chỉ là kết quả trung gian; luôn đọc trạng thái cuối trong `input_validation.json`.

Lưu ý khi đọc artifact đã nghiệm thu: trong bản đã lưu, trường `status` mang kết luận về rò rỉ chứ không phải kết quả kiểm tra đầu vào. Phần kiểm tra đầu vào của lần chạy đó đạt hoàn toàn, thể hiện ở `missing_failed_ids` bằng 0, `metadata_mismatches` bằng 0 và các số split khớp manifest. Để tránh hiểu nhầm, CLI nay ghi hai trường riêng là `leakage_verdict` và `input_validation`. Bộ artifact cũ giữ nguyên từng byte vì acceptance.json đã ghi sha256 của chúng. Source review là bước riêng sau phát hiện tự động. Không ghi đè bộ artifact đã nghiệm thu.

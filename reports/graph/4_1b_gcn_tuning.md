# Báo cáo Task 4.1b: Tinh chỉnh GCN trên Graph A

Dữ liệu: [DiverseVul 9077 - Processed Graph Data](https://www.kaggle.com/datasets/vtnmai/diversevul-9077-processed-graph-data/data), version 1 (`vtnmai/diversevul-9077-processed-graph-data/versions/1`), theo [Task 4.0](4_0_processed_data.md).
Mã thực nghiệm: commit `5d8b99e821c0eb93d873f6ff17c3c7fe8ab5d5f5`.
Notebook nguồn: [4_1b_gcn_tuning.ipynb](../../notebooks/4_1b_gcn_tuning.ipynb). Notebook đã thực thi: [Kaggle Saved Version 2 — tinh chỉnh](4_1b_gcn_tuning_run.ipynb) và [Kaggle Saved Version 3 — đánh giá test](4_1b_gcn_final_run.ipynb).
Kết quả: [giai đoạn tinh chỉnh](4_1b_results/tuning/) và [đánh giá test cuối](4_1b_results/final/).
Checkpoint được lưu trên Kaggle và không được đưa vào Git.
Kết quả tham chiếu: [báo cáo Task 4.1a](4_1a_baselines_gnn.md).

## 1. Cấu hình

GCN-A là mô hình GCN sử dụng Graph A, chỉ gồm các cạnh của cây cú pháp trừu tượng (AST). Cấu hình được lựa chọn dựa trên validation; test chỉ được đánh giá sau khi cấu hình đã cố định. Protocol `project_wise` là đánh giá chính, còn `seen_project` là đối chứng. Task 4.1c sử dụng cùng cấu hình đã chọn để đánh giá Graph B, không tinh chỉnh dựa trên test.

- GCN đối xứng hóa cạnh, thêm self-loop và không phân biệt loại cạnh. Biểu diễn của mỗi node là tổng của ba thành phần: embedding loại node, trung bình embedding các token (không tính padding) và phép chiếu vị trí dòng mã nguồn tương đối. Mô hình tổng hợp biểu diễn graph bằng mean và max; đầu phân loại MLP dự đoán một trong 23 nhãn CWE.
- B0 là cấu hình cơ sở: chiều biểu diễn ẩn (dim) 128, 3 lớp GCN và dropout 0,2. Hàm mất mát là cross-entropy có trọng số lớp được tính từ tập train. Bộ tối ưu AdamW sử dụng learning rate 1e-3 và weight decay 1e-4. Batch size là 32, ngưỡng gradient clipping là 5,0, số epoch tối đa là 40 và patience là 8. Mô hình sử dụng toàn bộ mẫu (`limit = null`).
- Cả bảy cấu hình được huấn luyện trên tập train và chỉ đánh giá trên validation trong giai đoạn tinh chỉnh, ở hai protocol với các seed **42, 43, 44**: 7 cấu hình × 2 protocol × 3 seed = **42 lần huấn luyện**. B0 được huấn luyện lại trong cùng môi trường với các biến thể; kết quả của Task 4.1a được sử dụng riêng làm tham chiếu. Sau khi lựa chọn và cố định L1, sáu checkpoint tương ứng với hai protocol và ba seed được sử dụng cho sáu lần đánh giá test.
- Checkpoint được chọn tại epoch có **Macro-F1 validation chưa làm tròn cao nhất**; nếu các giá trị bằng nhau, mô hình giữ checkpoint ở epoch sớm nhất. B0, D1, W1, H1, L1 và N1 sử dụng Macro-F1 validation làm tiêu chí early stopping. E1 sử dụng **validation loss có trọng số** làm tiêu chí early stopping, nhưng vẫn chọn checkpoint theo Macro-F1 validation. Khi giá trị của tiêu chí cải thiện nghiêm ngặt, bộ đếm số epoch liên tiếp không cải thiện được đặt lại; nếu không, bộ đếm tiếp tục tăng đến ngưỡng patience.
- Theo mặc định, các đồ thị vượt ngưỡng kích thước không bị cắt. N1 chỉ giữ 1.000 node đầu theo thứ tự lưu và các cạnh có cả hai đầu mút thuộc tập node này. Quy tắc được áp dụng trong bộ nhớ cho cả train và validation, không loại mẫu hoặc ghi đè tensor nguồn. L1 không áp dụng giới hạn số node tối đa.

### Dữ liệu và phân chia tập

Thí nghiệm sử dụng nguyên trạng dữ liệu đã xử lý của Task 4.0, cách phân chia tập, vocabulary và 23 nhãn; không trích xuất lại graph. Số mẫu train và kích thước vocabulary dưới đây được trích từ báo cáo 4.0. Số mẫu validation/test khớp `n_eval` và tổng support trong các tệp kết quả của Task 4.1b.

| Protocol | Train | Validation | Test | K (token/node) | Vocabulary token |
| :--- | ---: | ---: | ---: | ---: | ---: |
| project_wise | 6.101 | 762 | 936 | 23 | 25.151 |
| seen_project | 6.272 | 764 | 763 | 24 | 25.750 |

`K` là độ dài chuỗi token cố định của mỗi node: `x_tok` có dạng [N, K], được cắt hoặc đệm tới K token theo đặc tả Task 4.0. K được xác định từ train riêng cho từng protocol; số nhãn phân loại luôn là **23 CWE** ở cả hai protocol.

Mỗi protocol có 7.799 hàm hợp lệ; 1.278 hàm đã bị loại ở Task 4.0. Vocabulary chỉ được xây dựng từ tập train. Dữ liệu có 22 loại node. Graph A có 554 đồ thị vượt ngưỡng cảnh báo; trong project_wise, số lượng tương ứng theo thứ tự train/validation/test là 420/32/102. Theo Task 4.0, CWE-787 chiếm khoảng 31% tập validation của project_wise, so với 13% tập train; CWE-703 chỉ có 3 mẫu validation. Trong `seen_project`, 5 mẫu validation và 6 mẫu test có dữ liệu đầu vào trùng với train; trong số đó, lần lượt 1 và 2 mẫu có nhãn khác với mẫu trùng tương ứng trong train. `project_wise` không có dữ liệu đầu vào trùng giữa train và các tập validation/test. Các kết quả kiểm tra này được kế thừa từ Task 4.0, không được thực hiện lại trên tensor khi biên soạn báo cáo.

### Bảy cấu hình thực nghiệm

Bảy cấu hình thực nghiệm được xác định trước khi tiến hành huấn luyện. Mỗi cấu hình biến thể chỉ thay đổi một yếu tố so với cấu hình cơ sở B0.

| ID | Thay đổi so với B0 |
| :--- | :--- |
| B0 | Giữ nguyên mặc định |
| E1 | Early stopping: Macro-F1 → validation loss |
| D1 | Dropout: 0,2 → 0,4 |
| W1 | Weight decay: 1e-4 → 1e-3 |
| H1 | Dim: 128 → 64 |
| L1 | Số lớp GCN: 3 → 2 |
| N1 | `max_nodes`: không giới hạn → 1.000 |

## 2. Kết quả

Các bảng metric trình bày **trung bình ± độ lệch chuẩn tổng thể** trên ba seed, được tính từ CSV chưa làm tròn bằng `statistics.mean` và `statistics.pstdev` (ddof = 0). Macro-F1 là trung bình F1 trên đủ 23 nhãn; F1 của lớp không có dự đoán đúng được tính bằng 0. F1 và accuracy có miền giá trị [0, 1], còn MCC có miền [-1, 1]. Các bảng metric tổng hợp được làm tròn đến bốn chữ số thập phân; việc lựa chọn cấu hình sử dụng giá trị chưa làm tròn.

### Kết quả validation của bảy cấu hình — Kaggle Saved Version 2

**project_wise**

| ID | Macro-F1 | Weighted-F1 | MCC | Accuracy |
| :--- | ---: | ---: | ---: | ---: |
| B0 | 0,0545 ± 0,0081 | 0,0754 ± 0,0135 | 0,0128 ± 0,0034 | 0,0665 ± 0,0080 |
| E1 | 0,0434 ± 0,0123 | 0,0527 ± 0,0191 | 0,0303 ± 0,0209 | 0,0591 ± 0,0172 |
| D1 | 0,0490 ± 0,0021 | 0,0642 ± 0,0145 | 0,0177 ± 0,0101 | 0,0661 ± 0,0097 |
| W1 | 0,0559 ± 0,0055 | 0,0755 ± 0,0226 | 0,0191 ± 0,0162 | 0,0731 ± 0,0210 |
| H1 | 0,0632 ± 0,0108 | 0,0802 ± 0,0210 | 0,0203 ± 0,0199 | 0,0770 ± 0,0134 |
| L1 | 0,0696 ± 0,0092 | 0,1247 ± 0,0272 | 0,0236 ± 0,0184 | 0,1076 ± 0,0237 |
| N1 | 0,0594 ± 0,0078 | 0,0804 ± 0,0113 | 0,0186 ± 0,0108 | 0,0761 ± 0,0060 |

**seen_project**

| ID | Macro-F1 | Weighted-F1 | MCC | Accuracy |
| :--- | ---: | ---: | ---: | ---: |
| B0 | 0,1455 ± 0,0035 | 0,2127 ± 0,0162 | 0,1423 ± 0,0164 | 0,2024 ± 0,0194 |
| E1 | 0,1053 ± 0,0039 | 0,1478 ± 0,0033 | 0,0932 ± 0,0037 | 0,1392 ± 0,0068 |
| D1 | 0,1539 ± 0,0089 | 0,2070 ± 0,0074 | 0,1395 ± 0,0076 | 0,1985 ± 0,0096 |
| W1 | 0,1600 ± 0,0026 | 0,2089 ± 0,0068 | 0,1374 ± 0,0073 | 0,1972 ± 0,0114 |
| H1 | 0,1474 ± 0,0178 | 0,1929 ± 0,0155 | 0,1237 ± 0,0141 | 0,1811 ± 0,0134 |
| L1 | 0,1612 ± 0,0114 | 0,2081 ± 0,0014 | 0,1413 ± 0,0025 | 0,2072 ± 0,0031 |
| N1 | 0,1508 ± 0,0094 | 0,1959 ± 0,0043 | 0,1264 ± 0,0060 | 0,1880 ± 0,0099 |

### Xếp hạng validation và lựa chọn đã cố định

`experiment_plan.json` quy định `selection = project_wise.validation.macro_f1.mean`. Tệp lựa chọn đã cố định (`frozen_selection.json`) sử dụng format 2 và ghi cùng `selection_metric`. Xếp hạng được tính lại từ ba seed của từng cấu hình và khớp hoàn toàn với bảng dưới đây. Kết quả của `seen_project` không tham gia lựa chọn. Chỉ khi các cấu hình có cùng giá trị Macro-F1 validation trung bình, mã nguồn mới áp dụng thứ tự ưu tiên B0, E1, D1, W1, H1, L1, N1. Không có trường hợp cùng giá trị Macro-F1 trong kết quả này.

| Hạng | ID | Macro-F1 validation project_wise chưa làm tròn |
| :--- | ---: | ---: |
| 1 | L1 | 0.06958665231149123 |
| 2 | H1 | 0.06321407529734191 |
| 3 | N1 | 0.0594369634345724 |
| 4 | W1 | 0.05590380480392897 |
| 5 | B0 | 0.05452052013497637 |
| 6 | D1 | 0.048967718905094514 |
| 7 | E1 | 0.043418551187484986 |

Cấu hình được lựa chọn và cố định là **L1**, lưu tại thư mục `L1`, với Macro-F1 validation trung bình trên project_wise là `0.06958665231149123`. Metadata trong tệp lựa chọn đã cố định trùng khớp với metadata của L1, bao gồm cấu hình, mã nguồn, môi trường, mã băm dữ liệu đầu vào và sáu checkpoint được khai báo. SHA-256 của tệp lựa chọn đã cố định là `47b7ae96a1918813aa37b36416492ce355045a8001a794857bc3a4bf9fa88900`, khớp với `frozen_selection_sha256` trong metadata của lần đánh giá test cuối.

Macro-F1 validation trung bình của L1 cao hơn B0 trong cùng môi trường khoảng **0,0151** trên project_wise (0,0696 so với 0,0545) và 0,0158 trên seen_project (0,1612 so với 0,1455). Macro-F1 validation trung bình của L1 cao hơn H1 một khoảng 0,0064; mức chênh này nhỏ hơn độ lệch chuẩn của cả hai cấu hình. Việc lựa chọn L1 tuân theo tiêu chí đã định, nhưng các chênh lệch quan sát được chưa đủ để kết luận về sự cải thiện ổn định hoặc có ý nghĩa thống kê. L1 được cố định trước khi đánh giá test và không được lựa chọn lại dựa trên kết quả test.

### Kết quả test của cấu hình L1 đã cố định — Kaggle Saved Version 3

Metadata của lần đánh giá test cuối ghi `config_id = L1`, dim 128, **2 lớp**, dropout 0,2, lr 1e-3, weight decay 1e-4 và `max_nodes = null`, với hai protocol và ba seed. Tệp kết quả có sáu dòng đánh giá test. Hàm `evaluate_saved` nạp checkpoint đã chọn theo validation, không huấn luyện lại hoặc chọn epoch dựa trên test. Lịch sử huấn luyện lưu kèm kết quả test trùng khớp từng byte với lịch sử của L1 trong giai đoạn tinh chỉnh. Các trường epoch, số tham số, thời gian huấn luyện và bộ nhớ CUDA cấp phát tối đa cũng khớp theo từng seed.

| Protocol | Seed | Macro-F1 | Weighted-F1 | MCC | Accuracy |
| :--- | ---: | ---: | ---: | ---: | ---: |
| project_wise | 42 | 0,0512 | 0,1009 | 0,0214 | 0,1004 |
| project_wise | 43 | 0,0520 | 0,0984 | 0,0295 | 0,1058 |
| project_wise | 44 | 0,0624 | 0,1272 | 0,0462 | 0,1303 |
| seen_project | 42 | 0,1074 | 0,1556 | 0,0870 | 0,1560 |
| seen_project | 43 | 0,0947 | 0,1481 | 0,0811 | 0,1520 |
| seen_project | 44 | 0,0978 | 0,1429 | 0,0798 | 0,1494 |

| Protocol | Macro-F1 | Weighted-F1 | MCC | Accuracy |
| :--- | ---: | ---: | ---: | ---: |
| project_wise | 0,0552 ± 0,0051 | 0,1088 ± 0,0130 | 0,0324 ± 0,0103 | 0,1122 ± 0,0130 |
| seen_project | 0,1000 ± 0,0054 | 0,1489 ± 0,0052 | 0,0826 ± 0,0032 | 0,1525 ± 0,0027 |

### So sánh với kết quả tham chiếu của Task 4.1a trên test

Kết quả tham chiếu của Task 4.1a được tính lại từ `4_1a_results/gnn_results.csv` (GCN, Graph A) và `baselines_results.csv`. Theo thiết kế validation-only, B0 trong Task 4.1b không được đánh giá trên test. Vì vậy, các giá trị test của Task 4.1a là kết quả tham chiếu từ thực nghiệm trước, không phải kết quả test của B0 trong Task 4.1b.

| Protocol / mô hình | Macro-F1 | Weighted-F1 | MCC | Accuracy |
| :--- | ---: | ---: | ---: | ---: |
| project_wise / GCN-A 4.1a | 0,0664 ± 0,0088 | 0,0897 ± 0,0331 | 0,0342 ± 0,0123 | 0,0905 ± 0,0253 |
| project_wise / L1 4.1b | 0,0552 ± 0,0051 | 0,1088 ± 0,0130 | 0,0324 ± 0,0103 | 0,1122 ± 0,0130 |
| project_wise / token_nodes 4.1a | 0,1000 ± 0,0000 | 0,1495 ± 0,0000 | 0,0868 ± 0,0000 | 0,1656 ± 0,0000 |
| project_wise / token_method 4.1a | 0,0875 ± 0,0000 | 0,1418 ± 0,0000 | 0,0727 ± 0,0000 | 0,1528 ± 0,0000 |
| seen_project / GCN-A 4.1a | 0,1033 ± 0,0051 | 0,1445 ± 0,0101 | 0,0837 ± 0,0087 | 0,1472 ± 0,0093 |
| seen_project / L1 4.1b | 0,1000 ± 0,0054 | 0,1489 ± 0,0052 | 0,0826 ± 0,0032 | 0,1525 ± 0,0027 |
| seen_project / token_nodes 4.1a | 0,1541 ± 0,0000 | 0,1932 ± 0,0000 | 0,1332 ± 0,0000 | 0,1966 ± 0,0000 |
| seen_project / token_method 4.1a | 0,1701 ± 0,0000 | 0,2073 ± 0,0000 | 0,1505 ± 0,0000 | 0,2110 ± 0,0000 |

Macro-F1 test của L1 thấp hơn GCN-A trong Task 4.1a ở cả hai protocol: thấp hơn 0,0112 ở project_wise (0,0552 so với 0,0664) và 0,0033 ở seen_project (0,1000 so với 0,1033). Chênh lệch trên seen_project nhỏ hơn mức dao động giữa các seed. Trên project_wise, L1 có Weighted-F1 và accuracy cao hơn, nhưng MCC thấp hơn nhẹ so với GCN-A trong Task 4.1a. Giá trị cao hơn của các chỉ số chịu ảnh hưởng của phân bố lớp không đồng nghĩa với sự cải thiện đồng đều trên 23 CWE.

Cả hai baseline token có Macro-F1 test cao hơn L1 ở cả hai protocol. Trong kết quả tham chiếu của Task 4.1a, token_nodes đạt 0,1000 trên project_wise và token_method đạt 0,1701 trên seen_project. Macro-F1 của L1 thấp hơn các giá trị tương ứng lần lượt 0,0448 và 0,0701. Các lần chạy baseline token cho kết quả giống nhau ở ba seed nên có độ lệch chuẩn bằng 0; điều này không có nghĩa là bất định về khả năng tổng quát hóa bằng 0.

## 3. Nhận xét

### Kết quả validation theo cấu hình

- **B0:** cấu hình này được huấn luyện đủ sáu lần với cùng phiên bản mã nguồn và môi trường như các biến thể. Trên project_wise, Macro-F1 validation của B0 là 0,0545 ± 0,0081, so với 0,0493 ± 0,0012 của GCN-A trong Task 4.1a. Trên seen_project, các giá trị tương ứng là 0,1455 ± 0,0035 và 0,1472 ± 0,0191. Kết quả huấn luyện lại không thay thế kết quả tham chiếu của Task 4.1a. Task 4.1a ghi commit `f7e0629`, còn giai đoạn tinh chỉnh sử dụng `5d8b99e...`. Các mô tả dữ liệu tương ứng, nhưng các tệp kết quả 4.1a không có đầy đủ metadata và mã băm để xác nhận môi trường tương đương hoặc dữ liệu trùng khớp từng byte.
- **E1:** cấu hình này có Macro-F1 validation thấp hơn B0 ở cả hai protocol. Trên project_wise, E1 dừng ở epoch 9 với cả ba seed; validation loss đạt giá trị thấp nhất ở epoch 1 rồi không cải thiện trong tám epoch tiếp theo. Với thứ tự seed 42/43/44, epoch dừng trên seen_project là 12/11/9 và epoch có validation loss thấp nhất là 4/3/1. Epoch chọn checkpoint theo Macro-F1 validation lần lượt là 6/9/5 trên project_wise và 9/9/8 trên seen_project. Kết quả chưa hỗ trợ giả thuyết về lợi ích của tiêu chí dừng ít nhạy với nhiễu; E1 thay đổi tiêu chí early stopping, không làm mượt Macro-F1.
- **D1:** Macro-F1 validation trên project_wise là 0,0490, thấp hơn B0; trên seen_project, giá trị này là 0,1539, cao hơn B0. Kết quả không cho thấy sự cải thiện trên protocol chính.
- **W1:** Macro-F1 validation trung bình của W1 trên project_wise cao hơn B0 0,0014; chênh lệch này nhỏ so với độ lệch chuẩn giữa các seed. Trên seen_project, W1 đạt 0,1600. Chưa đủ bằng chứng để kết luận về sự cải thiện ổn định.
- **H1:** cấu hình này đạt Macro-F1 validation cao thứ hai trên project_wise (0,0632), với độ lệch chuẩn 0,0108. So với B0, H1 có số tham số và bộ nhớ CUDA cấp phát tối đa thấp hơn. Các phép đo này cho thấy yêu cầu tài nguyên thấp hơn, nhưng không chứng minh mô hình ít ghi nhớ dữ liệu huấn luyện hơn.
- **L1:** trong bảy cấu hình được đánh giá, L1 có Macro-F1 validation trung bình cao nhất ở cả hai protocol. Kết quả phù hợp với giả thuyết giảm số lớp, nhưng chưa chứng minh cơ chế này: thí nghiệm không đo trực tiếp hiện tượng các biểu diễn node trở nên quá tương đồng sau nhiều bước lan truyền (oversmoothing), cũng không có thí nghiệm tách riêng tác động của từng thành phần (ablation). Macro-F1 test của L1 thấp hơn GCN-A trong Task 4.1a.
- **N1:** Macro-F1 validation trung bình trên project_wise là 0,0594, cao hơn B0 0,0049; chênh lệch nằm trong mức dao động giữa các seed. Bộ nhớ CUDA cấp phát tối đa của N1 thấp hơn B0. Thí nghiệm kiểm tra độ nhạy với việc cắt graph, chưa đủ để kết luận ngưỡng 1.000 node là tối ưu hoặc graph lớn gây nhiễu. Số mẫu validation không thay đổi: 762/764, tương ứng với project_wise/seen_project.

### Per-CWE và mất cân bằng lớp

Bảng dưới trình bày F1 theo CWE của lần đánh giá test cuối từ `per_class.csv`, dưới dạng trung bình ± độ lệch chuẩn trên ba seed. Support là số mẫu test của mỗi seed, không phải tổng số mẫu qua các seed. Tệp có 23 lớp × 2 protocol × 3 seed = 138 dòng. Trung bình không trọng số và trung bình có trọng số theo support của F1 từng lớp khớp lần lượt với Macro-F1 và Weighted-F1 trong `results.csv`.

| CWE | Support project_wise | F1 project_wise | Support seen_project | F1 seen_project |
| :--- | ---: | ---: | ---: | ---: |
| CWE-119 | 109 | 0,1473 ± 0,0468 | 55 | 0,1962 ± 0,0240 |
| CWE-120 | 24 | 0,0104 ± 0,0147 | 13 | 0,0190 ± 0,0269 |
| CWE-125 | 87 | 0,0912 ± 0,0295 | 98 | 0,2655 ± 0,0285 |
| CWE-189 | 27 | 0,0000 ± 0,0000 | 23 | 0,0222 ± 0,0314 |
| CWE-190 | 92 | 0,1350 ± 0,0421 | 41 | 0,2169 ± 0,0203 |
| CWE-20 | 94 | 0,0876 ± 0,0274 | 77 | 0,1385 ± 0,0049 |
| CWE-200 | 30 | 0,0416 ± 0,0069 | 34 | 0,1073 ± 0,0189 |
| CWE-22 | 8 | 0,1485 ± 0,0174 | 13 | 0,0639 ± 0,0486 |
| CWE-264 | 6 | 0,0000 ± 0,0000 | 18 | 0,0580 ± 0,0820 |
| CWE-295 | 9 | 0,0303 ± 0,0429 | 9 | 0,1032 ± 0,0736 |
| CWE-369 | 13 | 0,0000 ± 0,0000 | 13 | 0,1928 ± 0,0226 |
| CWE-399 | 57 | 0,0426 ± 0,0324 | 28 | 0,1641 ± 0,0682 |
| CWE-400 | 5 | 0,0000 ± 0,0000 | 18 | 0,0000 ± 0,0000 |
| CWE-401 | 4 | 0,0000 ± 0,0000 | 13 | 0,0670 ± 0,0494 |
| CWE-415 | 13 | 0,0000 ± 0,0000 | 16 | 0,0000 ± 0,0000 |
| CWE-416 | 32 | 0,0208 ± 0,0295 | 63 | 0,1386 ± 0,0704 |
| CWE-476 | 125 | 0,1689 ± 0,0853 | 63 | 0,1150 ± 0,0124 |
| CWE-59 | 9 | 0,0256 ± 0,0363 | 9 | 0,0000 ± 0,0000 |
| CWE-617 | 10 | 0,0208 ± 0,0295 | 9 | 0,1157 ± 0,0910 |
| CWE-703 | 46 | 0,0639 ± 0,0161 | 32 | 0,0334 ± 0,0255 |
| CWE-770 | 4 | 0,0175 ± 0,0248 | 8 | 0,0000 ± 0,0000 |
| CWE-787 | 122 | 0,2180 ± 0,0251 | 101 | 0,2329 ± 0,0328 |
| CWE-835 | 10 | 0,0000 ± 0,0000 | 9 | 0,0494 ± 0,0698 |

- Trên project_wise, support mỗi lớp nằm trong khoảng 4 đến 125; CWE-401 và CWE-770 chỉ có 4 mẫu mỗi lớp. F1 trung bình bằng 0 ở **7/23 lớp**: CWE-189, CWE-264, CWE-369, CWE-400, CWE-401, CWE-415 và CWE-835. CWE-22 đạt F1 0,1485 nhưng chỉ có 8 mẫu, nên khả năng suy rộng từ kết quả này còn hạn chế.
- CWE-787 (122 mẫu, F1 0,2180), CWE-476 (125, 0,1689) và CWE-119 (109, 0,1473) có F1 cao hơn nhiều lớp có ít mẫu. F1 của ba lớp này cao hơn các giá trị tham chiếu của GCN-A trong Task 4.1a, lần lượt là 0,1062/0,1074/0,0744. Ngược lại, F1 của L1 thấp hơn ở CWE-189 (0,0735 → 0), CWE-703 (0,1444 → 0,0639) và CWE-190 (0,1899 → 0,1350); mũi tên biểu thị giá trị của GCN-A 4.1a → L1. Xu hướng này phù hợp với việc L1 có Weighted-F1 cao hơn nhưng Macro-F1 thấp hơn kết quả tham chiếu.
- Trên seen_project, support mỗi lớp nằm trong khoảng 8 đến 101. F1 bằng 0 ở **4/23 lớp**: CWE-400, CWE-415, CWE-59 và CWE-770. Các lớp có F1 cao nhất là CWE-125 (0,2655), CWE-787 (0,2329) và CWE-190 (0,2169). Kết quả cho thấy nhiều lớp ít mẫu vẫn có F1 thấp khi sử dụng loss có trọng số lớp; chưa có thí nghiệm riêng để xác định tác động của cơ chế trọng số.
- Confusion matrix chỉ được lưu cho **seed 42**, với một ma trận 23 × 23 cho mỗi protocol. Trên project_wise, các cặp CWE-119 → CWE-703, CWE-787 → CWE-119 và CWE-476 → CWE-787 có số mẫu lần lượt là 28, 27 và 20. Trên seen_project, CWE-125 → CWE-787 có 29 mẫu và CWE-416 → CWE-787 có 17 mẫu. Các số liệu này thuộc riêng seed 42, không phải tổng của ba seed. Không có ma trận seed 43/44 để đánh giá độ ổn định của từng kiểu nhầm lẫn.

### Thời gian huấn luyện, bộ nhớ CUDA và số tham số

Bảng dưới sử dụng số liệu giai đoạn tinh chỉnh trong Version 2, dưới dạng trung bình ± độ lệch chuẩn trên ba seed. Trường `peak_gpu_mb` đo **bộ nhớ CUDA cấp phát tối đa**, đơn vị MiB (`max_memory_allocated / 2**20`), không phải toàn bộ VRAM của tiến trình hay bộ nhớ CUDA được dành sẵn (reserved). Trường `train_seconds` đo thời gian huấn luyện, bao gồm đánh giá validation và chọn checkpoint, không phải toàn bộ thời lượng phiên Kaggle. Kết quả test cuối kế thừa thời gian huấn luyện của L1, **không phải thời gian chạy test Version 3**.

| ID / protocol | Giây/seed | Peak CUDA MiB | Tham số |
| :--- | ---: | ---: | ---: |
| B0 / project_wise | 104,7 ± 34,9 | 802,6 ± 69,8 | 3307799 |
| B0 / seen_project | 147,1 ± 12,5 | 866,7 ± 16,1 | 3384471 |
| E1 / project_wise | 37,0 ± 0,2 | 730,6 ± 64,2 | 3307799 |
| E1 / seen_project | 46,5 ± 5,5 | 866,9 ± 16,0 | 3384471 |
| D1 / project_wise | 90,3 ± 4,6 | 782,6 ± 26,6 | 3307799 |
| D1 / seen_project | 149,5 ± 23,1 | 907,4 ± 53,1 | 3384471 |
| W1 / project_wise | 80,5 ± 15,9 | 770,2 ± 38,8 | 3307799 |
| W1 / seen_project | 139,6 ± 18,7 | 866,7 ± 16,1 | 3384471 |
| H1 / project_wise | 91,8 ± 7,8 | 425,1 ± 23,5 | 1633431 |
| H1 / seen_project | 110,9 ± 10,3 | 468,2 ± 26,9 | 1671767 |
| L1 / project_wise | 74,0 ± 5,3 | 772,6 ± 35,9 | 3291287 |
| L1 / seen_project | 138,5 ± 4,9 | 907,0 ± 53,0 | 3367959 |
| N1 / project_wise | 88,5 ± 19,8 | 415,4 ± 8,0 | 3307799 |
| N1 / seen_project | 122,1 ± 19,8 | 443,7 ± 10,8 | 3384471 |

Tổng thời gian huấn luyện ghi trong 42 dòng kết quả của giai đoạn tinh chỉnh là **4.262,7 giây (71,0 phút)**; các trường thời gian sao kèm kết quả test cuối không được cộng thêm. Trên project_wise, thời gian huấn luyện trung bình của L1 thấp hơn B0 khoảng 29,4%, còn số tham số thấp hơn 16.512 (khoảng 0,5%). Phần embedding chiếm phần lớn số tham số của mô hình. Trên seen_project, bộ nhớ CUDA cấp phát tối đa trung bình của L1 cao hơn B0 (907,0 so với 866,7 MiB), nên chưa thể kết luận giảm số lớp luôn làm giảm đại lượng này. H1 có số tham số thấp hơn B0 gần một nửa. Bộ nhớ CUDA cấp phát tối đa trung bình của N1 là 415,4/443,7 MiB, thấp hơn B0 là 802,6/866,7 MiB, theo thứ tự project_wise/seen_project. Thời gian huấn luyện phụ thuộc số epoch thực tế; đây không phải phép đo tốc độ với số epoch cố định.

### Lịch sử huấn luyện

Mỗi cấu hình có sáu lịch sử huấn luyện. Trường `epochs_run` ghi số epoch thực tế và khớp với độ dài lịch sử; `best_epoch` là epoch sớm nhất đạt Macro-F1 validation cao nhất. Bảng dưới trình bày kết quả L1 theo thứ tự seed 42/43/44:

| Protocol | Macro-F1 validation từng seed | Best epoch | Epoch đã chạy |
| :--- | ---: | ---: | ---: |
| project_wise | 0,078736 / 0,056971 / 0,073053 | 12 / 15 / 12 | 20 / 23 / 20 |
| seen_project | 0,162003 / 0,174855 / 0,146874 | 30 / 31 / 28 | 38 / 39 / 36 |

Trên project_wise, loss train ban đầu của L1 xấp xỉ 3,13; giá trị ở epoch cuối lần lượt là 0,4748/0,4139/0,5192 theo thứ tự seed 42/43/44. Macro-F1 validation ở epoch cuối là 0,0678/0,0427/0,0468, thấp hơn giá trị tại checkpoint được chọn là 0,0787/0,0570/0,0731. Trên seen_project, loss train cuối là 0,1708/0,1709/0,1992; Macro-F1 validation cuối là 0,1525/0,1463/0,1407, thấp hơn giá trị được chọn là 0,1620/0,1749/0,1469, với cùng thứ tự seed. Loss train giảm theo epoch nhưng Macro-F1 validation không cải thiện tương ứng. Chưa thể tách riêng ảnh hưởng của việc ghi nhớ dữ liệu huấn luyện, lệch phân bố và giới hạn biểu diễn. Chỉ E1 lưu `val_loss`; không suy diễn diễn biến validation loss cho các cấu hình khác.

## 4. Giới hạn

- **Validation và test:** L1 đạt Macro-F1 validation trung bình cao nhất trên project_wise, nhưng có Macro-F1 test thấp hơn GCN-A trong Task 4.1a. Chỉ cấu hình đã lựa chọn và cố định được đánh giá test; kết quả test không được dùng để xếp hạng lại các ứng viên.
- **Ngân sách và bất định:** thí nghiệm gồm bảy cấu hình, ba seed và một cách phân chia dữ liệu cố định cho mỗi protocol. Chưa có kiểm định ý nghĩa thống kê hoặc khoảng tin cậy. Việc lựa chọn trên cùng tập validation có thể dẫn đến đánh giá lạc quan; chênh lệch nhỏ so với dao động giữa các seed chưa đủ để kết luận về sự cải thiện ổn định.
- **Dữ liệu và phạm vi:** mất cân bằng lớp, lớp hiếm, lệch phân bố trên project_wise và dữ liệu đầu vào trùng trên seen_project có thể ảnh hưởng đến kết quả. Task này chỉ đánh giá Graph A; Graph B được dành cho Task 4.1c. Thí nghiệm chưa xét mô hình văn bản mạnh hoặc kết hợp các thay đổi siêu tham số, nên chưa đủ bằng chứng để kết luận về việc biểu diễn graph không mang lại lợi ích.

## 5. Kết luận

Trong bảy cấu hình được đánh giá, L1 (GCN-A **2 lớp**, dim 128, dropout 0,2, không giới hạn số node) được lựa chọn vì đạt Macro-F1 validation trung bình cao nhất trên project_wise: **0,0696 ± 0,0092**, so với **0,0545 ± 0,0081** của B0 trong cùng môi trường. Cấu hình được lựa chọn trong Version 2 đã được cố định trước lần đánh giá test cuối ở Version 3 và được giữ nguyên cho Task 4.1c.

Trên test, L1 đạt Macro-F1 **0,0552 ± 0,0051** trên project_wise và **0,1000 ± 0,0054** trên seen_project. Các giá trị này thấp hơn kết quả tương ứng của GCN-A và các baseline token trong Task 4.1a. Riêng đối với `seen_project`, chênh lệch Macro-F1 giữa L1 và GCN-A của Task 4.1a nhỏ hơn độ lệch chuẩn giữa các seed, nên chưa đủ cơ sở để kết luận về sự khác biệt hiệu quả một cách ổn định. Việc lựa chọn L1 tuân thủ tiêu chí validation đã định trong phạm vi bảy cấu hình; tuy nhiên, kết quả test không cho thấy sự cải thiện khả năng tổng quát hóa. Cấu hình L1 được giữ nguyên để đánh giá Graph B trong Task 4.1c, với các giới hạn về dữ liệu và provenance tiếp tục được xem xét khi diễn giải.
## 6. Task 4.1c — Đánh giá GCN trên Graph B

### 6.1. Thiết lập thực nghiệm

Graph A chỉ có cạnh AST; Graph B bổ sung cạnh luồng điều khiển (CFG) và phụ thuộc dữ liệu (`DATA_DEP`) trên cùng tập node và đặc trưng. GCN đối xứng hóa cạnh, thêm self-loop và không phân biệt loại cạnh.

Giữ nguyên L1 đã chọn bằng Macro-F1 validation trung bình của `project_wise` trên Graph A trong Task 4.1b: dim 128, 2 lớp GCN, dropout 0,2, AdamW với learning rate 1e-3, weight decay 1e-4, batch size 32, tối đa 40 epoch và patience 8. Dùng cùng dataset processed version 1, vocabulary, split, 23 nhãn CWE và seed 42/43/44 cho hai protocol; giữ loss có trọng số lớp, gradient clipping 5,0, tổng hợp mean+max và không giới hạn mẫu/node.

Sáu mô hình Graph B được khởi tạo mới và huấn luyện từ đầu, không dùng trọng số Graph A hoặc tìm kiếm lại cấu hình. Early stopping theo Macro-F1 validation; chọn checkpoint có giá trị chưa làm tròn cao nhất, giữ epoch sớm nhất nếu bằng nhau. Mỗi mô hình được đánh giá test sau khi chọn checkpoint, không dùng test để chọn cấu hình hoặc epoch.

### 6.2. Kết quả và so sánh Graph A/B

Cả hai graph dùng L1. Bảng trình bày trung bình ± độ lệch chuẩn tổng thể trên ba seed (`ddof = 0`), tính từ CSV chưa làm tròn; Macro-F1 bao gồm đủ 23 nhãn CWE.

| Protocol | Graph | Macro-F1 test | Thời gian huấn luyện (giây/seed) | CUDA cấp phát tối đa (MiB) |
| :--- | :--- | ---: | ---: | ---: |
| project_wise | A | 0,0552 ± 0,0051 | 74,0 ± 5,3 | 772,6 ± 35,9 |
| project_wise | B | 0,0650 ± 0,0049 | 130,7 ± 9,6 | 1362,0 ± 60,7 |
| seen_project | A | 0,1000 ± 0,0054 | 138,5 ± 4,9 | 907,0 ± 53,0 |
| seen_project | B | 0,1026 ± 0,0161 | 183,9 ± 18,1 | 1256,5 ± 46,3 |

`train_seconds` gồm train và validation theo epoch, không gồm đánh giá cuối; `peak_gpu_mb` đo đỉnh CUDA cấp phát, không phải toàn bộ VRAM. Graph A ghi đỉnh bộ nhớ trong lần train chỉ có validation, còn Graph B ghi sau train và đánh giá validation/test, nên chênh lệch bộ nhớ không tách riêng chi phí huấn luyện.

### 6.3. Nhận xét và kết luận

Graph B có Macro-F1 test trung bình cao hơn Graph A khoảng **0,0098** trên `project_wise` và **0,0026** trên `seen_project`. Chênh lệch `project_wise` lớn hơn độ lệch chuẩn của từng nhóm nhưng không chứng minh ý nghĩa thống kê; chênh lệch `seen_project` nhỏ hơn độ lệch chuẩn Graph B (0,0161), nên chưa đủ bằng chứng kết luận Graph B tốt hơn.

Thời gian huấn luyện trung bình của Graph B cao hơn lần lượt 56,7 giây/seed (76,7%) và 45,4 giây/seed (32,8%); đỉnh CUDA cấp phát cao hơn 589,5 MiB và 349,5 MiB theo thứ tự hai protocol. Thời gian phụ thuộc số epoch thực tế, không phải so sánh với ngân sách epoch cố định.

Với L1, bổ sung CFG/DATA_DEP cho Macro-F1 trung bình quan sát được cao hơn nhưng tốn thời gian hơn; Weighted-F1, MCC và Accuracy thấp hơn. Chỉ có ba seed và một split cố định mỗi protocol, nên chưa thể kết luận Graph B cải thiện GCN một cách ổn định hoặc phổ quát. Giới hạn dữ liệu Task 4.0 vẫn áp dụng, gồm 5 mẫu validation và 6 mẫu test của `seen_project` trùng input với train.

Bằng chứng: Graph A — [notebook tuning](4_1b_gcn_tuning_run.ipynb), [log tuning](4_1b_results/tuning/4-1b-gcn-tuning.log), [notebook test](4_1b_gcn_final_run.ipynb), [log test](4_1b_results/final/4-1b-gcn-tuning.log), [CSV](4_1b_results/final/results.csv); Graph B — [notebook đã chạy](4_1c_gcn_graph_b_run.ipynb), [log](4_1c_results/graph_b.log), [CSV](4_1c_results/L1/results.csv).

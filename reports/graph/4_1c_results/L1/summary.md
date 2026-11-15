# Kết quả GNN (Task 4.1a)

Trung bình ± độ lệch chuẩn theo seed.

| Protocol | Graph | Model | Split | Macro-F1 | Weighted-F1 | MCC | Accuracy | Tham số | Giây/seed |
| :--- | :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| project_wise | graph_b | gcn | test | 0.0650 ± 0.0049 | 0.1069 ± 0.0057 | 0.0307 ± 0.0076 | 0.1058 ± 0.0075 | 3291287 | 131 |
| project_wise | graph_b | gcn | validation | 0.0663 ± 0.0084 | 0.1481 ± 0.0141 | 0.0364 ± 0.0103 | 0.1304 ± 0.0078 | 3291287 | 131 |
| seen_project | graph_b | gcn | test | 0.1026 ± 0.0161 | 0.1387 ± 0.0152 | 0.0730 ± 0.0152 | 0.1402 ± 0.0149 | 3367959 | 184 |
| seen_project | graph_b | gcn | validation | 0.1505 ± 0.0055 | 0.1972 ± 0.0103 | 0.1297 ± 0.0107 | 0.1928 ± 0.0134 | 3367959 | 184 |

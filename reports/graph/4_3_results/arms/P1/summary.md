# Kết quả GNN (Task 4.1a)

Trung bình ± độ lệch chuẩn theo seed.

| Protocol | Graph | Model | Split | Macro-F1 | Weighted-F1 | MCC | Accuracy | Tham số | Giây/seed |
| :--- | :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| project_wise | graph_b | ggnn | test | 0.0532 ± 0.0025 | 0.0939 ± 0.0180 | 0.0413 ± 0.0050 | 0.0994 ± 0.0206 | 3456407 | 126 |
| project_wise | graph_b | ggnn | validation | 0.0637 ± 0.0028 | 0.1126 ± 0.0014 | 0.0334 ± 0.0080 | 0.1059 ± 0.0118 | 3456407 | 126 |
| seen_project | graph_b | ggnn | test | 0.1188 ± 0.0155 | 0.1508 ± 0.0149 | 0.0859 ± 0.0148 | 0.1512 ± 0.0158 | 3533079 | 232 |
| seen_project | graph_b | ggnn | validation | 0.1676 ± 0.0037 | 0.2148 ± 0.0070 | 0.1433 ± 0.0079 | 0.2055 ± 0.0085 | 3533079 | 232 |

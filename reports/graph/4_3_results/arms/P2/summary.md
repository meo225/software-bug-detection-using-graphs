# Kết quả GNN (Task 4.1a)

Trung bình ± độ lệch chuẩn theo seed.

| Protocol | Graph | Model | Split | Macro-F1 | Weighted-F1 | MCC | Accuracy | Tham số | Giây/seed |
| :--- | :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| project_wise | graph_b | ggnn | test | 0.0532 ± 0.0097 | 0.0948 ± 0.0158 | 0.0296 ± 0.0047 | 0.1015 ± 0.0109 | 3456407 | 158 |
| project_wise | graph_b | ggnn | validation | 0.0668 ± 0.0167 | 0.1115 ± 0.0219 | 0.0300 ± 0.0079 | 0.1102 ± 0.0130 | 3456407 | 158 |
| seen_project | graph_b | ggnn | test | 0.1045 ± 0.0009 | 0.1506 ± 0.0081 | 0.0888 ± 0.0078 | 0.1555 ± 0.0081 | 3533079 | 237 |
| seen_project | graph_b | ggnn | validation | 0.1475 ± 0.0005 | 0.1948 ± 0.0020 | 0.1258 ± 0.0012 | 0.1889 ± 0.0027 | 3533079 | 237 |

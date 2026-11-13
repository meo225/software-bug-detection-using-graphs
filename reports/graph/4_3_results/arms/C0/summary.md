# Kết quả GNN (Task 4.1a)

Trung bình ± độ lệch chuẩn theo seed.

| Protocol | Graph | Model | Split | Macro-F1 | Weighted-F1 | MCC | Accuracy | Tham số | Giây/seed |
| :--- | :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| project_wise | graph_b | ggnn | test | 0.0520 ± 0.0099 | 0.0796 ± 0.0239 | 0.0178 ± 0.0037 | 0.0819 ± 0.0214 | 3456407 | 196 |
| project_wise | graph_b | ggnn | validation | 0.0603 ± 0.0108 | 0.1424 ± 0.0183 | 0.0472 ± 0.0199 | 0.1260 ± 0.0201 | 3456407 | 196 |
| seen_project | graph_b | ggnn | test | 0.1026 ± 0.0065 | 0.1504 ± 0.0032 | 0.0871 ± 0.0074 | 0.1516 ± 0.0065 | 3533079 | 257 |
| seen_project | graph_b | ggnn | validation | 0.1585 ± 0.0043 | 0.2113 ± 0.0036 | 0.1401 ± 0.0016 | 0.2020 ± 0.0016 | 3533079 | 257 |

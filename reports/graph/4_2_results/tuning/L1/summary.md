# Kết quả GGNN graph_b (cấu hình L1)

Trung bình ± độ lệch chuẩn theo seed.

| Protocol | Graph | Model | Split | Macro-F1 | Weighted-F1 | MCC | Accuracy | Tham số | Giây/seed |
| :--- | :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| project_wise | graph_b | ggnn | validation | 0.0616 ± 0.0119 | 0.1025 ± 0.0163 | 0.0221 ± 0.0123 | 0.0954 ± 0.0151 | 3456407 | 167 |
| seen_project | graph_b | ggnn | validation | 0.1603 ± 0.0014 | 0.2156 ± 0.0088 | 0.1463 ± 0.0086 | 0.2064 ± 0.0064 | 3533079 | 247 |

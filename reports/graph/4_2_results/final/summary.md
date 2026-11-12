# Kết quả GGNN graph_b (cấu hình L1)

Trung bình ± độ lệch chuẩn theo seed.

| Protocol | Graph | Model | Split | Macro-F1 | Weighted-F1 | MCC | Accuracy | Tham số | Giây/seed |
| :--- | :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| project_wise | graph_b | ggnn | test | 0.0579 ± 0.0106 | 0.1043 ± 0.0090 | 0.0292 ± 0.0039 | 0.1075 ± 0.0048 | 3456407 | 167 |
| seen_project | graph_b | ggnn | test | 0.0930 ± 0.0130 | 0.1324 ± 0.0166 | 0.0686 ± 0.0194 | 0.1354 ± 0.0181 | 3533079 | 247 |

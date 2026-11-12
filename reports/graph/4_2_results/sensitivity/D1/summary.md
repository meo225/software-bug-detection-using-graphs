# Kết quả GGNN graph_b (cấu hình D1), độ nhạy trên test, không dùng để chọn cấu hình

Trung bình ± độ lệch chuẩn theo seed.

| Protocol | Graph | Model | Split | Macro-F1 | Weighted-F1 | MCC | Accuracy | Tham số | Giây/seed |
| :--- | :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| project_wise | graph_b | ggnn | test | 0.0512 ± 0.0126 | 0.0897 ± 0.0195 | 0.0258 ± 0.0076 | 0.0951 ± 0.0083 | 3456407 | 214 |
| seen_project | graph_b | ggnn | test | 0.0945 ± 0.0096 | 0.1352 ± 0.0117 | 0.0732 ± 0.0161 | 0.1420 ± 0.0150 | 3533079 | 352 |

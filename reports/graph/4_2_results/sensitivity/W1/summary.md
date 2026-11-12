# Kết quả GGNN graph_b (cấu hình W1), độ nhạy trên test, không dùng để chọn cấu hình

Trung bình ± độ lệch chuẩn theo seed.

| Protocol | Graph | Model | Split | Macro-F1 | Weighted-F1 | MCC | Accuracy | Tham số | Giây/seed |
| :--- | :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| project_wise | graph_b | ggnn | test | 0.0623 ± 0.0122 | 0.0995 ± 0.0203 | 0.0287 ± 0.0136 | 0.0969 ± 0.0197 | 3456407 | 199 |
| seen_project | graph_b | ggnn | test | 0.1083 ± 0.0034 | 0.1516 ± 0.0085 | 0.0873 ± 0.0080 | 0.1538 ± 0.0061 | 3533079 | 375 |

# Kết quả codebert trên văn bản hàm (Task 4.5)

Trung bình ± độ lệch chuẩn theo seed.

| Protocol | Model | Split | Macro-F1 | Weighted-F1 | MCC | Accuracy | Tham số | Giây/seed |
| :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| project_wise | codebert | test | 0.1008 ± 0.0042 | 0.1637 ± 0.0195 | 0.0930 ± 0.0210 | 0.1788 ± 0.0202 | 124663319 | 2823 |
| project_wise | codebert | validation | 0.0709 ± 0.0108 | 0.1697 ± 0.0384 | 0.0590 ± 0.0309 | 0.1662 ± 0.0335 | 124663319 | 2823 |
| seen_project | codebert | test | 0.1358 ± 0.0038 | 0.1915 ± 0.0071 | 0.1293 ± 0.0034 | 0.1970 ± 0.0038 | 124663319 | 3424 |
| seen_project | codebert | validation | 0.2037 ± 0.0067 | 0.2546 ± 0.0063 | 0.1889 ± 0.0062 | 0.2531 ± 0.0043 | 124663319 | 3424 |

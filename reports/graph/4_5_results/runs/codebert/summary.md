# Kết quả codebert trên văn bản hàm (Task 4.5)

Trung bình ± độ lệch chuẩn theo seed.

| Protocol | Model | Split | Macro-F1 | Weighted-F1 | MCC | Accuracy | Tham số | Giây/seed |
| :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| project_wise | codebert | test | 0.0813 ± 0.0269 | 0.1316 ± 0.0186 | 0.0690 ± 0.0165 | 0.1578 ± 0.0140 | 124663319 | 1759 |
| project_wise | codebert | validation | 0.0677 ± 0.0105 | 0.1375 ± 0.0431 | 0.0543 ± 0.0193 | 0.1404 ± 0.0334 | 124663319 | 1759 |
| seen_project | codebert | test | 0.1458 ± 0.0153 | 0.1987 ± 0.0119 | 0.1385 ± 0.0098 | 0.2036 ± 0.0092 | 124663319 | 2398 |
| seen_project | codebert | validation | 0.1868 ± 0.0095 | 0.2378 ± 0.0133 | 0.1699 ± 0.0138 | 0.2312 ± 0.0139 | 124663319 | 2398 |

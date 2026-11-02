# Báo cáo kết quả trích xuất đồ thị cho tập mẫu DiverseVul Task 3.3

Phiên bản Joern: 4.0.654 (các lần chạy đầu không ghim phiên bản)
Schema: configs/graph/schema_spec.yaml

## 1. Nguyên tắc bảo toàn mẫu

Thực hiện trích xuất hai biểu diễn đồ thị cho 9.077 hàm:
- Graph A: đồ thị cây cú pháp trừu tượng AST
- Graph B: đồ thị ngữ nghĩa kết hợp AST, luồng điều khiển CFG và phụ thuộc dữ liệu DATA_DEP

Số lượng hàm thành công cộng số lượng hàm bị loại: 7799 + 1278 = 9077 trên 9077

- Tổng số đồ thị hợp lệ: 7799 trên 9077
- Số lượng đồ thị vượt ngưỡng kích thước: 997
- Tổng số mẫu bị loại: 1278 trên 9077
- Tỷ lệ bao phủ: 100%

## 2. Thống kê theo 23 lớp CWE

| CWE | Tổng số mẫu | Số lượng thành công | Tỷ lệ thành công | Số lượng bị loại |
| :--- | ---: | ---: | ---: | ---: |
| CWE-119 | 697 | 590 | 84.65% | 107 |
| CWE-120 | 145 | 109 | 75.17% | 36 |
| CWE-125 | 1101 | 945 | 85.83% | 156 |
| CWE-189 | 255 | 232 | 90.98% | 23 |
| CWE-190 | 441 | 382 | 86.62% | 59 |
| CWE-20 | 873 | 739 | 84.65% | 134 |
| CWE-200 | 500 | 434 | 86.80% | 66 |
| CWE-22 | 129 | 103 | 79.84% | 26 |
| CWE-264 | 209 | 176 | 84.21% | 33 |
| CWE-295 | 98 | 97 | 98.98% | 1 |
| CWE-369 | 136 | 128 | 94.12% | 8 |
| CWE-399 | 329 | 308 | 93.62% | 21 |
| CWE-400 | 179 | 127 | 70.95% | 52 |
| CWE-401 | 184 | 159 | 86.41% | 25 |
| CWE-415 | 191 | 147 | 76.96% | 44 |
| CWE-416 | 751 | 643 | 85.62% | 108 |
| CWE-476 | 736 | 663 | 90.08% | 73 |
| CWE-59 | 93 | 88 | 94.62% | 5 |
| CWE-617 | 102 | 94 | 92.16% | 8 |
| CWE-703 | 362 | 315 | 87.02% | 47 |
| CWE-770 | 89 | 76 | 85.39% | 13 |
| CWE-787 | 1368 | 1156 | 84.50% | 212 |
| CWE-835 | 109 | 88 | 80.73% | 21 |

## 3. Thống kê kích thước đồ thị

| Đại lượng | Nhỏ nhất | Trung vị | Trung bình | Lớn nhất | Tổng số |
| :--- | ---: | ---: | ---: | ---: | ---: |
| Node dùng chung | 3 | 166 | 358.0 | 9514 | 2792043 |
| Cạnh Graph A AST | 2 | 165 | 357.0 | 9513 | 2784244 |
| Cạnh CFG Graph B | 1 | 140 | 320.7 | 8901 | 2500900 |
| Cạnh DATA_DEP Graph B | 0 | 321 | 1030.9 | 58365 | 8040267 |
| Tổng cạnh Graph B | 3 | 630 | 1708.6 | 64599 | 13325411 |

## 4. Phân loại các trường hợp bị loại

- AST_EXTRACTION_ERROR: 647 mẫu
- METHOD_RESOLUTION_ERROR: 595 mẫu
- QUARANTINED: 3 mẫu
- UNSUPPORTED_SOURCE_REPRESENTATION: 32 mẫu
- TIMEOUT_ERROR: 1 mẫu

## 5. Kết luận nghiệm thu

Toàn bộ 9.077 mẫu đã được đối chiếu và bảo toàn đầy đủ. Đủ điều kiện nghiệm thu chuyển giao sang Phase 4.

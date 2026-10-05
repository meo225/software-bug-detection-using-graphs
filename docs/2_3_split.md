# Task 2.3: Split DiverseVul chống leakage

**Quyết định:** mọi model dùng chung 9.077 function của task 2.2 và hai cách chia dưới đây. Không tạo split mới khi train.

Manifest chung: `data/splits/diversevul_experiment_manifest.csv`.

| Protocol | Vai trò | File ID |
| --- | --- | --- |
| Project-wise | Đánh giá chính, unseen project | `data/splits/diversevul_project_wise/` |
| Seen-project | Đánh giá đối chứng, project được phép lặp lại | `data/splits/diversevul_seen_project/` |

Mỗi thư mục có `train.txt`, `validation.txt`, `test.txt`. Mỗi dòng là một `sample_id` dạng `row-{số thứ tự trong jsonl}`. File manifest thêm CWE, project, commit, CVE, `group_id` và tên split của cả hai protocol.

Số liệu kiểm tra nằm ở `data/splits/diversevul_split_report.json`. Tạo lại bằng:

```powershell
python scripts/split_diversevul.py
```

`src/data/split.py` vẫn là stub cho ba strategy tổng quát. Split của đồ án là các file trên, không phải một lần gọi `create_split` mới. Manifest 30 function trong `data/sample_manifests/` chỉ dành cho pilot Joern, không phải split thí nghiệm.

## Gom nhóm trước khi chia

Hai record đi cùng nhau nếu chúng chia sẻ một trong ba khóa sau. Khóa trống không được gom thành một nhóm.

1. Hash source sau chuẩn hóa whitespace của EDA.
2. `commit_id`.
3. Mã CVE lấy từ `diversevul_metadata.jsonl`, nối theo `commit_id`.

9.077 function tạo thành 3.352 thành phần liên thông. Trước khi hợp các khóa lại, có 6 mã source, 1.342 commit và 877 CVE được dùng chung bởi ít nhất hai function. 5.663 function có CVE; function không có CVE vẫn được gom theo commit hoặc source. 41 thành phần chạm đúng hai project.

## Project-wise

Đây là đánh giá chính của task 1.4. Một project chỉ nằm ở một split. Nếu một group chạm hai project, hai project đó bị dính thành một siêu-project và đi cùng nhau. 538 project được gom thành 524 siêu-project.

Chia theo siêu-project, nhắm 80/10/10, class hiếm được xếp trước. Đơn vị nhỏ được chuyển thêm để mỗi CWE có ít nhất 5 mẫu ở mỗi split mà split nguồn vẫn còn class đó.

| Split | Function | Tỷ lệ | Project |
| --- | ---: | ---: | ---: |
| train | 6.983 | 76,93% | 468 |
| validation | 1.047 | 11,53% | 37 |
| test | 1.047 | 11,53% | 33 |

Tỷ lệ lệch khỏi 80/10/10 vì cả project phải đi cùng nhau. Kiểm tra leakage: 0 group, 0 commit, 0 duplicate và 0 project bị cắt qua hai split.

| CWE | Tổng | Train | Validation | Test |
| --- | ---: | ---: | ---: | ---: |
| CWE-787 | 1.368 | 941 | 294 | 133 |
| CWE-125 | 1.101 | 874 | 112 | 115 |
| CWE-20 | 873 | 603 | 173 | 97 |
| CWE-416 | 751 | 683 | 34 | 34 |
| CWE-476 | 736 | 559 | 44 | 133 |
| CWE-119 | 697 | 483 | 99 | 115 |
| CWE-200 | 500 | 447 | 20 | 33 |
| CWE-190 | 441 | 311 | 33 | 97 |
| CWE-703 | 362 | 300 | 5 | 57 |
| CWE-399 | 329 | 249 | 23 | 57 |
| CWE-189 | 255 | 202 | 25 | 28 |
| CWE-264 | 209 | 181 | 22 | 6 |
| CWE-415 | 191 | 132 | 26 | 33 |
| CWE-401 | 184 | 173 | 6 | 5 |
| CWE-400 | 179 | 127 | 45 | 7 |
| CWE-120 | 145 | 108 | 13 | 24 |
| CWE-369 | 136 | 110 | 13 | 13 |
| CWE-22 | 129 | 104 | 12 | 13 |
| CWE-835 | 109 | 88 | 10 | 11 |
| CWE-617 | 102 | 82 | 10 | 10 |
| CWE-295 | 98 | 79 | 10 | 9 |
| CWE-59 | 93 | 75 | 9 | 9 |
| CWE-770 | 89 | 72 | 9 | 8 |

Ô nhỏ nhất là CWE-703 validation (5) và CWE-401 test (5). Khi báo per-CWE F1 ở protocol này, phải kèm support. Các ô dưới 10 mẫu không đủ để kết luận class đó khó hay dễ.

## Seen-project

Cùng 9.077 function, nhưng đơn vị chia là group chứ không phải project. Cùng một project được xuất hiện ở nhiều split. Group, commit, CVE và duplicate vẫn không được cắt.

174 project có mặt ở nhiều hơn một split. Đó là khác biệt cố ý so với protocol chính.

| Split | Function | Tỷ lệ |
| --- | ---: | ---: |
| train | 7.272 | 80,11% |
| validation | 902 | 9,94% |
| test | 903 | 9,95% |

Kiểm tra leakage: 0 group, 0 commit và 0 duplicate bị cắt. Mọi CWE có ít nhất 8 mẫu ở mỗi split.

| CWE | Tổng | Train | Validation | Test |
| --- | ---: | ---: | ---: | ---: |
| CWE-787 | 1.368 | 1.095 | 136 | 137 |
| CWE-125 | 1.101 | 881 | 110 | 110 |
| CWE-20 | 873 | 699 | 87 | 87 |
| CWE-416 | 751 | 601 | 75 | 75 |
| CWE-476 | 736 | 590 | 73 | 73 |
| CWE-119 | 697 | 559 | 69 | 69 |
| CWE-200 | 500 | 400 | 50 | 50 |
| CWE-190 | 441 | 353 | 44 | 44 |
| CWE-703 | 362 | 290 | 36 | 36 |
| CWE-399 | 329 | 263 | 33 | 33 |
| CWE-189 | 255 | 205 | 25 | 25 |
| CWE-264 | 209 | 167 | 21 | 21 |
| CWE-415 | 191 | 153 | 19 | 19 |
| CWE-401 | 184 | 148 | 18 | 18 |
| CWE-400 | 179 | 143 | 18 | 18 |
| CWE-120 | 145 | 117 | 14 | 14 |
| CWE-369 | 136 | 110 | 13 | 13 |
| CWE-22 | 129 | 103 | 13 | 13 |
| CWE-835 | 109 | 87 | 11 | 11 |
| CWE-617 | 102 | 82 | 10 | 10 |
| CWE-295 | 98 | 79 | 10 | 9 |
| CWE-59 | 93 | 75 | 9 | 9 |
| CWE-770 | 89 | 72 | 8 | 9 |

Không có chronological split. DiverseVul local không có timestamp đủ tin cậy; task 1.4 đã khóa điểm này.

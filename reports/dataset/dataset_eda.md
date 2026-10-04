# Audit dataset DiverseVul

**Trạng thái: HOÀN TẤT đối với các file local liệt kê dưới đây.** Báo cáo mô tả bản dữ liệu đã load; không tự chọn dataset cuối cùng, tập class, chính sách label, split, graph representation hoặc model.

## File dataset thực tế đã sử dụng

- Dataset chính: `D:/PROJECT/software-bug-detection-using-graphs/data/raw/diversevul/diversevul.jsonl`
- Metadata riêng: `D:/PROJECT/software-bug-detection-using-graphs/data/raw/diversevul/diversevul_metadata.jsonl`
- Bảng label-noise: `D:/PROJECT/software-bug-detection-using-graphs/data/raw/diversevul/diversevul_label_noise.xlsx`

Kích thước: **330,492 dòng x 8 cột thô**. Schema thô thực tế và missing values nằm trong `tables/missing_values.csv`.

Các field đã ánh xạ: `{'sample_id': None, 'source_code': 'func', 'is_vulnerable': 'target', 'cwe': 'cwe', 'project': 'project', 'commit': 'commit_id', 'provided_hash': 'hash', 'cve': None, 'repository': None}`

## So sánh với paper

| metric | paper | dataset_actual | difference |
| --- | --- | --- | --- |
| total_samples | 349,437 | 330,492 | -18,945 |
| vulnerable_samples | 18,945 | 18,945 | 0 |
| non_vulnerable_samples | 330,492 | 311,547 | -18,945 |
| unique_projects | 797 | 800 | 3 |
| unique_commits | 7,514 | 7,653 | 139 |
| unique_cwe | 150 | 150 | 0 |

Mọi chênh lệch được giữ nguyên như quan sát. Nguyên nhân có thể liên quan đến release/version, parsing, độ bao phủ metadata hoặc record bị trùng và cần được điều tra; số liệu không bao giờ bị sửa để khớp paper.

Quan sát đáng chú ý: tổng số dòng của file chính thức đang dùng (**330,492**) đúng bằng con số non-vulnerable mà paper công bố, trong khi file vẫn chứa đủ **18,945** dòng vulnerable; vì vậy số non-vulnerable thực tế chỉ còn **311,547**. Quan hệ số học này gợi ý khác biệt giữa artifact phát hành và cách paper cộng các tập con, nhưng chưa đủ bằng chứng để khẳng định nguyên nhân.

## Coverage và mất cân bằng CWE

- Vulnerable function có ít nhất một CWE parse được: **16,109**
- Vulnerable function không có CWE parse được: **2,836**
- Số CWE unique parse được trên vulnerable function: **150**

Top 20:

| cwe | sample_count | percentage_of_labeled_vulnerable | project_count | commit_count |
| --- | --- | --- | --- | --- |
| CWE-787 | 2,896 | 17.98 | 277 | 1,081 |
| CWE-125 | 1,869 | 11.60 | 176 | 819 |
| CWE-119 | 1,633 | 10.14 | 192 | 720 |
| CWE-20 | 1,315 | 8.16 | 148 | 499 |
| CWE-703 | 1,228 | 7.62 | 152 | 529 |
| CWE-416 | 1,005 | 6.24 | 79 | 392 |
| CWE-476 | 975 | 6.05 | 125 | 503 |
| CWE-190 | 783 | 4.86 | 96 | 293 |
| CWE-200 | 747 | 4.64 | 102 | 369 |
| CWE-399 | 509 | 3.16 | 59 | 240 |
| CWE-362 | 458 | 2.84 | 32 | 166 |
| CWE-284 | 432 | 2.68 | 66 | 178 |
| CWE-189 | 422 | 2.62 | 43 | 140 |
| CWE-264 | 420 | 2.61 | 41 | 151 |
| CWE-400 | 402 | 2.50 | 49 | 143 |
| CWE-401 | 366 | 2.27 | 30 | 185 |
| CWE-310 | 361 | 2.24 | 25 | 112 |
| CWE-120 | 299 | 1.86 | 56 | 113 |
| CWE-415 | 269 | 1.67 | 53 | 103 |
| CWE-369 | 261 | 1.62 | 31 | 155 |

Bằng chứng theo threshold (một multi-CWE function chỉ được tính giữ lại một lần nếu có bất kỳ label nào đạt ngưỡng):

| threshold | number_of_cwe | number_of_samples | percentage_samples_retained | minimum_class_size | maximum_class_size |
| --- | --- | --- | --- | --- | --- |
| 20 | 76 | 15,814 | 98.17 | 20 | 2,896 |
| 50 | 42 | 14,985 | 93.02 | 51 | 2,896 |
| 100 | 31 | 14,581 | 90.51 | 108 | 2,896 |
| 200 | 21 | 13,555 | 84.15 | 201 | 2,896 |

## Multi-CWE

| category | sample_count | percentage_of_vulnerable |
| --- | --- | --- |
| zero_cwe | 2,836 | 14.97 |
| exactly_one_cwe | 11,894 | 62.78 |
| two_or_more_cwe | 4,215 | 22.25 |

Không record multi-CWE nào bị rút gọn thành label đầu tiên. Các ví dụ nằm trong `tables/multi_cwe_examples.csv`.

## Phân bố project và tính khả thi của project-wise split

| minimum_projects_per_cwe | number_of_cwe | number_of_cwe_with_at_least_20_samples | number_of_cwe_with_at_least_50_samples | number_of_cwe_with_at_least_100_samples | number_of_cwe_with_at_least_200_samples |
| --- | --- | --- | --- | --- | --- |
| 2 | 114 | 74 | 42 | 31 | 21 |
| 3 | 97 | 72 | 42 | 31 | 21 |
| 5 | 73 | 66 | 42 | 31 | 21 |
| 10 | 51 | 49 | 38 | 30 | 21 |

Bảng bằng chứng cho các candidate, không phải tập class đã chọn:

| cwe | sample_count | project_count | largest_project_sample_count | largest_project_share |
| --- | --- | --- | --- | --- |
| CWE-787 | 2,896 | 277 | 401 | 13.85 |
| CWE-125 | 1,869 | 176 | 310 | 16.59 |
| CWE-119 | 1,633 | 192 | 279 | 17.09 |
| CWE-20 | 1,315 | 148 | 249 | 18.94 |
| CWE-703 | 1,228 | 152 | 408 | 33.22 |
| CWE-416 | 1,005 | 79 | 434 | 43.18 |
| CWE-476 | 975 | 125 | 229 | 23.49 |
| CWE-190 | 783 | 96 | 127 | 16.22 |
| CWE-200 | 747 | 102 | 214 | 28.65 |
| CWE-399 | 509 | 59 | 147 | 28.88 |
| CWE-362 | 458 | 32 | 278 | 60.70 |
| CWE-284 | 432 | 66 | 239 | 55.32 |
| CWE-189 | 422 | 43 | 94 | 22.27 |
| CWE-264 | 420 | 41 | 197 | 46.90 |
| CWE-400 | 402 | 49 | 117 | 29.10 |
| CWE-401 | 366 | 30 | 113 | 30.87 |
| CWE-310 | 361 | 25 | 184 | 50.97 |
| CWE-120 | 299 | 56 | 54 | 18.06 |
| CWE-415 | 269 | 53 | 41 | 15.24 |
| CWE-369 | 261 | 31 | 99 | 37.93 |

`largest_project_share` cao cho thấy rủi ro tập trung theo project hoặc leakage ngay cả khi class có nhiều sample.

## Duplicate và label conflict

| level | records_with_code | unique_code | duplicate_groups | duplicate_affected_records | duplicate_excess_records | duplicate_affected_percentage | vulnerable_label_conflict_groups | cwe_conflict_groups |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| raw_source | 330,491 | 330,491 | 0 | 0 | 0 | 0.00 | 0 | 0 |
| normalized_source | 330,491 | 329,628 | 863 | 1,726 | 863 | 0.52 | 459 | 299 |

Normalization chỉ chuyển đổi line ending, bỏ space/tab ở cuối từng dòng và xóa dòng trống ở biên. Quy trình không gộp whitespace bên trong hoặc xóa comment.

Kiểm tra field hash do dataset cung cấp:

| records_checked | matching_hash | mismatching_hash | invalid_provided_hash | algorithm |
| --- | --- | --- | --- | --- |
| 330,492 | 330,492 | 0 | 0 | MD5(source UTF-8) biểu diễn dưới dạng integer; chỉ kiểm tra tính toàn vẹn, không dùng cho bảo mật |

## Chất lượng source code và mức sẵn sàng cho graph

| check | sample_count | definition |
| --- | --- | --- |
| missing_source | 0 | giá trị source thô là null |
| empty_source | 1 | source là null, rỗng hoặc chỉ có whitespace |
| very_short_source | 5,608 | ít hơn 20 ký tự hoặc 3 dòng (chỉ là cờ sàng lọc) |
| very_long_source | 4,876 | nhiều hơn 10.000 ký tự hoặc 500 dòng (chỉ là cờ sàng lọc) |

| metric | min | median | mean | p90 | p95 | p99 | max |
| --- | --- | --- | --- | --- | --- | --- | --- |
| characters_per_function | 0 | 516.00 | 1,313.86 | 2,743.90 | 4,509.45 | 12,890.09 | 484,356 |
| lines_per_function | 0 | 19.00 | 43.58 | 91.00 | 146.00 | 392.00 | 24,047 |

| check | sample_count | percentage_of_all_samples | note |
| --- | --- | --- | --- |
| function_like_delimiters | 326,289 | 98.73 | heuristic lexical, không phải kết quả parse |
| preprocessor_directive | 29,947 | 9.06 | heuristic lexical, không phải kết quả parse |
| cpp_specific_marker | 44,420 | 13.44 | heuristic lexical, không phải kết quả parse |

Sample giới hạn để kiểm tra thủ công nằm trong `tables/source_inspection_sample.csv`. Manifest `data/sample_manifests/diversevul_graph_sample.csv` chứa reference được chọn bằng seed cố định cho tối đa 30 vulnerable function, trải trên các nhóm độ dài và số CWE. Manifest không nhúng toàn bộ source code. Audit này không chạy Joern.

Dataset không có field ngôn ngữ để tách C khỏi C++ một cách đáng tin cậy. Các dấu hiệu cú pháp ở trên chỉ là heuristic; tỷ lệ Joern parse thành công trên manifest mới là gate tiếp theo. Độ dài trải từ source rỗng đến hàng chục nghìn dòng và dữ liệu đến từ 800 project, nên corpus không thể xem là chỉ gồm các ví dụ C đơn điệu, nhưng các outlier cần giới hạn hoặc xử lý riêng khi tạo graph.

## Audit metadata

| metric | value | note |
| --- | --- | --- |
| metadata_rows | 7,511 |  |
| dataset_unique_commits | 7,653 |  |
| metadata_unique_commits | 7,511 |  |
| joined_unique_commits | 7,169 | Phần giao của commit ID |
| unjoined_dataset_commits | 484 |  |
| unjoined_metadata_commits | 342 |  |
| joined_dataset_records | 308,696 | Record có commit ID xuất hiện trong metadata |
| unjoined_dataset_records | 21,796 |  |
| missing_commit_url_rows | 0 |  |
| missing_repo_url_rows | 1 |  |
| missing_cve_rows | 3,472 |  |
| missing_cwe_rows | 201 |  |

Dataset chính không có CVE, repository URL hoặc timestamp; CVE/repository chỉ xuất hiện trong metadata riêng với coverage không hoàn chỉnh. Vì không có timestamp, EDA này không thể dựng chronological split có kiểm chứng từ các file chính thức đã tải.

## Bối cảnh label noise

| dataset | sample_size | correct_label | vulnerability_spread_multiple_functions | relevant_but_not_vulnerable | irrelevant | correct_percentage |
| --- | --- | --- | --- | --- | --- | --- |
| DiverseVul | 50 | 30 | 5 | 6 | 9 | 60.00 |
| Union of Three | 50 | 18 | 6 | 6 | 20 | 36.00 |
| CVEFixes | 29 | 15 | 3 | 5 | 6 | 51.72 |
| BigVul | 32 | 8 | 5 | 3 | 16 | 25.00 |
| CrossVul | 23 | 11 | 3 | 5 | 4 | 47.83 |

Bảng chính thức cho thấy 30/50 mẫu DiverseVul được đánh giá đúng (60%); phần còn lại gồm vulnerability trải qua nhiều function, thay đổi liên quan nhưng bản thân function không vulnerable và thay đổi không liên quan. Đây là audit thủ công mẫu nhỏ của authors, không phải thống kê được tính lại trên toàn bộ dataset và không được trộn vào mẫu số full EDA.

## Trả lời trực tiếp các câu hỏi nghiên cứu

1. **Có khớp paper không:** xem chênh lệch chính xác ở trên; không mismatch nào bị sửa để khớp paper.
2. **Vulnerable function có CWE:** 16,109.
3. **Có bao nhiêu CWE usable:** không có một con số duy nhất nếu chưa có policy; các bảng threshold và project support cung cấp số candidate.
4. **Mức mất cân bằng:** phân bố theo rank và biểu đồ tích lũy thể hiện long tail quan sát được.
5. **Threshold:** cả bốn threshold được báo cáo và không threshold nào được tự chọn.
6. **Multi-CWE:** 4,215 vulnerable sample có ít nhất hai CWE parse được.
7. **Duplicate:** tỷ lệ exact và normalized duplicate được báo cáo ở trên.
8. **Label conflict:** số nhóm conflict vulnerable/non-vulnerable và CWE được báo cáo ở trên.
9. **Độ trải theo project:** xem project count trên từng CWE và largest-project share.
10. **Project-wise split:** chỉ khả thi đối với các class đạt mức project support mong muốn; audit không tạo final split.
11. **Mức sẵn sàng cho Joern:** độ đầy đủ/độ dài source và sample manifest hỗ trợ một thử nghiệm giới hạn; tỷ lệ parse thành công vẫn cần được đo ở phase tiếp theo.
12. **Candidate CWE:** dùng bảng bằng chứng không ràng buộc ở trên, sau đó team quyết định policy.
13. **Mức phù hợp tổng thể:** DiverseVul chỉ phù hợp có điều kiện cho nghiên cứu function-to-CWE khi có policy multi-CWE tường minh, xử lý duplicate/conflict, caveat về label noise và đánh giá project-aware.

## Các quyết định nghiên cứu còn mở

- kích thước class tối thiểu và tập CWE candidate
- chính sách single-label, multi-label, hierarchical hoặc xử lý ambiguous sample
- các ràng buộc cho project-aware split cuối cùng
- cách xử lý duplicate và conflict
- graph representation và thiết lập trích xuất Joern
- kiến trúc GNN cuối cùng và evaluation protocol

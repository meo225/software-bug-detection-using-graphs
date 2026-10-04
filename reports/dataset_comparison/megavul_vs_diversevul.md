# So sánh MegaVul với DiverseVul

**Quyết định hiện tại:** DiverseVul vẫn là dataset chính tạm thời. Chưa chốt dataset. Mirror Hugging Face đã bị loại. File gốc `megavul_simple.json` chưa có trên máy, nên mọi số MegaVul bên dưới mới là số tác giả công bố.

## Đã đo: mirror không dùng được

Nguồn đã kiểm tra là `hitoshura25/megavul` trên Hugging Face, revision `dbca97fe510045492baa1592f934ae7b44f8ffe1`. Dataset card tự mô tả đây là bản chuyển sang format CVEfixes từ Kaggle `marcdamie/megavul-a-cc-java-vulnerability-dataset`. Repository tác giả không dẫn tới bản này.

| Chỉ số | Giá trị đo được |
| --- | ---: |
| Số dòng | 671.797 |
| Hash duy nhất | 24.352 |
| Dòng metadata lặp hoàn toàn | 644.189 |
| Dòng thuộc nhóm hash lặp | 670.548 |
| Số lần lặp lớn nhất của một hash | 9.306 |
| CVE duy nhất | 8.476 |
| CWE thô duy nhất | 171 |
| Commit URL duy nhất | 9.284 |

Mirror trùng số CVE tác giả công bố (8.476) nên trông giống bản gốc, nhưng 671.797 dòng không phải 353.873 function, và schema không còn `is_vul`, `func`, `func_before`, `cwe_ids`, `repo_name`, `commit_hash`. Không dùng mirror cho train, test hoặc thống kê luận văn.

Checksum nằm trong `tables/comparison_status.json`. File Parquet không được commit.

## Chưa đo: release chính thức

| Tiêu chí | DiverseVul đã audit | MegaVul đo local | MegaVul tác giả công bố |
| --- | --- | --- | --- |
| Artifact | `diversevul.jsonl` | chưa có file | `megavul_simple.json` trên OneDrive của tác giả |
| Tổng function | 330.492 | chưa đo | 353.873 |
| Vulnerable function | 18.945 | chưa đo | 17.975 |
| CWE unique | 150 | chưa đo | 176 |
| Commit timestamp | không có | chưa đo | có trong `megavul.json`, không có trong bản Simple |
| Graph Joern sẵn | không | chưa đo | tác giả báo 87% function tạo graph thành công |

Số cột cuối không được đưa vào luận văn như kết quả của nhóm. MegaVul chỉ trở thành dataset chính sau khi file gốc vượt cùng các phép đo đã dùng cho DiverseVul: duplicate, label conflict, multi-CWE, threshold 20/50/100/200 và project support 2/3/5/10.

## Việc cần làm

1. Tải `megavul_simple.json` từ OneDrive mà repository [Icyrockton/MegaVul](https://github.com/Icyrockton/MegaVul) trỏ tới.
2. Đặt file tại `data/raw/megavul/megavul_simple.json`.
3. Chạy `python scripts/run_dataset_comparison.py`.
4. Đọc `tables/megavul_official_summary.csv`, `megavul_official_author_comparison.csv`, `megavul_official_duplicate_summary.csv` và `megavul_official_project_support.csv`.
5. Chỉ sau bảng đó mới chọn một trong ba hướng: giữ DiverseVul, chuyển sang MegaVul, hoặc dùng dataset còn lại làm external validation. Không trộn hai corpus trước khi deduplicate xuyên nguồn.

Đối chiếu graph Joern là bước sau, khi schema function đã khớp. Tỷ lệ 87% hiện chưa phải kết quả của nhóm.

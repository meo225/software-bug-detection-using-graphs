# So sánh MegaVul với DiverseVul

**Quyết định:** giữ DiverseVul làm dataset chính. Dùng MegaVul C/C++ 2024-04 làm tập kiểm chứng ngoài. Chưa chuyển dataset chính.

File đã đo là `data/raw/megavul/megavul_simple.json`, 1.181.509.201 byte, SHA-256 `5316dc02e04f4dfd6a9c93e146236ed76da17d8473e1f4721f7e49dc23424b84`. Số function, CVE, commit và repository khớp công bố của tác giả. File không có `commit_date`.

## Số đã đo

| Tiêu chí | DiverseVul | MegaVul |
| --- | ---: | ---: |
| Tổng function | 330.492 | 353.873 |
| Vulnerable function | 18.945 | 17.975 |
| Vulnerable có CWE | 16.109 (85,0%) | 16.458 (91,6%) |
| Vulnerable không có CWE | 2.836 | 1.517 |
| CWE dạng số | 150 | 175 |
| Vulnerable có từ 2 CWE | 4.215 (22,2%) | 1.167 (6,5%) |
| CWE đạt ít nhất 50 mẫu | 42 | 48 |
| CWE đạt ít nhất 100 mẫu | 31 | 27 |
| CWE đạt ít nhất 200 mẫu | 21 | 17 |
| CWE có ít nhất 5 project và 50 mẫu | 42 | 48 |
| CWE có ít nhất 5 project và 100 mẫu | 31 | 27 |
| Nhóm source trùng hoàn toàn | 0 | 11.136 |
| Nhóm trùng source nhưng khác nhãn vulnerable | 459 sau chuẩn hóa whitespace | 143 |
| Path graph Joern cho hàm vulnerable trước vá | không có | 87,14% |

Tác giả công bố 176 CWE. File có thêm nhãn `CWE-Other` ở 33.444 chỗ. Nhãn này không phải một lớp CWE dạng số, nên bảng local đếm 175.

87,14% là tỷ lệ record có đường dẫn graph trong JSON. Chưa có `megavul_graph.zip`, nên chưa kiểm tra file graph có mở được hay không. Với các CWE từ 100 mẫu trở lên, tỷ lệ thiếu path ở mức trung vị 11%. CWE-20 thiếu cao nhất trong nhóm này, 24,7%. Chưa thấy một CWE lớn nào mất phần lớn graph.

11.136 nhóm source trùng nhau chủ yếu là hàm non-vulnerable lặp giữa các commit. Trong đó 7.280 nhóm non-vulnerable mang các CWE khác nhau. Nhóm vulnerable trùng source nhưng khác CWE dạng số chỉ có 38 nhóm, 78 dòng.

## Vì sao chưa chuyển sang MegaVul

MegaVul có metadata CVE, commit, file và path graph. Phủ CWE trên hàm vulnerable cũng cao hơn, và ít mẫu multi-CWE hơn. DiverseVul vẫn hơn ở ba điểm đang cần cho thí nghiệm chính: nhiều hàm vulnerable hơn, nhiều lớp CWE lớn hơn, và gần như không có source trùng hoàn toàn. DiverseVul cũng đã có audit label-noise. MegaVul chưa thắng đủ rõ để đổi dataset chính.

## Việc làm tiếp

1. Giữ DiverseVul cho thí nghiệm chính.
2. Giữ `megavul_simple.json` để kiểm chứng ngoài sau khi pipeline DiverseVul chạy được.
3. Chưa tải `megavul_graph.zip`.
4. Chỉ tải `megavul.json` nếu sau này cần chronological split. Bản simple không có ngày commit.

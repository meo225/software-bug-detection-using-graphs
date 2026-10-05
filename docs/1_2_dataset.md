# Task 1.2. Khảo sát và lựa chọn dataset có nhãn CWE

## 1. Mục tiêu và tiêu chí

Task này chọn dataset C/C++ ở mức function cho bài toán từ source sang graph, rồi GNN, rồi lớp CWE. Biểu diễn graph, công cụ tạo graph và model thuộc các phase sau. Tài liệu này không mặc định phải dùng CPG hay Joern.

Sáu tiêu chí:

- có nhãn CWE
- có source ở mức function
- đủ mẫu cho từng lớp
- có metadata project và commit
- kiểm soát được mẫu trùng và leakage
- đánh giá được khả năng tổng quát sang project chưa thấy

Nhãn từ CVE và fixing commit truy được nguồn tốt hơn nhãn chỉ từ static analyzer. Nhãn đó vẫn có nhiễu và không được xem là ground truth sạch.

## 2. Dataset đã khảo sát

### 2.1 Big-Vul

Big-Vul xây từ CVE, NVD và vulnerability-fixing commit, ở mức function C/C++. Paper báo cáo 188.636 function, khoảng 10.900 hàm vulnerable, 91 CWE và 348 project. Metadata gồm CVE, CWE, CVSS, commit, code trước và sau thay đổi, cùng mô tả CVE.

Truy vết tốt và metadata nhiều. Hạn chế là ít hàm vulnerable hơn DiverseVul, và nhãn suy từ fixing commit nên hàm bị sửa chưa chắc tự nó chứa lỗ hổng. Big-Vul hợp để so sánh hoặc bổ sung, không mặc định đáng tin hơn DiverseVul.

### 2.2 DiverseVul

DiverseVul thu từ vulnerability-fixing commit của nhiều project mã nguồn mở, ở mức function C/C++. Paper báo cáo 349.437 function, 18.945 hàm vulnerable, 330.492 hàm non-vulnerable, 797 project, 7.514 fixing commit và 150 CWE.

Số hàm vulnerable, số CWE và độ phủ project lớn. Tác giả kiểm tay 50 nhãn vulnerable và chỉ nhận 30 nhãn đúng, tức 60%. Lỗi gồm lỗ hổng trải nhiều hàm, hàm liên quan nhưng không trực tiếp vulnerable, và thay đổi không liên quan trong cùng commit.

### 2.3 Draper VDISC

Draper VDISC có khoảng 1,27 triệu function C/C++. Nhãn sinh từ Clang, Cppcheck và Flawfinder. Dataset tập trung bốn nhóm CWE chính cùng một nhóm khác, có thể mang nhiều nhãn, nhưng thiếu metadata project và commit để truy nguồn.

Dataset hữu ích cho học từ nhãn analyzer. Với mục tiêu phân loại CWE có nguồn gốc lỗ hổng và đánh giá theo project, Draper kém phù hợp hơn Big-Vul và DiverseVul.

### 2.4 Devign

Devign không được chọn làm dataset chính vì chỉ có nhãn vulnerable hoặc non-vulnerable, không có nhãn CWE. Paper vẫn có giá trị như nghiên cứu nền về graph và GGNN.

## 3. Bảng so sánh

| Tiêu chí | Big-Vul | DiverseVul | Draper VDISC |
| --- | --- | --- | --- |
| Ngôn ngữ | C/C++ | C/C++ | C/C++ |
| Đơn vị | Function | Function | Function |
| Nguồn nhãn | CVE, NVD và fixing commit | Security issue và fixing commit | Static analyzer |
| Quy mô paper | 188.636 function | 349.437 function | Khoảng 1,27 triệu function |
| Vulnerable | Khoảng 10.900 | 18.945 | Không có một số binary duy nhất |
| CWE | 91 | 150 | 4 nhóm chính và other |
| Project | 348 | 797 theo paper, 800 trong artifact | Không đủ metadata project |
| Metadata | CVE, CWE, CVSS, commit, code trước và sau | CWE, project, commit, message, source. CVE và repo nằm ở metadata riêng | Code và nhãn analyzer |
| Phù hợp mục tiêu | Khá, dùng để so sánh hoặc bổ sung | Cao nhưng có điều kiện | Thấp cho mục tiêu hiện tại |

## 4. EDA trên artifact DiverseVul

Bảng đầy đủ và biểu đồ nằm ở `reports/dataset/dataset_eda.md`. Các số dưới đây là phần dùng để chọn dataset.

Artifact local có 330.492 function, gồm 18.945 vulnerable và 311.547 non-vulnerable, 800 project, 7.653 commit và 150 CWE. So với paper, tổng function thấp hơn 18.945, project cao hơn 3 và commit cao hơn 139. Chênh lệch được giữ nguyên. Chưa đủ bằng chứng để kết luận nguyên nhân là release, parsing hay cách paper cộng các tập con.

Trong 18.945 hàm vulnerable, 16.109 mẫu có ít nhất một CWE và 2.836 mẫu không có CWE. CWE-787 có 2.896 mẫu, trong khi nhiều CWE rất ít mẫu. Không huấn luyện mặc định đủ 150 lớp.

| Ngưỡng tối thiểu | Số CWE | Số sample | Tỷ lệ giữ lại | Khoảng kích thước lớp |
| --- | ---: | ---: | ---: | --- |
| ≥20 | 76 | 15.814 | 98,17% | 20–2.896 |
| ≥50 | 42 | 14.985 | 93,02% | 51–2.896 |
| ≥100 | 31 | 14.581 | 90,51% | 108–2.896 |
| ≥200 | 21 | 13.555 | 84,15% | 201–2.896 |

Bảng ngưỡng chỉ cho thấy đánh đổi giữa số lớp và số mẫu giữ lại. EDA không tự chọn ngưỡng.

Có 11.894 hàm vulnerable mang đúng một CWE, 4.215 hàm mang từ hai CWE, chiếm 22,25%, và 2.836 hàm không có CWE. Không lấy CWE đầu tiên, không chọn ngẫu nhiên một CWE, không nhân một function thành nhiều dòng, và không xóa hết multi-CWE trước khi chốt chính sách nhãn.

Source thô không trùng tuyệt đối. Sau chuẩn hóa line ending, khoảng trắng cuối dòng và dòng trống ở biên, có 863 nhóm trùng, ảnh hưởng 1.726 record, tức 0,52%. Trong đó 459 nhóm lệch nhãn vulnerable và 299 nhóm lệch CWE. Các nhóm phải được xử lý hoặc đi cùng một split.

Với ngưỡng 100 mẫu, 31 CWE có ít nhất 5 project và 30 CWE có ít nhất 10 project. Project-wise split khả thi cho một tập candidate, không tự động đúng cho cả 150 CWE. Project lớn nhất của CWE-362 chiếm 60,70% và của CWE-284 chiếm 55,32%.

File chính có source, target, CWE, project, commit, hash, size và commit message. Không có CVE hay URL repository. Metadata riêng có 7.511 commit nhưng chỉ nối được 7.169 trên 7.653 commit, tương ứng 308.696 record. 21.796 record không nối được. Metadata còn thiếu CVE ở 3.472 dòng. Truy vết hữu ích nhưng chưa đủ.

Có 1 source rỗng. 98,73% mẫu trông giống function theo heuristic. Median 19 dòng, outlier tới 24.047 dòng. 5.608 mẫu rất ngắn và 4.876 mẫu rất dài theo cờ sàng lọc. Corpus từ 800 project và có dấu hiệu C++, nên không phải tập C đơn điệu. Parse success và lệch kích thước graph phải đo bằng pilot, chưa suy ra từ EDA từ vựng.

## 5. Quyết định

Không chọn Draper làm dataset chính vì nhãn phụ thuộc static analyzer, ít nhóm CWE và thiếu metadata project cùng commit. Kết luận này chỉ cho mục tiêu hiện tại. Draper vẫn có giá trị cho bài toán học từ nhãn analyzer.

Big-Vul làm được phân loại CWE và có metadata tốt, nhưng ít hàm vulnerable, ít CWE và ít project hơn DiverseVul. Giữ làm nguồn đối chiếu nếu cần kiểm tra kết quả trên dataset khác.

Chọn DiverseVul làm dataset chính. Lý do là có source function, 150 CWE, 18.945 hàm vulnerable và độ phủ project tốt. Mức phù hợp là có điều kiện. Phải có chính sách nhãn, dedup sau chuẩn hóa, xử lý conflict, chọn CWE theo cả số mẫu và số project, và đánh giá theo project.

Không xem toàn bộ artifact là tập huấn luyện sẵn dùng. Bài toán chính chỉ xét hàm vulnerable có CWE sau các cổng lọc dữ liệu.

Cách chia chính là project-wise, để đo project chưa thấy. Cách chia đối chứng là seen-project theo nhóm đã gom. Mẫu trùng sau chuẩn hóa, commit và CVE liên quan, cùng conflict, phải gom trước khi chia. Chưa chọn chronological split vì metadata local không có timestamp đủ tin.

Pilot graph bắt đầu bằng khoảng 30 function đại diện. So AST tối thiểu với graph có control flow và data dependence. CPG và Joern chỉ giữ nếu pilot cho thấy parse, thời gian chạy và chất lượng graph chấp nhận được.

Tại task 1.2, các mục sau còn mở: ngưỡng và danh sách CWE, single-label hay multi-label hay phân cấp, cách xử lý conflict, khóa gom nhóm và tỷ lệ split, biểu diễn graph, node feature, model, và cách xử lý mất cân bằng lớp. Không mục nào trong số đó suy ra chỉ vì DiverseVul có quy mô lớn. Danh sách CWE và split được chốt ở `docs/2_2_cwe_policy.md` và `docs/2_3_split.md`.

DiverseVul phù hợp nhất trong ba dataset đã khảo sát cho hướng function, graph, GNN, CWE, nhưng chỉ sau khi kiểm soát nhiễu nhãn, multi-CWE, conflict do mẫu trùng, mất cân bằng lớp và tập trung theo project. Điểm mạnh là quy mô và độ đa dạng. Điểm yếu chính là độ tin cậy của nhãn và metadata chưa đủ.

Kết quả task này là chọn DiverseVul làm nguồn chính để tiếp tục audit, chọn CWE, thiết kế split và chạy pilot graph. Không phải khẳng định dataset đã sẵn sàng để train.

## 6. Tài liệu tham khảo

[1] Chen et al. DiverseVul: A New Vulnerable Source Code Dataset for Deep Learning Based Vulnerability Detection. RAID, 2023.

[2] Wagner Group. DiverseVul dataset repository.

[3] Fan et al. A C/C++ Code Vulnerability Dataset with Code Changes and CVE Summaries. MSR, 2020.

[4] Russell et al. Automated Vulnerability Detection in Source Code Using Deep Representation Learning. 2018.

[5] Draper VDISC dataset.

[6] EDA trong repository: `reports/dataset/dataset_eda.md` và các bảng CSV liên quan.

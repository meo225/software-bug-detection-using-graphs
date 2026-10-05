# Task 1.2: Khảo sát và lựa chọn dataset có nhãn CWE

## 1. Mục tiêu và tiêu chí lựa chọn

Task 1.2 khảo sát dataset C/C++ ở mức function để chọn nguồn dữ liệu phù hợp cho bài toán function source code → graph → GNN → CWE class. Graph representation, công cụ tạo graph và model vẫn là quyết định của các phase sau; tài liệu này không mặc định phải dùng CPG hoặc Joern.

Dataset được đánh giá theo sáu tiêu chí: có nhãn CWE; có source code ở mức function; đủ số mẫu cho từng class; có project/commit metadata; hỗ trợ kiểm soát duplicate và leakage; và cho phép đánh giá khả năng tổng quát hóa sang project chưa thấy. Nguồn nhãn từ CVE/fixing commit có khả năng truy vết tốt hơn nhãn chỉ từ static analyzer, nhưng vẫn có label noise và không được xem là ground truth hoàn toàn sạch.

## 2. Các dataset được khảo sát

### 2.1 Big-Vul

Big-Vul là dataset C/C++ function-level được xây từ CVE/NVD và vulnerability-fixing commit. Paper báo cáo 188.636 function, khoảng 10.900 vulnerable function, 91 CWE và 348 project. Metadata gồm CVE, CWE, CVSS, commit, code trước/sau thay đổi và mô tả CVE.

Ưu điểm là khả năng truy vết và metadata phong phú. Hạn chế là quy mô vulnerable nhỏ hơn DiverseVul và nhãn vẫn được suy ra từ fixing commit; function bị thay đổi chưa chắc tự nó chứa vulnerability. Big-Vul phù hợp làm dataset so sánh hoặc nguồn bổ sung, không mặc định đáng tin hơn DiverseVul.

### 2.2 DiverseVul

DiverseVul là dataset C/C++ function-level thu thập từ vulnerability-fixing commit của nhiều project mã nguồn mở. Paper báo cáo 349.437 function, 18.945 vulnerable function, 330.492 non-vulnerable function, 797 project, 7.514 fixing commit và 150 CWE.

Ưu điểm là số vulnerable function, số CWE và độ đa dạng project lớn. Tuy nhiên manual audit của authors chỉ đánh giá đúng 30/50 vulnerable label (60%) trong mẫu kiểm tra. Các lỗi gồm vulnerability trải qua nhiều function, function liên quan nhưng không trực tiếp vulnerable và thay đổi không liên quan trong cùng commit.

### 2.3 Draper VDISC

Draper VDISC chứa khoảng 1,27 triệu function C/C++ và nhãn sinh từ Clang, Cppcheck và Flawfinder. Dataset tập trung vào bốn nhóm CWE chính cùng nhóm khác, có thể mang nhiều nhãn nhưng thiếu project/commit metadata đủ để truy vết.

Dataset hữu ích cho nghiên cứu weak supervision hoặc học từ nhãn analyzer, nhưng không phù hợp bằng Big-Vul và DiverseVul cho mục tiêu CWE classification có nguồn gốc vulnerability và project-aware evaluation.

### 2.4 Devign

Devign không được chọn làm dataset chính vì chỉ cung cấp nhãn vulnerable/non-vulnerable, không có nhãn CWE phù hợp cho output của đồ án. Devign vẫn có giá trị như nghiên cứu nền tảng về biểu diễn graph và GGNN.

## 3. Bảng so sánh dataset

| Tiêu chí | Big-Vul | DiverseVul | Draper VDISC |
| --- | --- | --- | --- |
| Ngôn ngữ | C/C++ | C/C++ | C/C++ |
| Đơn vị | Function | Function | Function |
| Nguồn nhãn | CVE/NVD + fixing commit | Security issue + fixing commit | Static analyzers |
| Quy mô paper | 188.636 function | 349.437 function | Khoảng 1,27 triệu function |
| Vulnerable | Khoảng 10.900 | 18.945 | Không có một số binary duy nhất |
| CWE | 91 | 150 | 4 nhóm chính + other |
| Project | 348 | 797 theo paper; 800 trong artifact | Không đủ metadata project |
| Metadata | CVE, CWE, CVSS, commit, before/after code | CWE, project, commit, message, source; CVE/repo ở metadata riêng | Code và nhãn analyzer |
| Phù hợp mục tiêu | Khá; nguồn so sánh/bổ sung | Cao nhưng có điều kiện | Thấp cho mục tiêu hiện tại |

## 4. Kết quả EDA trên artifact DiverseVul thực tế

### 4.1 So sánh paper và dữ liệu đã tải

Artifact local có 330.492 function, gồm 18.945 vulnerable và 311.547 non-vulnerable; 800 project, 7.653 commit và 150 CWE. So với paper, tổng số function thấp hơn 18.945, số project cao hơn 3 và số commit cao hơn 139. EDA giữ nguyên chênh lệch này; chưa đủ bằng chứng để kết luận nguyên nhân là release, parsing hay cách paper cộng các tập con.

### 4.2 Độ phủ và mất cân bằng CWE

Trong 18.945 vulnerable function, 16.109 mẫu có ít nhất một CWE parse được và 2.836 mẫu không có CWE. Phân bố có long tail: CWE-787 có 2.896 mẫu trong khi nhiều CWE chỉ có rất ít mẫu. Do đó không thể mặc định huấn luyện classifier đủ 150 lớp.

| Ngưỡng tối thiểu | Số CWE | Số sample | Tỷ lệ giữ lại | Khoảng class size |
| --- | ---: | ---: | ---: | --- |
| ≥20 | 76 | 15.814 | 98,17% | 20–2.896 |
| ≥50 | 42 | 14.985 | 93,02% | 51–2.896 |
| ≥100 | 31 | 14.581 | 90,51% | 108–2.896 |
| ≥200 | 21 | 13.555 | 84,15% | 201–2.896 |

Bảng threshold chỉ cung cấp evidence về trade-off giữa số class và dữ liệu giữ lại. EDA không tự chọn ngưỡng cuối cùng.

### 4.3 Multi-CWE

Có 11.894 vulnerable function mang đúng một CWE, 4.215 function mang từ hai CWE trở lên (22,25%) và 2.836 function không có CWE. Không được tự động lấy CWE đầu tiên, chọn ngẫu nhiên một CWE, nhân bản function thành nhiều nhãn hoặc loại toàn bộ multi-CWE trước khi team chốt label policy.

### 4.4 Duplicate và label conflict

Raw source không có exact duplicate. Sau normalization tối thiểu về line ending, trailing whitespace và dòng trống ở biên, có 863 duplicate group ảnh hưởng 1.726 record (0,52%). Trong đó có 459 group xung đột vulnerable/non-vulnerable và 299 group xung đột CWE. Các group phải được xử lý hoặc gom cùng split trước khi train.

### 4.5 Project distribution và khả năng split

Project-wise split khả thi đối với một tập CWE candidate, nhưng không tự động phù hợp cho toàn bộ 150 CWE. Với ngưỡng 100 mẫu, 31 CWE xuất hiện ở ít nhất 5 project và 30 CWE xuất hiện ở ít nhất 10 project. Một số class vẫn tập trung mạnh: largest-project share của CWE-362 là 60,70% và CWE-284 là 55,32%.

### 4.6 Metadata và khả năng truy vết

File chính có source code, target, CWE, project, commit ID, hash, size và commit message; không có CVE hoặc repository URL. Metadata riêng có 7.511 commit nhưng chỉ join được 7.169/7.653 commit của dataset, tương ứng 308.696 record; 21.796 record không join được. Metadata còn thiếu CVE ở 3.472 row. Vì vậy khả năng truy vết là hữu ích nhưng không hoàn chỉnh.

### 4.7 Mức sẵn sàng cho graph

Dataset chỉ có 1 source rỗng; 98,73% mẫu có hình dạng giống function theo heuristic. Median là 19 dòng nhưng có outlier tới 24.047 dòng; 5.608 mẫu rất ngắn và 4.876 mẫu rất dài theo cờ sàng lọc. Corpus đến từ 800 project và có cả dấu hiệu C++, nên không phải tập code C đơn điệu. Tuy nhiên parse success và graph-size bias phải được đo bằng graph pilot, chưa thể suy ra từ EDA lexical.

## 5. Đánh giá mức độ phù hợp

### 5.1 Draper VDISC

Không chọn làm dataset chính vì nhãn phụ thuộc static analyzer, số nhóm CWE hạn chế và thiếu project/commit metadata. Kết luận này chỉ áp dụng cho mục tiêu hiện tại, không phủ nhận giá trị của Draper trong bài toán weak supervision.

### 5.2 Big-Vul

Khả thi cho CWE classification và có metadata tốt, nhưng ít vulnerable function, CWE và project hơn DiverseVul. Nên giữ làm nguồn đối chiếu hoặc phương án bổ sung nếu cần kiểm tra tính ổn định của kết quả trên dataset khác.

### 5.3 DiverseVul

Là dataset candidate chính vì có source function, 150 CWE, 18.945 vulnerable function và độ phủ project tốt. Mức phù hợp là có điều kiện: phải có label policy rõ ràng, normalized deduplication, xử lý conflict, lựa chọn CWE theo cả sample count và project count, cùng project-aware evaluation.

## 6. Quyết định và kế hoạch sử dụng

Chọn DiverseVul làm dataset chính cho phase tiếp theo, nhưng không xem toàn bộ artifact là tập huấn luyện sẵn dùng. Bài toán chính chỉ xét vulnerable function có CWE sau khi hoàn tất các gate dữ liệu.

Primary split là project-wise để đo unseen-project generalization. Secondary split là seen-project stratified-group để so sánh trong điều kiện project đã xuất hiện ở train. Normalized duplicate, commit/CVE liên quan và conflict phải được group trước khi chia. Chronological split chưa được chọn vì metadata local không có timestamp đủ tin cậy.

Graph construction bắt đầu bằng manifest khoảng 30 function đại diện. AST tối thiểu được so sánh với graph có control/data dependence; CPG/Joern chỉ được giữ nếu pilot cho thấy parse success, runtime và graph quality phù hợp.

## 7. Các quyết định còn mở

Team vẫn cần chốt: threshold và danh sách CWE; single-label, multi-label hoặc hierarchical policy; cách xử lý conflict; group key và tỷ lệ split; graph representation; node feature; model và kỹ thuật xử lý class imbalance. Không quyết định nào trong số này được suy ra chỉ từ việc DiverseVul có quy mô lớn.

## 8. Kết luận

DiverseVul phù hợp nhất trong ba dataset được khảo sát cho hướng function → graph → GNN → CWE, nhưng chỉ sau khi kiểm soát label noise, multi-CWE, duplicate conflict, class imbalance và project concentration. Điểm mạnh của dataset là quy mô và diversity; điểm yếu chính là độ tin cậy của label và metadata không hoàn chỉnh.

Kết quả task 1.2 không phải là khẳng định DiverseVul đã sẵn sàng để train, mà là lựa chọn DiverseVul làm nguồn dữ liệu chính để tiếp tục audit, xây candidate CWE, thiết kế split và chạy graph pilot.

## 9. Tài liệu tham khảo

[1] Chen et al. DiverseVul: A New Vulnerable Source Code Dataset for Deep Learning Based Vulnerability Detection. RAID, 2023.

[2] Wagner Group. DiverseVul dataset repository.

[3] Fan et al. A C/C++ Code Vulnerability Dataset with Code Changes and CVE Summaries. MSR, 2020.

[4] Russell et al. Automated Vulnerability Detection in Source Code Using Deep Representation Learning. 2018.

[5] Draper VDISC dataset.

[6] EDA reproducible trong repository software-bug-detection-using-graphs: reports/dataset/dataset_eda.md và các bảng CSV liên quan.

# 1. Các tiêu chí khảo sát

Đề tài hướng tới bài toán phân loại loại lỗi (bug) theo CWE dựa trên mã nguồn C/C++, sử dụng biểu diễn Code Property Graph (CPG) kết hợp mô hình Graph Neural Network (GNN). Mục tiêu của phần khảo sát này là chọn được dataset chính phù hợp nhất cho bài toán đó.

Tiêu chí chọn dataset:

Có nhãn CWE trực tiếp (không chỉ nhãn nhị phân lỗi/không lỗi) và phủ đủ nhiều loại CWE.

Nhãn được lấy từ nguồn đáng tin cậy (CVE/NVD, commit sửa lỗi), không chỉ từ static analysis tool.

Dữ liệu ở mức function-level, có source code và metadata (project, commit) để trace lại nguồn gốc.

Quy mô đủ lớn để huấn luyện mô hình deep learning.

Có thể chia train/test theo project để đánh giá công bằng.

## 2. Các dataset được khảo sát

Khảo sát tập trung vào 3 dataset phổ biến trong nghiên cứu phát hiện lỗ hổng phần mềm ở mức function-level trên C/C++:

### 2.1. Big-Vul

Ngôn ngữ / Đơn vị: C/C++; function-level.

Nguồn nhãn: CVE từ NVD, ánh xạ tới commit sửa lỗi trên GitHub.

Tổng số hàm: 188,636 (trong đó 10,900 hàm lỗi, ~5.8%).

Số CWE: 91 loại.

Số project: 348 dự án mã nguồn mở.

Metadata: CVE ID, CWE ID, CVSS score, commit hash, before/after function code, file path, CVE summary.

### 2.2. DiverseVul

Ngôn ngữ / Đơn vị: C/C++; function-level.

Nguồn nhãn: Security issues và commit sửa lỗi từ 797 project mã nguồn mở trên GitHub.

Tổng số hàm: 349,437 (trong đó 18,945 hàm lỗi, ~5.4%).

Số CWE: 150 loại; 16,109/18,945 hàm lỗi có thông tin CWE.

Số commit: 7,514 fixing commits từ 797 projects.

Metadata: CWE type, project name, commit ID, commit message, function source code, hash.

### 2.3. Draper VDISC

Ngôn ngữ / Đơn vị: C/C++; function-level.

Nguồn nhãn: Kết quả từ 3 công cụ static analysis (Clang, Cppcheck, Flawfinder), không dựa trên CVE/NVD.

Tổng số hàm: 1,274,366.

Nhãn CWE: Chỉ 4 nhóm CWE chính (CWE-119, CWE-120, CWE-469, CWE-476) + CWE-other; có thể multi-label.

Metadata: Mã hàm và nhãn từ analyzer; không có thông tin project/commit cụ thể.

Lưu ý: Devign cũng được xem xét nhưng không đưa vào so sánh chi tiết vì dataset chỉ cung cấp nhãn nhị phân (vulnerable/non-vulnerable), không có nhãn CWE, nên không phù hợp cho bài toán phân loại theo CWE.

## 3. Bảng so sánh dataset

| Tiêu chí | Big-Vul | DiverseVul | Draper VDISC |
| --- | --- | --- | --- |
| Ngôn ngữ | C/C++ | C/C++ | C/C++ |
| Đơn vị dữ liệu | Function-level | Function-level | Function-level |
| Nguồn nhãn | CVE/NVD + commit | Security issue + commit | Static analysis tools |
| Tổng số hàm | 188,636 | 349,437 | 1,274,366 |
| Hàm lỗi | 10,900 (~5.8%) | 18,945 (~5.4%) | Không có số duy nhất (multi-label) |
| Số CWE | 91 | 150 (16,109 hàm có CWE) | 4 nhóm + CWE-other |
| Số project | 348 | 797 | Không rõ (mã nguồn mở chung) |
| Metadata | CVE, CWE, CVSS, commit, before/after code | CWE, project, commit, message, code | Code + nhãn analyzer |
| Source code | Có (before/after function) | Có (function) | Có (function) |
| Trace về nguồn | Tốt (CVE + commit) | Tốt (project + commit) | Hạn chế |
| Phù hợp CWE multiclass | Khá (91 CWE, 10.9K hàm lỗi) | Cao (150 CWE, 16.1K hàm có CWE) | Thấp (chỉ 4 CWE chính) |

## 4. Phân tích khả năng sử dụng cho bài toán phân loại CWE

### 4.1. Draper VDISC — Không phù hợp

Nhãn từ static analysis tool, không dựa trên CVE/NVD nên chất lượng nhãn không đảm bảo cho bài toán phân loại CWE.

Chỉ có 4 nhóm CWE + CWE-other, quá ít để làm bài toán multiclass có ý nghĩa.

Thiếu metadata project/commit để trace lại nguồn gốc lỗi.

Kết luận: Loại khỏi danh sách lựa chọn.

### 4.2. Big-Vul — Khả thi nhưng hạn chế

Có nhãn CWE (91 loại), nguồn nhãn đáng tin cậy từ CVE/NVD.

Metadata phong phú: CVE, CWE, CVSS, before/after code, commit.

Hạn chế: Chỉ có 10,900 hàm lỗi — khi chia cho 91 CWE, nhiều lớp sẽ có rất ít mẫu.

Số project (348) và phạm vi nhỏ hơn DiverseVul.

Kết luận: Có thể dùng được nhưng không phải lựa chọn tối ưu.

### 4.3. DiverseVul — Phù hợp nhất

Nhiều hàm lỗi nhất (18,945) và nhiều CWE nhất (150 loại), trong đó 16,109 hàm lỗi có CWE label.

Nguồn nhãn từ security issues và commit sửa lỗi — đáng tin cậy hơn static analysis.

Đa dạng project (797) giúp mô hình tổng quát tốt hơn và hỗ trợ chia train/test theo project.

Có đủ metadata (project, commit, code) để trace về nguồn gốc và xây dựng CPG.

Quy mô lớn hơn Big-Vul cả về tổng hàm lẫn số hàm lỗi có CWE.

### 4.4. Vấn đề mất cân bằng dữ liệu

Cả Big-Vul và DiverseVul đều có mất cân bằng nghiêm trọng ở hai mức:

Mất cân bằng lỗi/không lỗi: Tỷ lệ hàm lỗi chỉ khoảng 5–6% tổng số hàm. Nếu chỉ dùng accuracy, model có thể đoán toàn "không lỗi" mà vẫn đạt ~94%.

Mất cân bằng giữa các CWE: Với DiverseVul, 16,109 hàm lỗi có CWE chia cho 150 loại CWE — không phải CWE nào cũng đủ mẫu. Cần đếm cụ thể số mẫu từng CWE sau khi tải dataset, rồi chỉ giữ các CWE có đủ mẫu tối thiểu (ví dụ ≥50–100 mẫu) để đưa vào bài toán multiclass.

Hướng xử lý dự kiến:

Lọc giữ các hàm lỗi có CWE label, bỏ bản ghi thiếu nhãn.

Đếm số hàm từng CWE; chỉ giữ các CWE có ít nhất N mẫu (N cần xác định sau khi thống kê).

Hàm có nhiều CWE: xử lý theo hướng single-label (giữ CWE chính) hoặc tách riêng cho multi-label.

Áp dụng class weight hoặc focal loss khi huấn luyện.

Dùng macro-F1 làm chỉ số chính; kèm weighted-F1, precision/recall từng CWE.

Chia train/validation/test theo project (không chia ngẫu nhiên từng hàm) để tránh data leakage.

## 5. Dataset lựa chọn

Dataset chính: DiverseVul

Lý do:

Đúng mục tiêu: Có nhãn CWE trực tiếp (150 loại), phù hợp cho bài toán phân loại bug theo CWE. Big-Vul cũng có CWE nhưng quy mô nhỏ hơn. Draper VDISC chỉ có 4 CWE và nhãn từ tool.

Quy mô lớn nhất: 18,945 hàm lỗi (16,109 có CWE) — gần gấp đôi Big-Vul (10,900 hàm lỗi, 91 CWE). Điều này giúp có nhiều mẫu hơn cho từng CWE khi làm multiclass.

Đa dạng nguồn: 797 project, 7,514 commit — nhiều hơn Big-Vul (348 project), giúp mô hình tổng quát hóa tốt hơn.

Nguồn nhãn đáng tin: Nhãn lấy từ security issues và commit sửa lỗi, đáng tin hơn nhãn từ static analysis tool.

Metadata đủ dùng: Có project name, commit ID, source code — đủ để xây dựng CPG và trace lại nguồn gốc.

Hỗ trợ chia theo project: Số lượng project lớn cho phép chia train/test theo project, đảm bảo đánh giá công bằng.

## 6. Tóm tắt kết quả

Khảo sát Big-Vul, DiverseVul và Draper VDISC theo nguồn nhãn, số lượng mẫu, số CWE, metadata và khả năng sử dụng cho phân loại CWE. Chốt DiverseVul làm dataset chính vì có 18,945 hàm lỗi (16,109 có CWE), 150 loại CWE, 797 project và metadata commit/repository đủ để trace nguồn gốc và xây dựng CPG.

Nguồn tham khảo:

[1] Chen et al. (2023). "DiverseVul: A New Vulnerable Source Code Dataset for Deep Learning Based Vulnerability Detection." arXiv:2304.00409. https://arxiv.org/abs/2304.00409

[2] Wagner Group. DiverseVul dataset repository. https://github.com/wagner-group/diversevul

[3] Fan et al. (2020). "A C/C++ Code Vulnerability Dataset with Code Changes and CVE Summaries." MSR 2020. https://github.com/ZeoVan/MSR_20_Code_vulnerability_CSV_Dataset

[4] Russell et al. (2018). "Automated Vulnerability Detection in Source Code Using Deep Representation Learning." arXiv:1807.04320. https://arxiv.org/abs/1807.04320

[5] Draper VDISC dataset. https://huggingface.co/datasets/claudios/Draper

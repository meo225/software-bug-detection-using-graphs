# Task 1.1: Khảo sát nghiên cứu và pipeline phát hiện software weakness bằng đồ thị

## 1. Mục tiêu và phạm vi

Tài liệu tổng hợp các hướng nghiên cứu tiêu biểu về phát hiện software weakness trong mã nguồn C/C++ bằng đồ thị và mô hình học máy. Đầu ra của task 1.1 là một bản related work giúp nhóm hiểu rõ: đơn vị đầu vào, cách tạo graph, node và edge, feature, model, output, metric, hạn chế của từng nghiên cứu và bài học áp dụng cho đồ án.

Mục tiêu cuối của nhóm là function source code → graph → GNN → CWE class. Đây là bài toán phân loại loại weakness theo CWE, khác với phần lớn nghiên cứu trước vốn chỉ dự đoán vulnerable hoặc non-vulnerable. Vì vậy, các paper được dùng để kế thừa kỹ thuật và thiết kế thực nghiệm, không được sao chép nguyên bài toán hoặc protocol đánh giá.

## 2. Khái niệm và pipeline chung

### 2.1 Đơn vị phân tích

Function-level dùng toàn bộ một hàm làm một mẫu. Cách này phù hợp trực tiếp với DiverseVul và dễ xây baseline. Program slice chỉ giữ phần code liên quan đến một điểm nhạy cảm; biểu diễn tập trung hơn nhưng cần phân tích phụ thuộc và có thể cần ngữ cảnh liên thủ tục.

### 2.2 Biểu diễn mã nguồn bằng graph

AST mô tả cấu trúc cú pháp. CFG mô tả các đường thực thi. Data-flow graph theo dõi sự hình thành và sử dụng dữ liệu. PDG kết hợp phụ thuộc điều khiển và dữ liệu. CPG hợp nhất nhiều góc nhìn trong cùng một graph. Lựa chọn graph quyết định mô hình nhìn thấy thông tin nào; CPG và Joern hiện chỉ là phương án ứng viên, chưa phải quyết định cuối.

### 2.3 Pipeline khái quát

Mã nguồn C/C++ → chọn function hoặc slice → phân tích tĩnh → tạo graph → mã hóa node/edge thành vector → message passing bằng GNN → graph pooling → classifier → dự đoán binary hoặc CWE. Đối với đồ án, output mong muốn là CWE và phải xử lý class imbalance, multi-CWE, duplicate và project generalization.

## 3. Khảo sát các nghiên cứu chính

### 3.1 Devign

Devign (NeurIPS 2019) giải bài toán binary vulnerability detection ở mức function. Paper tạo joint graph gồm AST, CFG, data flow và natural code sequence; node feature kết hợp code embedding với node type. Gated graph recurrent network truyền thông tin theo loại edge, sau đó Conv module tổng hợp node để dự đoán toàn graph.

Bài học áp dụng: composite graph cho phép kết hợp cú pháp, control flow và data dependence; GGNN là baseline hợp lý cho graph nhiều loại cạnh. Hạn chế: output chỉ có hai lớp và paper dùng random split 75/25, nên không phù hợp để sao chép nguyên protocol cho CWE classification hoặc unseen-project evaluation.

### 3.2 ReVeal

ReVeal thực hiện function-level binary detection bằng Code Property Graph và GGNN. CPG cung cấp node source code, node type và typed edges; graph embedding được đưa vào classifier. Đây là pipeline gần hướng CPG của nhóm, nhưng tài liệu hiện chưa có PDF gốc ReVeal nên các chi tiết chỉ được xem là thông tin đối chiếu từ DiverseVul và implementation công khai.

### 3.3 DeepWukong

DeepWukong xây program slice từ program dependence graph rồi biểu diễn slice bằng XFG. Node là statement; edge thể hiện control dependency và data dependency. Paper thử GCN, GAT và k-GNN, đồng thời loại duplicate và conflict trước khi chia dữ liệu.

Bài học áp dụng: slicing giúp tập trung vào vùng code liên quan và control flow bổ sung cho data flow. Tuy nhiên pipeline phức tạp hơn function-level. Slicing và interprocedural context nên là hướng mở rộng sau khi baseline function-level hoạt động ổn định.

### 3.4 Big-Vul

Big-Vul là dataset C/C++ liên kết CVE, CWE, fixing commit và code change. Điểm mạnh là metadata phong phú và hỗ trợ truy vết từ vulnerability đến thay đổi mã nguồn. Tuy nhiên nhãn vẫn chủ yếu được suy ra từ fixing commit, vì vậy một function bị sửa không đồng nghĩa chắc chắn function đó chứa weakness.

Bài học áp dụng: dùng Big-Vul làm nguồn so sánh hoặc bổ sung, nhưng không mặc định dataset này đáng tin hơn DiverseVul. Mọi lựa chọn dataset vẫn cần audit label, duplicate, metadata và project distribution.

### 3.5 DiverseVul

DiverseVul (RAID 2023) cung cấp function C/C++, nhãn vulnerable, CWE, project, commit và source code. Paper mở rộng số project và loại CWE so với nhiều dataset trước, đồng thời báo cáo hiệu năng giảm đáng kể khi test trên project chưa xuất hiện trong train.

Paper cũng tự audit label noise: 30/50 vulnerable function trong mẫu kiểm tra được đánh giá là đúng, tương đương 60%. Các lỗi còn lại gồm vulnerability trải qua nhiều function, function liên quan nhưng không trực tiếp vulnerable và thay đổi không liên quan. Vì vậy DiverseVul phù hợp có điều kiện, không phải ground truth hoàn toàn sạch.

### 3.6 GRACE

GRACE nghiên cứu cách kết hợp thông tin cấu trúc graph với mô hình ngôn ngữ và có thực nghiệm vulnerability-type multiclass, gần mục tiêu phân loại CWE hơn các binary detector truyền thống. Kết quả gợi ý graph vẫn bổ sung tín hiệu ngay cả khi backbone là mô hình ngôn ngữ.

Bài học áp dụng: cần có baseline source/token không dùng graph để đo phần giá trị thực sự của graph. LLM chưa nên là trọng tâm vì phụ thuộc phiên bản, chi phí, khả năng tái lập và rủi ro contamination; chỉ nên xem là hướng mở rộng hoặc công cụ giải thích.

### 3.7 Real-Vul

Real-Vul chỉ ra rằng hiệu năng có thể giảm mạnh khi đánh giá trên toàn codebase thực tế. Nhiều function được gọi là non-vulnerable thực chất chỉ là chưa có bằng chứng vulnerability và nên được xem là uncertain. Paper nhấn mạnh chronological hoặc project-aware evaluation và false-positive burden.

Bài học áp dụng: ngoài Macro-F1 cần báo FPR hoặc số false alarm trên 1.000 function; kết quả trên split cân bằng không đủ để suy ra khả năng triển khai. Với DiverseVul, chronological split chưa thể kiểm chứng vì artifact hiện dùng không có timestamp đáng tin cậy.

### 3.8 PrimeVul

PrimeVul tập trung vào label quality, normalized deduplication, chronological split và realistic evaluation. Paper cho thấy duplicate leakage và split không thực tế có thể làm benchmark lạc quan; function riêng lẻ cũng có thể thiếu caller hoặc interprocedural context.

Bài học áp dụng: duplicate group, commit/CVE group và label conflict phải được xử lý trước khi split. Model architecture không thể bù cho dữ liệu hoặc evaluation protocol kém tin cậy.

## 4. Ma trận related work

| Nghiên cứu | Bài toán / dữ liệu | Biểu diễn | Mô hình / output | Bài học cho đồ án |
| --- | --- | --- | --- | --- |
| Devign | Function C; binary | AST + CFG + DFG + NCS | GGNN + Conv; vulnerable/safe | Typed-edge graph hữu ích; không sao chép random split |
| ReVeal | Function; binary | CPG | GGNN; vulnerable/safe | CPG baseline gần hướng nhóm; cần audit nguồn gốc |
| DeepWukong | Program slice; chủ yếu SARD | XFG từ PDG | GCN/GAT/k-GNN; slice binary | Slicing tập trung hơn; loại duplicate/conflict |
| Big-Vul | Dataset C/C++; CVE/CWE/commit | Function + code change | Dataset, không phải graph model | Metadata tốt nhưng label từ fixing commit |
| DiverseVul | Function C/C++; 150 CWE | Source + metadata; benchmark graph/text | Nhiều baseline binary | Phù hợp có điều kiện; label noise và project shift |
| GRACE | Vulnerability type multiclass | Graph bổ trợ code model | Graph + LLM/CLM | Cần baseline text; LLM chỉ là hướng mở rộng |
| Real-Vul | Đánh giá trên codebase thực tế | Không tập trung graph architecture | Realistic evaluation | Đo false alarm; non-vulnerable có thể uncertain |
| PrimeVul | Dataset và evaluation | Normalized dedup + grouping | Code language models | Chống leakage; split và label quan trọng như model |

## 5. Kết quả EDA DiverseVul và tác động đến kế hoạch

### 5.1 Quy mô và độ phủ CWE

Artifact thực tế có 330.492 function, gồm 18.945 vulnerable và 311.547 non-vulnerable, trải trên 800 project và 7.653 commit. Tổng số dòng thấp hơn paper 18.945 mẫu; số project cao hơn 3 và số commit cao hơn 139. EDA giữ nguyên chênh lệch này và chưa khẳng định nguyên nhân khi chưa có bằng chứng về release hoặc quy trình cộng mẫu của paper.

Trong 18.945 vulnerable function, 16.109 mẫu có ít nhất một CWE parse được và 2.836 mẫu không có CWE. Có 150 CWE nhưng phân bố long-tail. Với ngưỡng tối thiểu 20/50/100/200 mẫu, còn lần lượt 76/42/31/21 CWE và giữ lại 98,17%/93,02%/90,51%/84,15% số vulnerable sample đã có CWE. Đây là evidence để chọn candidate, không phải quyết định threshold.

### 5.2 Multi-CWE và label policy

Có 11.894 vulnerable function mang đúng một CWE, 4.215 function mang từ hai CWE trở lên và 2.836 function không có CWE. Multi-CWE chiếm 22,25% vulnerable data, đủ lớn để không thể tùy ý lấy CWE đầu tiên. Nhóm phải chốt riêng single-label, multi-label, hierarchical mapping hoặc loại ambiguous sample.

### 5.3 Duplicate, conflict và leakage

Raw source không có exact duplicate. Sau normalization an toàn về line ending, trailing whitespace và dòng trống ở biên, có 863 duplicate group ảnh hưởng 1.726 record (0,52%). Trong đó có 459 group xung đột vulnerable/non-vulnerable và 299 group xung đột CWE. Các group này phải được xử lý hoặc gom cùng split trước khi train.

### 5.4 Project generalization

Nhiều CWE phổ biến trải trên nhiều project, nhưng mức tập trung khác nhau đáng kể. Ví dụ largest-project share của CWE-787 là 13,85%, trong khi CWE-362 là 60,70% và CWE-284 là 55,32%. Với ngưỡng 100 mẫu, 31 CWE xuất hiện ở ít nhất 5 project và 30 CWE xuất hiện ở ít nhất 10 project. Project-wise split khả thi cho một tập candidate phù hợp, không mặc định cho toàn bộ 150 CWE.

### 5.5 Mức sẵn sàng cho graph

Dataset chỉ có 1 source rỗng; 98,73% mẫu có dấu phân cách giống function theo heuristic. Median là 19 dòng, nhưng có outlier tới 24.047 dòng; 5.608 mẫu rất ngắn và 4.876 mẫu rất dài theo cờ sàng lọc. Corpus đến từ 800 project và có cả dấu hiệu C++ nên không thể xem là code C đơn điệu, nhưng parse success và graph-size bias vẫn phải được đo bằng pilot.

## 6. Pipeline thực nghiệm đề xuất

### 6.1 Dataset và label gate

Chỉ xét vulnerable function có CWE cho bài toán chính. Candidate CWE phải đồng thời đủ sample và đủ project. Trước khi train, nhóm phải chốt policy multi-CWE, xử lý missing CWE, duplicate conflict và class imbalance. Binary vulnerable/non-vulnerable chỉ dùng để kiểm tra pipeline nếu cần, không thay thế mục tiêu CWE.

### 6.2 Split protocol

Primary protocol là project-wise split để đo unseen-project generalization. Secondary protocol là seen-project stratified-group split để so sánh với nghiên cứu cũ trong điều kiện project đã xuất hiện ở train. Trước khi chia, phải group normalized duplicate, commit/CVE liên quan và conflict; mọi model dùng cùng split cố định. Chưa chọn chronological split vì metadata local không có timestamp đủ tin cậy.

### 6.3 Graph pilot

Chạy pilot khoảng 30 function đại diện trước khi xử lý toàn bộ. So sánh AST tối thiểu với graph có control/data dependence; Joern/CPG chỉ được giữ nếu parse success, runtime và chất lượng graph phù hợp. Báo cáo tỷ lệ parse thành công, runtime, node/edge count, graph rỗng, outlier và bias do parse failure.

### 6.4 Baseline và model ladder

Baseline gồm majority/random và một mô hình source/token không dùng graph. Với graph, ưu tiên GGNN vì phù hợp typed edges; GCN và GAT chỉ được thêm khi phục vụ câu hỏi so sánh. R-GCN hoặc heterogeneous GNN chỉ xem xét nếu edge-type ablation cho thấy loại cạnh mang giá trị rõ ràng.

### 6.5 Đánh giá và ablation

Macro-F1 là metric chính; báo thêm precision, recall, F1 theo từng CWE, confusion matrix và kết quả riêng cho seen-project/unseen-project. Khi đánh giá binary hoặc trên codebase rộng hơn, bổ sung FPR hoặc false alarm trên 1.000 function. Hai ablation ưu tiên là graph-vs-text và AST-vs-control/data graph.

## 7. Câu hỏi nghiên cứu đề xuất

RQ1. Graph-based model phân loại CWE tốt hơn baseline source/token đến mức nào trên cùng dataset và split?

RQ2. Bổ sung control-flow và data-dependence vào AST ảnh hưởng thế nào đến Macro-F1 và từng CWE?

RQ3. Hiệu năng thay đổi ra sao giữa seen-project và unseen-project evaluation?

RQ4. Duplicate/conflict handling và label policy ảnh hưởng thế nào đến kết quả và độ tin cậy của thí nghiệm?

## 8. Các quyết định còn mở

Nhóm chưa nên chốt: threshold cuối, danh sách CWE, single-label hay multi-label, cách xử lý conflict, graph representation, Joern/CPG, node feature và model cuối. Ba đầu việc kế tiếp là chốt candidate CWE bằng evidence EDA, thiết kế split có thể tái lập và chạy graph pilot trên manifest 30 function.

## 9. Kết luận của task 1.1

Hướng hiện tại phù hợp nếu đề tài được định vị là nghiên cứu CWE classification có kiểm soát leakage và project generalization, thay vì chỉ tạo CPG rồi thử nhiều GNN. DiverseVul phù hợp có điều kiện: quy mô và độ phủ project tốt, nhưng có label noise, multi-CWE, long-tail, normalized duplicate conflict và metadata thiếu.

Đóng góp thực tế và khả thi nhất của đồ án là một protocol đánh giá trung thực, graph ablation rõ ràng và phân tích giới hạn dữ liệu. Function-level là điểm khởi đầu hợp lý; slicing, interprocedural context và LLM là hướng mở rộng sau baseline.

## 10. Tài liệu tham khảo

[1] Zhou et al. Devign: Effective Vulnerability Identification by Learning Comprehensive Program Semantics via Graph Neural Networks. NeurIPS, 2019.

[2] Chakraborty et al. Deep Learning based Vulnerability Detection: Are We There Yet? ReVeal.

[3] Cheng et al. DeepWukong: Statically Detecting Software Vulnerabilities Using Deep Graph Neural Network.

[4] Fan et al. A C/C++ Code Vulnerability Dataset with Code Changes and CVE Summaries. MSR, 2020.

[5] Chen et al. DiverseVul: A New Vulnerable Source Code Dataset for Deep Learning Based Vulnerability Detection. RAID, 2023.

[6] GRACE. Graph-augmented vulnerability detection and vulnerability-type classification. Journal of Systems and Software, 2024.

[7] Chakraborty et al. Real-Vul: Toward Realistic Evaluation of Deep Learning Vulnerability Detection. IEEE TSE, 2024.

[8] Ding et al. Vulnerability Detection with Code Language Models: How Far Are We? PrimeVul, 2024.

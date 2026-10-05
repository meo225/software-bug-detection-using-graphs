# Task 1.1. Khảo sát nghiên cứu và pipeline

## 1. Mục tiêu

Đây là related work cho bài toán từ function sang graph, rồi GNN, rồi lớp CWE. Phần lớn nghiên cứu trước chỉ dự đoán có lỗ hổng hay không. Paper dùng để kế thừa kỹ thuật và cách đánh giá, không sao chép nguyên bài toán.

## 2. Khái niệm dùng chung

Function-level lấy cả hàm làm một mẫu. Cách này khớp DiverseVul và dễ làm baseline. Program slice chỉ giữ đoạn liên quan một điểm nhạy cảm. Biểu diễn tập trung hơn, nhưng cần phân tích phụ thuộc và có thể cần ngữ cảnh liên thủ tục.

AST giữ cú pháp. CFG giữ đường thực thi. Data-flow theo dõi dữ liệu được tạo và được dùng ở đâu. PDG gộp phụ thuộc điều khiển và dữ liệu. CPG gộp nhiều góc nhìn vào một graph. CPG và Joern hiện chỉ là phương án ứng viên.

Pipeline đi từ mã nguồn C/C++ tới function hoặc slice, phân tích tĩnh, graph, vector node và edge, message passing, pooling, rồi phân loại. Output của đồ án là CWE. Phải xử lý mất cân bằng lớp, multi-CWE, mẫu trùng và lệch theo project.

## 3. Các nghiên cứu

### 3.1 Devign

Devign, NeurIPS 2019, làm binary detection ở mức function. Joint graph gồm AST, CFG, data flow và natural code sequence. Node feature gồm code embedding và node type. GGNN truyền tin theo loại cạnh, rồi một lớp conv dự đoán cho cả graph.

Graph nhiều loại cạnh là hướng đáng thử, và GGNN là baseline hợp lý. Hạn chế là output chỉ có hai lớp và paper chia ngẫu nhiên 75/25, nên không sao chép protocol này cho phân loại CWE hay đánh giá project chưa thấy.

### 3.2 ReVeal

ReVeal cũng làm binary detection ở mức function, bằng CPG và GGNN. Node có source và node type, cạnh có loại, rồi graph embedding đưa vào classifier. Hướng này gần CPG, nhưng nhóm chưa có PDF gốc. Chi tiết hiện chỉ để đối chiếu từ DiverseVul và mã công khai.

### 3.3 DeepWukong

DeepWukong cắt program slice từ PDG rồi biểu diễn bằng XFG. Node là statement. Cạnh là control dependency và data dependency. Paper thử GCN, GAT và k-GNN, và loại duplicate cùng conflict trước khi chia dữ liệu.

Slice giúp tập trung vào vùng liên quan, và control flow bổ sung cho data flow. Pipeline này nặng hơn function-level. Slicing và ngữ cảnh liên thủ tục để sau, khi baseline function-level đã chạy ổn.

### 3.4 Big-Vul

Big-Vul nối CVE, CWE, fixing commit và thay đổi mã nguồn. Metadata tốt để truy từ lỗ hổng về commit. Nhãn chủ yếu suy từ commit sửa lỗi, nên hàm bị sửa chưa chắc tự nó chứa weakness.

Dùng Big-Vul để so sánh hoặc bổ sung. Không mặc định dataset này đáng tin hơn DiverseVul. Dataset nào cũng cần audit nhãn, mẫu trùng, metadata và phân bố project.

### 3.5 DiverseVul

DiverseVul, RAID 2023, có function C/C++, nhãn vulnerable, CWE, project, commit và source. Paper tăng số project và số CWE so với nhiều dataset trước, và cho thấy kết quả giảm rõ khi test trên project chưa có trong train.

Tác giả tự kiểm 50 hàm vulnerable và chỉ nhận 30 hàm là đúng, tức 60%. Phần còn lại là lỗ hổng trải nhiều hàm, hàm liên quan nhưng không trực tiếp vulnerable, và thay đổi không liên quan. DiverseVul dùng được nếu kiểm soát nhiễu nhãn, không phải ground truth sạch.

### 3.6 GRACE

GRACE kết hợp cấu trúc graph với mô hình ngôn ngữ và có thí nghiệm phân loại loại lỗ hổng, gần mục tiêu CWE hơn các detector nhị phân. Graph vẫn thêm tín hiệu khi backbone là mô hình ngôn ngữ.

Vì vậy cần baseline source và token, không dùng graph, để đo phần giá trị thật của graph. LLM chưa nên là trọng tâm vì phụ thuộc phiên bản, chi phí, khả năng tái lập và rủi ro contamination. Chỉ xem là hướng mở rộng hoặc công cụ giải thích.

### 3.7 Real-Vul

Real-Vul cho thấy kết quả có thể giảm mạnh trên cả codebase thực tế. Nhiều hàm gọi là non-vulnerable thực ra chỉ chưa có bằng chứng, nên nên xem là uncertain. Paper nhấn mạnh đánh giá theo thời gian hoặc theo project, và gánh nặng false positive.

Ngoài Macro-F1 cần báo số false alarm trên 1.000 function. Kết quả trên split cân bằng không đủ để nói về triển khai. DiverseVul local không có timestamp đáng tin, nên chưa kiểm được chronological split.

### 3.8 PrimeVul

PrimeVul tập trung vào chất lượng nhãn, dedup sau chuẩn hóa, chronological split và đánh giá sát thực tế. Trùng mẫu và split không thực tế làm benchmark lạc quan. Một hàm riêng cũng có thể thiếu caller và ngữ cảnh liên thủ tục.

Nhóm trùng source, nhóm commit và CVE, và conflict nhãn phải xử lý trước khi chia. Kiến trúc model không bù được dữ liệu hoặc protocol đánh giá kém.

## 4. Ma trận related work

| Nghiên cứu | Bài toán | Biểu diễn | Mô hình và output | Bài học |
| --- | --- | --- | --- | --- |
| Devign | Function C, binary | AST, CFG, DFG và NCS | GGNN và conv, vulnerable hoặc safe | Cạnh có loại thì hữu ích. Không sao chép random split |
| ReVeal | Function, binary | CPG | GGNN, vulnerable hoặc safe | Gần hướng CPG. Cần kiểm nguồn chi tiết |
| DeepWukong | Program slice, chủ yếu SARD | XFG từ PDG | GCN, GAT, k-GNN, slice binary | Slice tập trung hơn. Loại duplicate và conflict |
| Big-Vul | Dataset C/C++, CVE, CWE, commit | Function và code change | Dataset, không phải model graph | Metadata tốt, nhãn từ fixing commit |
| DiverseVul | Function C/C++, 150 CWE | Source và metadata | Nhiều baseline binary | Phù hợp có điều kiện. Có nhiễu nhãn và lệch project |
| GRACE | Phân loại loại lỗ hổng | Graph bổ trợ code model | Graph và LLM | Cần baseline text. LLM chỉ là hướng mở rộng |
| Real-Vul | Đánh giá trên codebase thực tế | Không tập trung kiến trúc graph | Đánh giá sát thực tế | Đo false alarm. Non-vulnerable có thể là uncertain |
| PrimeVul | Dataset và evaluation | Dedup và grouping sau chuẩn hóa | Code language model | Chống leakage. Split và nhãn quan trọng như model |

## 5. Hệ quả cho đồ án

Số liệu đầy đủ nằm ở `reports/dataset/dataset_eda.md`. Artifact local có 330.492 function, gồm 18.945 vulnerable và 311.547 non-vulnerable, trên 800 project và 7.653 commit. So với paper, tổng dòng thấp hơn 18.945, project nhiều hơn 3, commit nhiều hơn 139. Chênh lệch được giữ nguyên.

Trong các hàm vulnerable, 16.109 mẫu có CWE, 11.894 mẫu có đúng một CWE, 4.215 mẫu có từ hai CWE và 2.836 mẫu không có CWE. Không lấy CWE đầu tiên. Có 150 CWE và phân bố đuôi dài. Ngưỡng 100 mẫu còn 31 CWE, nhưng đó chỉ là bằng chứng để chọn lớp, chưa phải ngưỡng đã chốt.

Source thô không trùng tuyệt đối. Sau chuẩn hóa line ending, khoảng trắng cuối dòng và dòng trống ở biên, có 863 nhóm trùng, ảnh hưởng 1.726 record. Trong đó 459 nhóm lệch nhãn vulnerable và 299 nhóm lệch CWE. Các nhóm này phải đi cùng một split.

CWE-787 có project lớn nhất chiếm 13,85%. CWE-362 chiếm 60,70% và CWE-284 chiếm 55,32%. Project-wise split khả thi với một tập candidate, không mặc định cho cả 150 CWE. Có 1 source rỗng. 98,73% mẫu trông giống function theo heuristic. Median 19 dòng, outlier tới 24.047 dòng. Parse success phải đo bằng pilot.

Đánh giá chính là project-wise, để đo project chưa thấy. Đánh giá đối chứng là seen-project, chia theo nhóm sau khi đã gom mẫu trùng. Chưa dùng chronological split vì không có timestamp đủ tin. Mọi model dùng chung một split. Metric chính là Macro-F1, kèm precision, recall và F1 từng CWE.

Baseline gồm majority, random, và một mô hình source hoặc token không dùng graph. Với graph, ưu tiên GGNN. GCN và GAT chỉ thêm khi phục vụ một câu hỏi so sánh. Pilot khoảng 30 function trước khi chạy toàn bộ. So AST tối thiểu với graph có control flow và data dependence.

Tại thời điểm task 1.1, nhóm chưa chốt ngưỡng, danh sách CWE, single-label hay multi-label, cách xử lý conflict, biểu diễn graph và model cuối. Các mục đó được chốt ở các task sau.

Đề tài đáng làm nếu được đặt là phân loại CWE có kiểm soát leakage và khả năng tổng quát sang project mới. Đóng góp khả thi nhất là protocol đánh giá trung thực, ablation graph rõ, và phân tích giới hạn dữ liệu. Function-level là điểm bắt đầu. Slicing, ngữ cảnh liên thủ tục và LLM là phần mở rộng sau baseline.

## 6. Tài liệu tham khảo

[1] Zhou et al. Devign: Effective Vulnerability Identification by Learning Comprehensive Program Semantics via Graph Neural Networks. NeurIPS, 2019.

[2] Chakraborty et al. Deep Learning based Vulnerability Detection: Are We There Yet? ReVeal.

[3] Cheng et al. DeepWukong: Statically Detecting Software Vulnerabilities Using Deep Graph Neural Network.

[4] Fan et al. A C/C++ Code Vulnerability Dataset with Code Changes and CVE Summaries. MSR, 2020.

[5] Chen et al. DiverseVul: A New Vulnerable Source Code Dataset for Deep Learning Based Vulnerability Detection. RAID, 2023.

[6] GRACE. Graph-augmented vulnerability detection and vulnerability-type classification. Journal of Systems and Software, 2024.

[7] Chakraborty et al. Real-Vul: Toward Realistic Evaluation of Deep Learning Vulnerability Detection. IEEE TSE, 2024.

[8] Ding et al. Vulnerability Detection with Code Language Models: How Far Are We? PrimeVul, 2024.

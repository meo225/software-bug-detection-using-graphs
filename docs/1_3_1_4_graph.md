# Task 1.3-1.4: Lựa chọn biểu diễn graph và khung thực nghiệm

- **Task 1.1:** Khảo sát nghiên cứu và pipeline
- **Task 1.2:** Khảo sát và lựa chọn dataset có nhãn CWE
- **Task 2.1:** Audit và EDA DiverseVul

## 1. Mục tiêu của tài liệu

Tài liệu này trả lời hai quyết định trước khi xây pipeline graph:

- **Task 1.3:** biểu diễn graph nào đủ hợp lý để thử nghiệm trên DiverseVul?
- **Task 1.4:** câu hỏi nghiên cứu, baseline, model và protocol đánh giá nào vừa có giá trị khoa học vừa khả thi trong phạm vi đồ án?

Kết luận được xây dựng từ related work, tài liệu Joern và kết quả EDA thực tế của repository. Đây là quyết định cho giai đoạn pilot, không phải cam kết rằng một cấu hình sẽ là phương án cuối cùng.

## 2. Các câu hỏi nghiên cứu đã đặt ra

### 2.1. Về đơn vị đầu vào

1. Dataset cung cấp function độc lập hay đủ context của cả project?
2. Một function có luôn chứa đủ nguyên nhân của vulnerability không?
3. Có thể bổ sung caller/callee hoặc program slice mà vẫn tái lập và không làm vượt phạm vi môn học không?

### 2.2. Về graph

1. AST giữ được thông tin gì và bỏ mất thông tin gì?
2. Control flow và data dependence có cung cấp tín hiệu bổ sung cho phân loại CWE không?
3. Có cần toàn bộ CPG hay chỉ một subgraph gồm các loại node/edge đã chọn?
4. Joern có tạo graph ổn định từ các function rời, macro và C/C++ không đầy đủ context không?
5. Graph quá lớn, graph rỗng và parse failure có tập trung vào một số CWE/project hay không?
6. Có cần giữ edge type, direction và reverse edge khi đưa graph vào GNN không?

### 2.3. Về node feature

1. Node type và lexical token có đủ làm baseline không?
2. Có nên giữ identifier/literal nguyên bản hay chuẩn hóa để hạn chế học thuộc project?
3. Embedding token nên học từ đầu hay dùng encoder source-code có sẵn?
4. Node feature có được tạo chỉ từ train set để tránh leakage không?

### 2.4. Về model và bằng chứng thực nghiệm

1. Graph có tốt hơn baseline không dùng graph trên cùng split không?
2. Thêm CFG/data-dependence vào AST có cải thiện Macro-F1 hay chỉ làm tăng chi phí?
3. Model có giữ edge type có tốt hơn model gộp mọi edge thành một loại không?
4. Kết quả giảm bao nhiêu khi chuyển từ seen-project sang unseen-project?
5. Kết luận có ổn định qua nhiều seed và theo từng CWE không?

## 3. Bằng chứng liên quan

### 3.1. Từ EDA DiverseVul

- Dataset local có 330.492 function, trong đó 18.945 function vulnerable.
- 16.109 vulnerable function có ít nhất một CWE; 4.215 function có từ hai CWE trở lên.
- 150 CWE tạo thành long-tail. Threshold 100 còn 31 CWE và 14.581 function, nhưng đây chỉ là bằng chứng để team chọn class, không phải quyết định tự động.
- Normalization bảo thủ phát hiện 863 nhóm duplicate, 459 nhóm xung đột vulnerable/non-vulnerable và 299 nhóm xung đột CWE.
- Nhiều CWE trải trên nhiều project, nhưng một số class vẫn tập trung mạnh vào một project.
- 98,73% sample có dấu hiệu lexical giống function; tuy nhiên có source rỗng, function rất ngắn, function cực dài, macro và cú pháp C++.
- Dataset không có field ngôn ngữ đáng tin cậy và không có timestamp đủ để dựng chronological split có kiểm chứng.
- Manual audit của authors chỉ đánh giá đúng 30/50 vulnerable labels. Function-level label vì vậy phải được xem là nhãn có nhiễu.

Hệ quả: graph extraction cần có pilot và báo cáo parse bias; split phải gom duplicate/conflict trước; đánh giá chính phải project-aware; kết luận không được diễn giải như ground truth hoàn hảo.

### 3.2. Từ nghiên cứu và công cụ

- **Devign** cho thấy graph tổng hợp nhiều quan hệ chương trình có thể dùng cho graph-level vulnerability classification và sử dụng GGNN. Tuy nhiên bài toán là binary và evaluation random split không đủ trả lời project generalization.
- **DeepWukong** dùng program slicing/XFG để tập trung control/data flow liên quan. Kết quả ủng hộ giá trị của dependency information, nhưng slicing và context liên thủ tục làm pipeline phức tạp hơn baseline function-level.
- **IVDetect** tách vulnerable statements và context qua data/control dependency, cho thấy PDG có ích cho biểu diễn và giải thích. Đây vẫn không phải bằng chứng rằng mọi edge CPG đều cần thiết.
- **LineVul** là bằng chứng rằng source/token model có thể là baseline mạnh. Không có baseline không dùng graph thì không thể kết luận cải thiện đến từ graph.
- **PrimeVul** nhấn mạnh deduplication, split theo thời gian và realistic metrics. DiverseVul local thiếu timestamp, nên không nên tạo chronological split giả; project-wise split là lựa chọn thay thế có thể kiểm chứng.
- **Real-Vul** cho thấy kết quả có thể giảm mạnh trên dữ liệu gần thực tế và toàn codebase. Vì đề tài đang làm CWE classification trên vulnerable subset, false alarms trên toàn codebase chỉ nên là metric phụ nếu có binary screening stage.
- **Joern** biểu diễn CPG như directed, edge-labeled, attributed multigraph gồm nhiều layer, trong đó có AST, control flow và intra-procedural data flow. Vì vậy có thể dùng Joern để sinh dữ liệu rồi chủ động chọn một tập node/edge; không cần đưa toàn bộ CPG vào model.
- **GCN** là baseline message-passing đơn giản và hiệu quả, nhưng bản chuẩn không phân biệt edge type.
- **GAT** học trọng số láng giềng, nhưng attention không tự động thay thế semantics của edge type.
- **GGNN** dùng cập nhật có cổng qua nhiều bước message passing và phù hợp để kiểm tra graph chương trình có hướng; cách triển khai vẫn phải xác nhận nó sử dụng edge type như thế nào.
- **R-GCN** xử lý relation type tường minh nhưng tăng chi phí theo số relation; chỉ nên thêm nếu ablation cho thấy edge type thực sự quan trọng.

## 4. Kết luận Task 1.3: phương án biểu diễn graph

### 4.1. Quyết định cho pilot

Chọn **Joern làm công cụ ứng viên để pilot**, không coi Joern hay CPG là quyết định cuối cùng. Trên cùng manifest khoảng 30 function đã tạo từ EDA, sinh hai biến thể:

1. **Graph A - AST baseline**
   - Node: các node cú pháp trong phạm vi function.
   - Edge: AST parent-child, thêm reverse edge khi model cần truyền thông tin hai chiều.
   - Mục đích: baseline graph đơn giản, dễ kiểm tra và rẻ hơn.

2. **Graph B - semantic graph tối thiểu**
   - Node: dùng cùng miền node với Graph A khi có thể.
   - Edge: AST + CFG + data-dependence; giữ edge type và direction.
   - Mục đích: kiểm tra control/data relation có mang lại giá trị vượt AST hay không.

Không đưa toàn bộ edge CPG vào lần chạy đầu. Call graph, interprocedural context, slicing/XFG, dominator edges và các overlay khác chỉ được xem xét khi baseline thất bại theo một giả thuyết cụ thể.

### 4.2. Node feature ban đầu

Feature tối thiểu gồm:

- node type;
- token/code của node sau normalization bảo thủ;
- tùy chọn vị trí tương đối hoặc line number nếu không tạo shortcut theo project.

Không dùng project, commit, CVE hoặc CWE trong node feature. Identifier/literal cần một ablation nhỏ giữa giữ subtoken và chuẩn hóa placeholder; vocabulary hoặc tokenizer phải được fit trên train set.

### 4.3. Gate trước khi chạy toàn bộ

Pilot chỉ được thông qua khi báo cáo được:

- parse success theo sample, CWE, project và nhóm độ dài;
- nguyên nhân parse failure;
- số node/edge, edge type, graph rỗng và component bất thường;
- thời gian và dung lượng trên mỗi function;
- khả năng ánh xạ graph về đúng sample/label;
- khác biệt giữa AST và semantic graph;
- bias nếu sample bị loại do parse lỗi hoặc vượt giới hạn kích thước.

Nếu Joern không parse ổn function rời, thử wrapper tối thiểu hoặc context reconstruction có kiểm soát và ghi lại thay đổi. Không được âm thầm loại sample parse lỗi.

## 5. Kết luận Task 1.4: khung thực nghiệm

### 5.1. Phát biểu bài toán

Input chính là source code của một function C/C++ vulnerable có CWE. Output là CWE theo chính sách label được chốt ở task 2.2. Đề tài là **phân loại weakness theo CWE**, không phải malware detection và không đồng nhất với binary vulnerability detection.

Do 22,25% vulnerable sample là multi-CWE, chưa thể mặc định dùng softmax multiclass. Task 2.2 phải chọn một trong ba phương án có thể bảo vệ được: subset single-label; multi-label classification; hoặc mapping/hierarchy có tài liệu. Không lấy CWE đầu tiên và không nhân bản một function thành nhiều single-label record trước khi split.

### 5.2. Câu hỏi nghiên cứu chính

- **RQ1:** Biểu diễn graph có cải thiện CWE classification so với baseline chỉ dùng source/token trên cùng dữ liệu và split không?
- **RQ2:** AST + control/data dependence có cải thiện so với AST-only không, và chi phí tăng bao nhiêu?
- **RQ3:** Kết quả thay đổi như thế nào giữa seen-project và unseen-project evaluation?
- **RQ4:** Những CWE nào hoạt động tốt/kém, và lỗi có liên quan đến class size, project concentration, label noise hoặc parse failure không?

So sánh GCN, GAT và GGNN không nên là câu hỏi trung tâm độc lập. Đây là so sánh phụ để tìm xem inductive bias nào phù hợp với graph đã chọn.

### 5.3. Baseline và model ladder

Thứ tự tối thiểu:

1. Majority baseline và stratified-random baseline.
2. Baseline source/token không dùng graph, ưu tiên một mô hình nhẹ và tái lập được.
3. GCN trên AST để kiểm tra pipeline graph cơ bản.
4. GGNN hoặc relational message-passing trên semantic graph để khai thác direction/edge relation.
5. GAT chỉ thêm khi có đủ thời gian hoặc có giả thuyết rằng trọng số láng giềng giúp ích.

Không chạy đồng thời mọi kiến trúc. R-GCN/heterogeneous GNN chỉ là bước mở rộng nếu thí nghiệm gộp-và-giữ edge type cho thấy relation type quan trọng.

### 5.4. Split và leakage control

- Trước split, tạo group từ normalized duplicate; các record cùng group không được nằm ở nhiều split.
- Xử lý hoặc cô lập nhóm xung đột label; không để cùng code với label khác nhau xuất hiện ở train và test.
- Gom thêm theo commit/CVE khi metadata cho phép để giảm leakage từ cùng vulnerability-fix context.
- **Primary evaluation:** project-wise split với project test hoàn toàn không xuất hiện trong train.
- **Secondary evaluation:** seen-project stratified-group split để so sánh với setting dễ hơn và nghiên cứu cũ.
- Không dùng chronological split cho bản DiverseVul hiện tại vì timestamp không đủ tin cậy.
- Split phải được tạo một lần, lưu manifest và dùng chung cho mọi baseline/model.

### 5.5. Metric và cách báo cáo

- Metric chính: Macro-F1.
- Metric bổ sung: macro Precision/Recall, weighted-F1, per-CWE Precision/Recall/F1, confusion matrix và support.
- Báo riêng seen-project và unseen-project.
- Báo mean và standard deviation qua ít nhất ba seed nếu tài nguyên cho phép.
- Báo coverage sau mỗi filter: missing CWE, multi-CWE policy, duplicate/conflict, parse failure và graph-size cap.
- Báo runtime, peak memory, số parameter và dung lượng graph để so sánh tính khả thi.
- Accuracy không được dùng làm metric chính vì long-tail distribution.

False alarms trên 1.000 function chỉ có ý nghĩa trực tiếp nếu hệ thống có bước binary vulnerable/non-vulnerable. Với thí nghiệm chỉ phân loại CWE trên vulnerable subset, không nên trình bày metric này như false-positive rate triển khai thực tế.

### 5.6. Ablation tối thiểu

- source/token baseline so với graph model;
- AST-only so với AST+CFG+data-dependence;
- gộp edge type so với giữ edge type, nếu model hỗ trợ;
- identifier/literal nguyên bản so với normalization, nếu còn thời gian.

Không cần đưa slicing, interprocedural graph, LLM hoặc explainability vào core experiment.

## 6. Tiêu chí dừng và phạm vi thực tế

Core experiment được xem là đủ cho đồ án khi:

1. Có một label policy và candidate CWE set được giải thích bằng EDA.
2. Có split manifest chống duplicate leakage và có unseen-project test.
3. Có source/token baseline, AST graph baseline và một semantic graph model.
4. Có RQ1-RQ4, Macro-F1, per-CWE result và phân tích failure/limitation.
5. Pipeline, seed, config và artifact đủ để chạy lại.

Tuning sâu, thêm model, slicing, context liên thủ tục, LLM và demo giải thích là phần mở rộng. Chỉ thực hiện khi core experiment đã hoàn tất và còn thời gian.

## 7. Hành động tiếp theo

1. Task 2.2: tạo bảng candidate CWE theo sample count, project count và concentration; chốt policy multi-CWE.
2. Task 2.3: dựng hai split manifest, kèm kiểm tra leakage và class coverage.
3. Task 3.1: đặc tả schema Graph A và Graph B ở mức node/edge/feature.
4. Task 3.2: cài Joern và chạy pilot trên manifest 30 function; xuất báo cáo parse/runtime/graph size.
5. Chỉ sau khi pilot đạt gate mới chạy extraction trên toàn subset thực nghiệm.

## 8. Nguồn chính

- Devign: https://papers.nips.cc/paper_files/paper/2019/hash/49265d2447bc3bbfe9e76306ce40a31f-Abstract.html
- DeepWukong: https://doi.org/10.1145/3436877
- IVDetect: https://arxiv.org/abs/2106.10478
- LineVul: https://doi.org/10.1145/3524842.3528452
- DiverseVul repository: https://github.com/wagner-group/diversevul
- Joern Code Property Graph documentation: https://docs.joern.io/code-property-graph/
- Code Property Graph specification: https://cpg.joern.io/
- PrimeVul: https://arxiv.org/abs/2403.18624
- Real-Vul: https://arxiv.org/abs/2407.03093
- GCN: https://arxiv.org/abs/1609.02907
- GAT: https://arxiv.org/abs/1710.10903
- GGNN: https://arxiv.org/abs/1511.05493
- PyTorch Geometric relational layers: https://pytorch-geometric.readthedocs.io/en/2.6.1/generated/torch_geometric.nn.conv.RGCNConv.html

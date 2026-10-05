# Task 1.3 và 1.4. Biểu diễn graph và khung thực nghiệm

- Task 1.1. Khảo sát nghiên cứu và pipeline
- Task 1.2. Khảo sát và lựa chọn dataset có nhãn CWE
- Task 2.1. Audit và EDA DiverseVul

## 1. Mục tiêu

Tài liệu chốt hai việc trước khi xây pipeline graph.

- Task 1.3. Biểu diễn graph nào đủ hợp lý để thử trên DiverseVul?
- Task 1.4. Câu hỏi nghiên cứu, baseline, model và cách đánh giá nào vừa có giá trị vừa làm được trong phạm vi đồ án?

Kết luận dựa trên related work, tài liệu Joern và EDA của repository. Đây là quyết định cho giai đoạn pilot, không phải cam kết cấu hình cuối.

## 2. Câu hỏi đã dùng để chọn

Về đầu vào: dataset có đủ context project hay chỉ từng function? Một function có luôn chứa đủ nguyên nhân lỗ hổng không? Thêm hàm gọi, hàm được gọi hoặc program slice mà vẫn tái lập và không vượt phạm vi môn học được không?

Về graph: AST giữ gì và mất gì? Control flow và data dependence có thêm tín hiệu cho phân loại CWE không? Cần cả CPG hay chỉ một subgraph đã chọn? Joern có tạo graph ổn từ function rời, macro và C/C++ thiếu context không? Graph quá lớn, graph rỗng và parse lỗi có tập trung vào một số CWE hoặc project không? Có cần giữ loại cạnh, chiều cạnh và cạnh ngược không?

Về feature: node type và token có đủ làm baseline không? Giữ identifier và literal hay chuẩn hóa để hạn chế học thuộc project? Embedding học từ đầu hay dùng encoder có sẵn? Feature có được tạo chỉ từ tập train không?

Về bằng chứng: graph có hơn baseline không dùng graph trên cùng split không? Thêm CFG và data dependence vào AST có tăng Macro-F1 hay chỉ tăng chi phí? Giữ loại cạnh có hơn gộp mọi cạnh không? Kết quả giảm bao nhiêu từ seen-project sang unseen-project? Kết luận có ổn qua nhiều seed và từng CWE không?

## 3. Bằng chứng

### 3.1 Từ EDA

Dataset local có 330.492 function, trong đó 18.945 function vulnerable. 16.109 hàm vulnerable có ít nhất một CWE. 4.215 hàm có từ hai CWE. 150 CWE tạo đuôi dài. Ngưỡng 100 mẫu còn 31 CWE và 14.581 function. Đó là bằng chứng để chọn lớp, không phải quyết định tự động.

Chuẩn hóa bảo thủ thấy 863 nhóm trùng, 459 nhóm lệch nhãn vulnerable và 299 nhóm lệch CWE. Nhiều CWE trải nhiều project, nhưng một số lớp vẫn dồn vào một project. 98,73% mẫu trông giống function theo từ vựng, nhưng có source rỗng, hàm rất ngắn, hàm rất dài, macro và cú pháp C++. Không có trường ngôn ngữ đáng tin và không có timestamp đủ để chia theo thời gian. Tác giả chỉ đánh giá đúng 30 trên 50 nhãn vulnerable. Nhãn mức function phải được xem là nhãn có nhiễu.

Hệ quả: trích graph cần pilot và phải báo lệch do parse lỗi. Split phải gom mẫu trùng và conflict trước. Đánh giá chính phải theo project. Kết luận không được diễn giải như ground truth hoàn hảo.

### 3.2 Từ nghiên cứu và công cụ

Chi tiết từng paper nằm ở `docs/1_1_related_work.md`. Phần dưới chỉ giữ hệ quả cho việc chọn graph.

- Devign cho thấy graph gộp nhiều quan hệ có thể dùng cho phân loại mức graph, với GGNN. Bài toán là binary và chia ngẫu nhiên, nên không đủ trả lời khả năng tổng quát sang project mới.
- DeepWukong dùng slice và XFG để tập trung control flow cùng data flow. Thông tin phụ thuộc có giá trị, nhưng slicing và ngữ cảnh liên thủ tục nặng hơn baseline mức function.
- IVDetect tách câu lệnh vulnerable và context qua phụ thuộc dữ liệu và điều khiển. PDG hữu ích cho biểu diễn và giải thích. Điều đó không chứng minh mọi cạnh CPG đều cần.
- LineVul cho thấy mô hình source và token có thể là baseline mạnh. Không có baseline này thì không kết luận được phần cải thiện đến từ graph.
- PrimeVul nhấn mạnh dedup, chia theo thời gian và metric sát thực tế. DiverseVul local thiếu timestamp, nên không tạo chronological split giả. Project-wise split là phương án thay thế kiểm được.
- Real-Vul cho thấy kết quả có thể giảm mạnh trên dữ liệu gần thực tế và cả codebase. Đề tài đang phân loại CWE trên tập vulnerable. False alarm trên cả codebase chỉ là metric phụ nếu có bước sàng nhị phân.
- Joern biểu diễn CPG là multigraph có hướng, cạnh có nhãn, node có thuộc tính, gồm nhiều lớp như AST, control flow và data flow trong hàm. Có thể dùng Joern để sinh dữ liệu rồi tự chọn một tập node và cạnh. Không cần đưa cả CPG vào model.
- GCN là baseline message passing đơn giản, nhưng bản chuẩn không phân biệt loại cạnh.
- GAT học trọng số láng giềng. Attention không tự thay thế ý nghĩa của loại cạnh.
- GGNN cập nhật có cổng qua nhiều bước và hợp để thử graph có hướng. Cách triển khai vẫn phải xác nhận nó dùng loại cạnh thế nào.
- R-GCN xử lý loại quan hệ tường minh nhưng chi phí tăng theo số loại quan hệ. Chỉ thêm nếu ablation cho thấy loại cạnh thực sự quan trọng.

## 4. Kết luận task 1.3

### 4.1 Quyết định cho pilot

Chọn Joern làm công cụ ứng viên để pilot. Không coi Joern hay CPG là quyết định cuối. Trên cùng manifest khoảng 30 function đã tạo từ EDA, sinh hai biến thể.

1. Graph A, baseline AST. Node là các node cú pháp trong phạm vi function. Cạnh là cha con trên AST, thêm cạnh ngược khi model cần truyền tin hai chiều. Mục đích là baseline graph đơn giản, dễ kiểm và rẻ hơn.
2. Graph B, semantic graph tối thiểu. Node dùng cùng miền với Graph A khi có thể. Cạnh là AST, CFG và data dependence. Giữ loại cạnh và chiều cạnh. Mục đích là kiểm control flow và data dependence có hơn AST hay không.

Không đưa toàn bộ cạnh CPG vào lần chạy đầu. Call graph, ngữ cảnh liên thủ tục, slicing, cạnh dominator và các lớp phủ khác chỉ xem xét khi baseline thất bại theo một giả thuyết cụ thể.

### 4.2 Node feature ban đầu

Feature tối thiểu gồm node type, token của node sau chuẩn hóa bảo thủ, và tùy chọn vị trí tương đối hoặc số dòng nếu không tạo đường tắt theo project.

Không dùng project, commit, CVE hoặc CWE trong node feature. Identifier và literal cần một ablation nhỏ giữa giữ subtoken và thay bằng placeholder. Vocabulary hoặc tokenizer phải fit trên tập train.

### 4.3 Cổng trước khi chạy toàn bộ

Pilot chỉ qua khi báo cáo được các mục sau.

- tỷ lệ parse thành công theo mẫu, CWE, project và nhóm độ dài
- nguyên nhân parse lỗi
- số node, số cạnh, loại cạnh, graph rỗng và thành phần bất thường
- thời gian và dung lượng trên mỗi function
- khả năng ánh xạ graph về đúng mẫu và đúng nhãn
- khác biệt giữa AST và semantic graph
- lệch nếu mẫu bị loại vì parse lỗi hoặc vượt giới hạn kích thước

Nếu Joern không parse ổn function rời, thử wrapper tối thiểu hoặc dựng lại context có kiểm soát, và ghi lại thay đổi. Không được âm thầm loại mẫu parse lỗi.

## 5. Kết luận task 1.4

### 5.1 Bài toán

Input chính là source của một function C/C++ vulnerable có CWE. Output là CWE theo chính sách nhãn chốt ở task 2.2. Đề tài là phân loại weakness theo CWE, không phải phát hiện malware và không đồng nhất với binary vulnerability detection.

22,25% mẫu vulnerable là multi-CWE, nên chưa mặc định dùng softmax một lớp. Task 2.2 phải chọn một trong ba phương án bảo vệ được: tập single-label, phân loại multi-label, hoặc ánh xạ phân cấp có tài liệu. Không lấy CWE đầu tiên. Không nhân một function thành nhiều dòng single-label trước khi chia.

### 5.2 Câu hỏi nghiên cứu

- RQ1. Biểu diễn graph có cải thiện phân loại CWE so với baseline chỉ dùng source và token, trên cùng dữ liệu và cùng split, hay không?
- RQ2. AST kèm control flow và data dependence có hơn chỉ AST hay không, và chi phí tăng bao nhiêu?
- RQ3. Kết quả thay đổi thế nào giữa seen-project và unseen-project?
- RQ4. CWE nào chạy tốt hoặc kém, và lỗi có liên quan kích thước lớp, tập trung project, nhiễu nhãn hoặc parse lỗi hay không?

So sánh GCN, GAT và GGNN không nên là câu hỏi trung tâm riêng. Đó là so sánh phụ để xem inductive bias nào hợp graph đã chọn.

### 5.3 Baseline và thứ tự model

1. Baseline majority và baseline random có phân tầng.
2. Baseline source và token, không dùng graph. Ưu tiên mô hình nhẹ và tái lập được.
3. GCN trên AST để kiểm pipeline graph cơ bản.
4. GGNN hoặc message passing có loại quan hệ trên semantic graph, để dùng chiều cạnh và loại cạnh.
5. GAT chỉ thêm khi còn thời gian, hoặc khi có giả thuyết rằng trọng số láng giềng giúp ích.

Không chạy đồng thời mọi kiến trúc. R-GCN và heterogeneous GNN chỉ là bước mở rộng nếu thí nghiệm gộp cạnh với giữ loại cạnh cho thấy loại quan hệ quan trọng.

### 5.4 Split và chống leakage

- Trước khi chia, tạo nhóm từ mẫu trùng sau chuẩn hóa. Các record cùng nhóm không được nằm ở nhiều split.
- Xử lý hoặc tách riêng nhóm conflict nhãn. Không để cùng mã nguồn với nhãn khác nhau xuất hiện ở cả train và test.
- Gom thêm theo commit và CVE khi metadata cho phép, để giảm leakage từ cùng một ngữ cảnh sửa lỗ hổng.
- Đánh giá chính là project-wise. Project trong test không xuất hiện trong train.
- Đánh giá đối chứng là seen-project, chia theo nhóm đã gom, để so với setting dễ hơn và với nghiên cứu cũ.
- Không dùng chronological split cho bản DiverseVul hiện tại vì timestamp không đủ tin.
- Split tạo một lần, lưu manifest, và dùng chung cho mọi baseline và model.

### 5.5 Metric

- Metric chính là Macro-F1.
- Metric bổ sung là macro precision, macro recall, weighted-F1, precision, recall và F1 từng CWE, confusion matrix và support.
- Báo riêng seen-project và unseen-project.
- Báo trung bình và độ lệch chuẩn qua ít nhất ba seed nếu tài nguyên cho phép.
- Báo coverage sau mỗi bộ lọc: thiếu CWE, chính sách multi-CWE, mẫu trùng và conflict, parse lỗi, và trần kích thước graph.
- Báo thời gian chạy, bộ nhớ đỉnh, số parameter và dung lượng graph để so khả năng làm được.
- Accuracy không làm metric chính vì phân bố đuôi dài.

False alarm trên 1.000 function chỉ có nghĩa trực tiếp nếu hệ thống có bước phân vulnerable và non-vulnerable. Với thí nghiệm chỉ phân loại CWE trên tập vulnerable, không trình bày metric này như tỷ lệ false positive khi triển khai.

### 5.6 Ablation tối thiểu

- baseline source và token so với model graph
- chỉ AST so với AST kèm CFG và data dependence
- gộp loại cạnh so với giữ loại cạnh, nếu model hỗ trợ
- identifier và literal nguyên bản so với chuẩn hóa, nếu còn thời gian

Không đưa slicing, graph liên thủ tục, LLM hoặc giải thích model vào thí nghiệm lõi.

## 6. Phạm vi đủ cho đồ án

Thí nghiệm lõi đủ khi có đủ năm mục sau.

1. Có chính sách nhãn và tập CWE candidate được giải thích bằng EDA.
2. Có manifest split chống leakage do mẫu trùng, và có tập test project chưa thấy.
3. Có baseline source và token, baseline graph AST, và một model semantic graph.
4. Có RQ1 đến RQ4, Macro-F1, kết quả từng CWE, và phân tích lỗi cùng giới hạn.
5. Pipeline, seed, config và artifact đủ để chạy lại.

Tuning sâu, thêm model, slicing, ngữ cảnh liên thủ tục, LLM và demo giải thích là phần mở rộng. Chỉ làm khi thí nghiệm lõi đã xong và còn thời gian.

## 7. Việc tiếp theo

1. Task 2.2 đã chốt tập CWE và chính sách nhãn tại `docs/2_2_cwe_policy.md`.
2. Task 2.3 đã chốt hai manifest split tại `docs/2_3_split.md`.
3. Task 3.1 đặc tả schema Graph A và Graph B ở mức node, cạnh và feature.
4. Task 3.2 cài Joern và chạy pilot trên manifest 30 function. Xuất báo cáo parse, thời gian chạy và kích thước graph.
5. Chỉ sau khi pilot đạt cổng mới trích graph trên toàn subset thí nghiệm.

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

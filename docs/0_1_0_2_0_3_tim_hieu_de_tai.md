# 0.1: Các thuật ngữ + phạm vi
-  Software bug: Lỗi trong code khiến chương trình hoạt động sai so với yêu cầu
- Software weakness: Điểm yếu của chương trình có thể bị đe dọa -> CWE
- Software vulnerability: Điểm yếu cụ thể trong phần mềm có thể bị kẻ tấn công khai thác  -> CVE
- Một số CWE  trong C/C++:

1. CWE-119

2. CWE-476

3. CWE-416

4. CWE-190

## 0.2.

Graph: cấu trúc dữ liệu dùng để biểu diễn các đối tượng và mối quan hệ của chúng.

Node: Đại diện một đối tượng trong code. Có thể là 1 biến, phép toán, gọi hàm hoặc khối lệnh .

Edge: Đại diện quan hệ giữa các node. Ví dụ: “Lệnh A chạy trước B”
- AST( Abstract Syntax Tree): Phân tích cấu trúc code tương tự cách phân tích ngữ pháp câu văn. Gồm các Node ( khai báo hàm, toán tử, ..) => Biết code được viết thế nào nhưng không hiểu được thứ tự chạy
- Các cạnh thể hiện quan hệ cha - con
- CFG (Control Flow Graph) : Mô tả thứ tự thực thi của code =>         có nhánh( True/False) , vòng lặp.
- Các cạnh thể hiện đường thực thi
- PDG( Program Dependence Graph) : Mỗi node trong PDG mô tả một lệnh hoặc 1 điều kiện .Có 2 loại cạnh:
- DDG(Data Dependence) : phụ thuộc dữ liệu => biến được tạo ở đâu, dùng chỗ nào.
- CDG(Control Dependence) : điều kiện lệnh hoạt động
- CPG(Code Property Graph): Tập hợp 3 loại graph phía trên.

Static Program Analysis : Phân tích tĩnh

=> Quá trình phân tích và kiểm tra code, không cần chạy

Cách công cụ sử dụng để phân tích:
- Phân tích từ vựng(Lexical Analysis): Đọc source code và băm nhỏ thành các token
- Phân tích cú pháp(Syntax Analysis)         : Ghép các token theo cú pháp của ngôn ngữ lập trình để xây dựng AST
- Control Flow: Từ AST, duyệt qua các nhánh (if/else), vòng lặp ->tạo ra các đường thực thi
- Data flow : Đi theo CFG , theo dõi vòng đời các biến ( khởi tạo, thay đổi, dùng ở đâu) => tạo thành CFG
- CPG: tập hợp tất cả, đánh index các node và edge

## 0.3

Các thành phần GNN:
- Node Feature: là vector đại diện ý nghĩa node.
- Edge : Biết được thông tin truyền từ node nào sang node nào
- Message Passing: Truyền tin giữa các node. Các node chia sẻ và cập nhật thông tin theo các cạnh nối

Graph pooling + Graph embedding: sau quá trình truyền tin , các node chứa đầy đủ ngữ cảnh. Tuy nhiên, đồ thị sẽ có độ lớn nhỏ khác nhau => Cần vector đầu vào có kích thước cố định
- Graph pooling: gom các vector của các node thành 1 vector duy nhất. Lấy trung bình hoặc lớn nhất
- Graph embedding : Vector duy nhất được tạo

=> đưa ra dự đoán

Pipepline tổng quát:

1. Source code -> graph (chứa text + cạnh nối) -> vector -> GNN model chạy message passing->Graph pooling gom các đỉnh-> vector đại diện -> đưa vào mạng noron Linear -> Đưa ra dự đoán CWE

Bài toán phân loại(Classification)

Input: Đồ thị

Label: Đáp án cung cấp cho mô hình

Output: Kết quả mô hình dự đoán

Binary Classification:

Input: “Đoạn code có lỗi hay không)

Label: Có 2 giá trị: 0 = không có lỗi, 1 = có lỗi

Đặc điểm: Dễ huấn luyện, độ chính xác cao

Multiclass CWE Classification:

Input: “Đoạn code chứa cụ thể loại lỗi CWE nào”

Label: Có nhiều giá trị

Đặc điểm: Khó hơn vì GNN phải học cách phân biệt sự khác nhau giữa các lỗi.

(các ý quan trọng màu đỏ)

## 1. PHASE 0.1 — SOFTWARE BUG, WEAKNESS, VULNERABILITY, CWE, CVE

### 1.1 Software bug là gì?

Bug là lỗi/khuyết tật trong code hoặc thiết kế khiến phần mềm hoạt động không đúng dự kiến.

### 1.2 Software weakness là gì?

Weakness là một kiểu điều kiện hoặc điểm yếu trong thiết kế/code có khả năng góp phần tạo ra vulnerability.

Hiểu đơn giản:

Bug = một lỗi cụ thể trong việc xây dựng phần mềm.

Weakness = một kiểu điểm yếu có ý nghĩa về an toàn/an ninh.

CWE = hệ thống phân loại các kiểu weakness.

### 1.3 Vulnerability là gì?

Vulnerability (lỗ hổng) là một điểm yếu trong một hệ thống/sản phẩm cụ thể có thể bị khai thác hoặc kích hoạt để gây ảnh hưởng an toan thông tin.

Cách nhớ:

Bug/defect → có thể tạo ra weakness (điểm yếu) → trong điều kiện cụ thể weakness có thể trở thành vulnerability (lỗ hổng) có thể bị khai thác.

Không nên hiểu đây là chuỗi bắt buộc 100% cho mọi bug. Không phải bug nào cũng trở thành vulnerability.

### 1.4 CWE là gì?

CWE = Common Weakness Enumeration. (Hệ thống phân loại các điểm yếu Weakness phổ biến trong phần mềm và phần cứng.)

VD: Đoạn code

↓

có một lỗi/điểm yếu

↓

Weakness thuộc loại nào?

↓

CWE-787: Out-of-bounds Write

CWE là danh mục các loại weakness phổ biến trong software/hardware. Mỗi loại có mã định danh.

Ví dụ:

- CWE-79: Cross-site Scripting.

- CWE-89: SQL Injection.

- CWE-787: Out-of-bounds Write.

CWE trả lời câu hỏi:

“Đây là LOẠI điểm yếu gì?”

Trong đồ án:

source code/graph = X

CWE = y (label)

Nếu dataset có nhiều CWE và mỗi sample thuộc một CWE, bài toán có thể được xây dựng thành multiclass classification.

### 1.5 CVE là gì?

CVE = Common Vulnerabilities and Exposures.

CVE định danh một vulnerability cụ thể đã được ghi nhận trong một sản phẩm cụ thể.

Cách nhớ cực ngắn:

CWE = loại điểm yếu. → đây là loại Weakness gì **MANG TÍNH LÝ THUYẾT

CVE = trường hợp vulnerability cụ thể. → đây là vulnerability  cụ thể nào? ** THUỘC MỘT SẢN PHẨM CỤ THỂ TRONG THỰC THẾ

Một CWE có thể liên quan đến rất nhiều CVE

Một CVE có thể được ánh xạ tới một hoặc nhiều CWE phù hợp

Ví dụ tư duy:

“SQL Injection” là một loại weakness → có thể được mô tả bởi CWE.

“Một lỗ hổng SQL Injection cụ thể trong sản phẩm X phiên bản Y” → có thể có CVE riêng.

Một CWE có thể liên quan tới nhiều CVE khác nhau.

### 1.6 Chuỗi thuật ngữ cần hiểu

Không nên học thuộc cứng “Bug → Weakness → Vulnerability → CVE → CWE” như một pipeline thời gian.

Hiểu chính xác hơn:

- Bug: defect trong code/design.

- Weakness: kiểu điều kiện yếu có thể dẫn đến vấn đề security.

- Vulnerability: instance có thể khai thác trong một sản phẩm/hệ thống cụ thể.

- CWE: taxonomy/classification cho weakness.

- CVE: identifier cho vulnerability cụ thể.

Trong đề tài của nhóm, nhãn cần quan tâm nhất là CWE.

CHECKPOINT 0.1

- Bug có phải lúc nào cũng là vulnerability không? → Không.

- CWE là gì? → Hệ thống phân loại weakness.

- CVE là gì? → Định danh vulnerability cụ thể.

- Model của nhóm dự đoán gì? → Loại bug/weakness, biểu diễn bằng nhãn CWE.

## 2. PHASE 0.2 — TỪ SOURCE CODE ĐẾN GRAPH

### 2.1 Graph là gì?

Graph G thường được hiểu đơn giản gồm:

- Node (đỉnh): các đối tượng.

- Edge (cạnh): quan hệ giữa các đối tượng.

Với source code, node có thể là biến, toán tử, statement, expression, function...

Edge có thể thể hiện:

- quan hệ cú pháp;

- thứ tự thực thi;

- dữ liệu truyền từ đâu tới đâu;

- statement nào phụ thuộc statement nào.

### 2.2 AST — Abstract Syntax Tree

AST biểu diễn CẤU TRÚC CÚ PHÁP của code. → cây cú pháp trừu tượng

Code:

x = a + b;

AST:

AST trả lời:

“Đoạn code được cấu tạo cú pháp như thế nào?”

AST tốt cho:

- loại biểu thức/ câu lệnh

- quan hệ cha-con cú pháp;

- cấu trúc code.

AST không trực tiếp cho biết đầy đủ chương trình sẽ chạy nhánh nào trước/sau hay dữ liệu từ statement nào ảnh hưởng statement nào.

vì tree cũng là một dạng graph đặc biệt, AST có thể được dùng làm một cách để chuyển source code → graph → GNN

### 2.3 CFG — Control Flow Graph

CFG = Control Flow Graph.

Nó biểu diễn LUỒNG ĐIỀU KHIỂN, tức các đường chương trình có thể thực thi.

Ví dụ:

if (x > 0)

y = 1;

else

y = 2;

print(y);

CFG:

[x > 0?]

↙      ↘

[y=1]  [y=2]

↘    ↙

[print(y)]

CFG trả lời:

“Chương trình có thể đi từ câu lệnh/ khối code  nào sang câu lệnh/ khối code  nào?”

CFG quan trọng với bug vì nhiều bug phụ thuộc đường thực thi.

### 2.4 Data Flow

Data flow tập trung vào cách GIÁ TRỊ/DỮ LIỆU di chuyển.

Ví dụ:

input = read();

x = input;

execute(x);

Ta quan tâm:

input → x → execute

Điều này đặc biệt hữu ích trong security: dữ liệu không tin cậy đi từ source đến một sink nguy hiểm mà không được kiểm tra có thể là dấu hiệu weakness.

Cần nhớ:

Control flow = chương trình chạy theo đường nào.

Data flow = dữ liệu/giá trị truyền qua đâu.

### 2.5 PDG — Program Dependence Graph

PDG biểu diễn các quan hệ phụ thuộc trong chương trình, thường gồm:

- data dependency;

- control dependency.

Ví dụ:

if (admin) {

deleteFile(file);

}

deleteFile(file) phụ thuộc control vào điều kiện admin.

Nếu file nhận giá trị từ userInput, nó có thể có data dependency với userInput.

PDG trả lời:

“Statement này phụ thuộc vào dữ liệu hoặc điều kiện nào?”

### 2.6 CPG — Code Property Graph

CPG = Code Property Graph.

Hiểu đơn giản: CPG gom nhiều góc nhìn của chương trình vào một graph thống nhất, thường kết hợp thông tin cú pháp và semantic/program-analysis như AST, CFG và các quan hệ data/dependence tùy công cụ/schema.

Tư duy:

AST = code trông như thế nào về cú pháp.

CFG = code có thể chạy theo đường nào.

PDG/data flow = dữ liệu đi như thế nào. Câu lệnh này phụ thuộc vào cái gì? (dependancy)

CPG = ghép nhiều loại thông tin đó để phân tích code trong một graph giàu thông tin hơn.

→ AST, CFG, PDG là các cách biểu diễn code khác nhau nhưng có liên quan; còn CPG thường là graph kết hợp nhiều loại thông tin đó.

CPG rất phù hợp với vulnerability/bug analysis vì bug thường không thể nhận ra chỉ từ một token đơn lẻ.

### 2.7 Static Program Analysis là gì?

Static analysis = phân tích chương trình mà không cần chạy chương trình.

Một static-analysis tool có thể:

1. parse source code;

2. tạo AST;

3. suy ra CFG;

4. phân tích data flow/dependency;

5. tạo PDG/CPG hoặc các quan hệ tương ứng.

Trong đồ án, nhóm không nhất thiết phải tự viết parser. Có thể dùng tool/library có sẵn để chuyển code thành graph, tùy dataset và ngôn ngữ.

### 2.8 So sánh nhanh

AST

- Giữ: syntax.

- Câu hỏi: code được viết/cấu tạo thế nào?

CFG

- Giữ: execution/control flow.

- Câu hỏi: chương trình có thể chạy qua đâu?

Data Flow

- Giữ: sự truyền giá trị.

- Câu hỏi: dữ liệu đi từ đâu tới đâu?

PDG

- Giữ: data + control dependency.

- Câu hỏi: statement phụ thuộc vào cái gì?

CPG

- Giữ: nhiều loại quan hệ trong một graph chung.

- Câu hỏi: có thể kết hợp syntax + control + data/dependency để phân tích code thế nào?

## 3. PHASE 0.3 — GNN VÀ GRAPH CLASSIFICATION

GNN = model học trên graph.

Node feature + Edge = dữ liệu GNN nhìn vào.

Message Passing = cách GNN học.

Node Embedding = kết quả học ở từng node.

Pooling = gom các node lại.

Graph Embedding = đại diện cho cả graph.

Classifier = nhìn graph embedding và đoán CWE.

________________

Mối quan hệ

SOURCE CODE

↓

GRAPH

(node features + edges)

↓

GNN

↓

Message Passing

↓

Node Embeddings

↓

Pooling

↓

Graph Embedding

↓

Classifier

↓

Predicted CWE

Ví dụ

code.c

↓

CPG

↓

GNN

↓

học thông tin các node

↓

gom thành thông tin toàn graph

↓

Classifier

↓

CWE-89

Chốt lại: GNN dùng node + edge → message passing để học node embedding → pooling thành graph embedding → classifier dự đoán CWE.

## 4. PIPELINE CỦA ĐỒ ÁN

Pipeline tối thiểu nên hiểu trước khi sang phase sau:

[1] Chọn dataset

Dataset cần source code/sample và nhãn CWE phù hợp.

↓

[2] Khảo sát dataset

Ngôn ngữ? Đơn vị sample là function hay file? Bao nhiêu CWE? Mất cân bằng lớp không? Label có sạch không?

↓

[3] Chuyển source code → graph

Chọn AST/CFG/PDG/CPG hoặc representation cụ thể dựa trên paper/baseline và khả năng tool.

↓

[4] Graph preprocessing

Tạo node features, edge/edge types, mapping label.

↓

[5] Train baseline

Có một baseline để biết hệ thống cơ bản đạt bao nhiêu.

↓

[6] Train các GNN/model khác

Ví dụ các kiến trúc graph phù hợp được paper/dataset hỗ trợ.

↓

[7] Evaluation

So sánh bằng các metric phù hợp như Accuracy, Precision, Recall, F1; nếu class imbalance mạnh cần đặc biệt chú ý macro-F1/per-class metrics.

↓

[8] Phân tích

Model nào tốt hơn? CWE nào dễ/khó? Representation graph ảnh hưởng thế nào? Có class imbalance/data leakage không?

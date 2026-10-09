# Task 3.1. Đặc tả kỹ thuật Graph A và Graph B

## 1. Mục tiêu và căn cứ tài liệu

### 1.1 Mục tiêu
Tài liệu này chốt đặc tả kỹ thuật chi tiết cho hai biểu diễn đồ thị:
1. **Graph A (Baseline AST)**: Cây cú pháp trừu tượng thuần túy trong phạm vi function.
2. **Graph B (Semantic Graph tối thiểu: AST + CFG + Data Dependence)**: Đồ thị đa quan hệ bổ sung luồng điều khiển và phụ thuộc dữ liệu trên cùng miền node với Graph A.

Mục tiêu cốt lõi:
- Đảm bảo tính nhất quán tuyệt đối với tập thí nghiệm **9.077 function, 23 CWE** và hai protocol split (**Project-wise** và **Seen-project**) đã chốt ở Task 2.2 và 2.3.
- Cung cấp đặc tả đủ cụ thể về node, edge, feature, label mapping, kích thước trần, và định dạng lưu trữ để Task 3.2 (Pilot) và Phase 3 trích xuất dữ liệu không phải tự đưa ra bất kỳ quyết định tùy biến nào.
- Ngăn ngừa hoàn toàn rò rỉ dữ liệu (data leakage) ở tầng đồ thị và feature.

---

### 1.2 Kiểm tra tính nhất quán với 4 tài liệu nền tảng

Bốn tài liệu nền tảng đã được đối chiếu chi tiết:
- `docs/1_1_related_work.md` (Related Work & Baseline).
- `docs/1_3_1_4_graph.md` (Định hướng biểu diễn Graph & RQ1–RQ4).
- `docs/2_2_cwe_policy.md` (Tập 23 CWE candidate & chính sách single-label multiclass).
- `docs/2_3_split.md` (Hai protocol split chống leakage trên 9.077 mẫu).

#### Kết quả đối chiếu và cách xử lý các điểm chưa rõ / khác biệt:

| Vấn đề đối chiếu | Nội dung trong tài liệu trước | Quy ước bắt buộc tại Task 3.1 | Quyết định xử lý kỹ thuật |
| :--- | :--- | :--- | :--- |
| **Cạnh ngược (Reverse Edges)** | `docs/1_3_1_4_graph.md` ghi: "thêm cạnh ngược khi model cần truyền tin hai chiều". | Task 3.1 quy định: "Không giữ cạnh ngược chiều nếu không cần thiết theo thiết kế đã chốt." | **Tách biệt tầng lưu trữ (storage) và tầng mô hình (model)**. Tầng lưu trữ artifact (JSON/intermediate) **chỉ lưu cạnh có hướng thực tế** (canonical directed edges) để tiết kiệm dung lượng đĩa và phản ánh đúng ngữ nghĩa chương trình. Việc bổ sung cạnh ngược hoặc đồ thị vô hướng chỉ diễn ra ở tầng `DataLoader` / PyG Transform khi một mô hình cụ thể (như GCN) yêu cầu. |
| **Miền Node giữa Graph A và Graph B** | `docs/1_3_1_4_graph.md` ghi: "Node dùng cùng miền với Graph A khi có thể." | Task 3.1 quy định: "Tái sử dụng miền node của Graph A khi có thể." | **Đồng nhất 100% miền node** ($V_B \equiv V_A$). Mọi node trong Graph B chính là các node AST của Graph A. Cạnh CFG và Data Dependence sẽ nối trực tiếp giữa các node câu lệnh/biểu thức trong cây AST đó. Điều này đảm bảo khi thực hiện ablation so sánh RQ2 (AST vs AST+CFG+DDG), tập node và feature là hằng số, loại bỏ biến ngoại lai. |
| **Chính sách nhãn CWE** | `docs/1_3_1_4_graph.md` còn mở 3 hướng (single-label, multi-label, phân cấp). | `docs/2_2_cwe_policy.md` đã chốt: Single-label multiclass 23 CWE, loại bỏ multi-CWE, loại bỏ conflict. | **Tuân thủ tuyệt đối Task 2.2**: Áp dụng bài toán phân loại đơn nhãn 23 lớp trên 9.077 function. Không xét multi-label hay nhãn phân cấp ở pipeline lõi. |
| **Phân chia dữ liệu (Splits)** | `docs/1_3_1_4_graph.md` định hướng chống leakage. | `docs/2_3_split.md` đã tạo file split cố định trong `data/splits/`. | **Khóa cứng split**: Mọi đồ thị trích xuất được ánh xạ trực tiếp theo `sample_id` về hai bộ split có sẵn. Tuyệt đối không tự động chia lại dữ liệu khi trích xuất graph. |
| **Nguyên tắc khớp từ vựng (Vocabulary Anti-Leakage)** | `docs/1_3_1_4_graph.md` yêu cầu vocabulary fit trên tập train. | Task 3.1 cấm tuyệt đối fit trên toàn bộ dữ liệu. | **Tách rời Graph Trích xuất thô và Graph Tensor**: Graph trích xuất thô lưu token dạng chuỗi văn bản thuần túy. File từ vựng (vocabulary/tokenizer) chỉ được huấn luyện độc lập trên tập `train.txt` của từng split protocol cụ thể. |

---

## 2. Đặc tả Graph A — Baseline AST

### 2.1 Định nghĩa và phạm vi
- **Định nghĩa**: Graph A là cây cú pháp trừu tượng (Abstract Syntax Tree - AST) của function C/C++.
- **Phạm vi**: Intra-procedural (thuần túy trong nội bộ một function đơn lẻ).
- **Mục tiêu thực nghiệm**: Đóng vai trò là graph baseline đơn giản nhất, kiểm tra xem cấu trúc phân cấp cú pháp có đem lại tín hiệu nhận diện CWE tốt hơn mô hình chuỗi token hay không (RQ1, RQ2).

### 2.2 Miền Node ($V_A$)
Mỗi node $u \in V_A$ tương ứng với một thực thể cú pháp của hàm:
- Node gốc (`Method` / `FunctionDefinition`): Đại diện cho toàn bộ hàm.
- Node khối (`Block`, `CompoundStatement`): Khối lệnh `{ ... }`.
- Node câu lệnh (`IfStatement`, `WhileStatement`, `ForStatement`, `ReturnStatement`, `ExpressionStatement`...).
- Node biểu thức & toán tử (`Call`, `BinaryOperator`, `UnaryOperator`, `Assignment`...).
- Node nguyên tử (`Identifier`, `Literal`, `TypeRef`...).

### 2.3 Miền Cạnh ($E_A$)
- **Loại cạnh**: Duy nhất 1 loại quan hệ cú pháp cha-con (`AST_CHILD`).
- **Chiều cạnh**: Có hướng từ node cha trỏ đến node con (`parent -> child`).
- **Mã loại cạnh (Edge Type ID)**: `0` (chuỗi: `"AST"`).
- **Quy ước**:
  - Không có cạnh ngược (`child -> parent`) trong file lưu trữ.
  - Không có khuyên tự lặp (`self-loops`).
  - Không có cạnh ngang (`sibling edges`).

---

## 3. Đặc tả Graph B — Semantic Graph tối thiểu (AST + CFG + Data Dependence)

### 3.1 Định nghĩa và phạm vi
- **Định nghĩa**: Graph B là đồ thị đa quan hệ có hướng (directed multigraph) kết hợp cấu trúc cú pháp (AST), luồng điều khiển thực thi (Control Flow Graph - CFG) và quan hệ phụ thuộc dữ liệu (Data Dependence Graph - DDG / Def-Use chains).
- **Phạm vi**: Intra-procedural (trong phạm vi function).
- **Mục tiêu thực nghiệm**: Kiểm chứng xem việc bổ sung luồng thực thi và luồng dữ liệu vào AST có cải thiện đáng kể Macro-F1 trên từng CWE so với chỉ AST hay không (RQ2).

### 3.2 Miền Node ($V_B$)
- **Nguyên tắc tái sử dụng**: $V_B \equiv V_A$.
- Graph B sử dụng **chính xác cùng tập node cú pháp** của Graph A. Mọi node trong Graph B đều tồn tại trong Graph A với cùng `node_id`.
- Các cạnh CFG và Data Dependence chỉ được thiết lập giữa các node thuộc $V_A$ (cụ thể là các node câu lệnh hoặc biểu thức có ngữ nghĩa thực thi và thao tác dữ liệu). Không tạo thêm node ảo hay node ngoài hàm.

### 3.3 Miền Cạnh ($E_B$)
$E_B$ là hợp của 3 tập cạnh có loại riêng biệt: $E_B = E_{\text{AST}} \cup E_{\text{CFG}} \cup E_{\text{DDG}}$.

| Loại cạnh | Edge Type ID | Tên định danh | Hướng quan hệ | Ý nghĩa ngữ nghĩa |
| :--- | :---: | :--- | :--- | :--- |
| **AST** | `0` | `"AST"` | `parent -> child` | Quan hệ cú pháp cha-con, kế thừa 100% từ Graph A. |
| **CFG** | `1` | `"CFG"` | `predecessor -> successor` | Luồng điều khiển thực thi giữa các câu lệnh/biểu thức kế tiếp nhau trong hàm. |
| **Data Dependence** | `2` | `"DATA_DEP"` | `def_node -> use_node` | Phụ thuộc dữ liệu (Reaching Definition): Từ câu lệnh gán/định nghĩa biến $v$ đến câu lệnh đọc/sử dụng biến $v$. |

### 3.4 Các thành phần bị loại trừ tường minh (Explicit Exclusions)
Để giữ Graph B là "semantic graph tối thiểu", tránh bùng nổ kích thước và kiểm soát độ phức tạp:
1. **Không đưa Call Graph / Inter-procedural edges**: Không nối sang hàm khác trong cùng file hay project; giữ đúng bài toán function-level.
2. **Không áp dụng Slicing**: Không cắt tỉa graph theo điểm nhạy cảm (sensitive sink/source) vì slicing đòi hỏi phân tích phụ thuộc liên hàm và có thể làm mất ngữ cảnh hàm ban đầu.
3. **Không đưa Dominator Tree / CDG riêng biệt**: Không giữ cạnh `DOMINATE` hoặc `POST_DOMINATE` vì CFG kết hợp AST đã chứa đủ thông tin điều khiển.
4. **Không đưa toàn bộ CPG Overlays**: Loại bỏ các cạnh meta của Joern như `REF` (trỏ đến biến khai báo), `EVAL_TYPE` (kiểu dữ liệu suy diễn), `CONTAINS` (quan hệ chứa đựng của file/namespace).

---

## 4. Đặc tả Node Feature và Chính sách Anti-Leakage Vocabulary

### 4.1 Thuộc tính của Node (Node Attributes)
Mỗi node $u$ trong Graph A và Graph B chứa các thuộc tính sau trước khi mã hóa thành vector:

| Thuộc tính | Kiểu dữ liệu | Mô tả | Ví dụ |
| :--- | :--- | :--- | :--- |
| `node_id` | `int` | Định danh node 0-indexed liên tục trong hàm: $[0, N-1]$. | `14` |
| `node_type` | `string` | Kiểu cú pháp AST chuẩn hóa. | `"Call"`, `"Identifier"`, `"Literal"` |
| `code_token` | `string` | Chuỗi mã nguồn gắn với node sau khi chuẩn hóa bảo thủ. | `"malloc"`, `"size"`, `"<NUM>"` |
| `line_number` | `int` | Số dòng của node trong hàm (1-indexed theo function). | `12` |
| `rel_line_number` | `float` | Vị trí tương đối của dòng: $\frac{\text{line\_number}}{\text{max\_line\_number}} \in [0.0, 1.0]$. | `0.45` |

### 4.2 Chuẩn hóa bảo thủ (Conservative Normalization)
Nhằm tránh việc mô hình học thuộc lòng các tên biến hoặc chuỗi văn bản đặc thù của từng project (project shortcuts), áp dụng quy tắc chuẩn hóa bảo thủ:
1. **Từ khóa và hàm hệ thống**: Giữ nguyên toàn bộ từ khóa C/C++ (`if`, `while`, `for`, `return`, `int`, `char*`, `const`, `struct`...) và các hàm thư viện chuẩn phổ biến liên quan đến an toàn bộ nhớ (`malloc`, `free`, `realloc`, `memcpy`, `memset`, `strncpy`, `sizeof`...).
2. **Identifier (Tên biến, tên hàm nội bộ)**:
   - Tách subtoken theo quy tắc CamelCase và snake_case (ví dụ: `buffer_len` $\rightarrow$ `["buffer", "len"]`, `parseHeader` $\rightarrow$ `["parse", "header"]`).
   - Giữ các subtoken có độ dài $\ge 2$ ký tự, chuyển về chữ thường.
3. **Literals (Hằng số và chuỗi)**:
   - Chuỗi ký tự string literal dài $\rightarrow$ thay bằng token hằng `"<STR>"`.
   - Số nguyên lớn (giá trị $> 100$) hoặc số thực $\rightarrow$ thay bằng token hằng `"<NUM>"`.
   - Hằng số hex (địa chỉ bộ nhớ, bitmask) $\rightarrow$ thay bằng token hằng `"<HEX>"`.
   - Số nguyên nhỏ thông dụng ($0, 1, 2, -1$) được giữ nguyên vì thường mang ý nghĩa logic điều khiển (mã lỗi, chỉ số mảng cơ sở).

### 4.3 Các trường bị CẤM TUYỆT ĐỐI trong Node Feature
Để ngăn chặn hoàn toàn rò rỉ dữ liệu (data leakage) và shortcut learning:
- **CẤM** đưa tên `project` vào bất kỳ trường nào của node.
- **CẤM** đưa `commit_id`, `commit_message`, `cve`, `hash` vào node.
- **CẤM** đưa nhãn `cwe` hoặc target nhị phân vào node.
- **CẤM** đưa tên `split` (`train`, `validation`, `test`) hoặc `group_id` vào graph.

### 4.4 Quy tắc huấn luyện Từ vựng (Vocabulary Anti-Leakage Rules)
1. **Không fit từ vựng toàn cục**: Tuyệt đối không xây dựng tokenizer / vocabulary / dictionary trên toàn bộ 9.077 mẫu.
2. **Fit độc lập theo từng Split Protocol**:
   - Khi chạy thực nghiệm theo **Protocol 1 (Project-wise)**: Bộ từ vựng $\mathcal{V}_{\text{pw}}$ (cho tokens) và $\mathcal{T}_{\text{pw}}$ (cho node types) chỉ được xây dựng từ **6.983 mẫu của tập train** (`data/splits/diversevul_project_wise/train.txt`).
   - Khi chạy thực nghiệm theo **Protocol 2 (Seen-project)**: Bộ từ vựng $\mathcal{V}_{\text{sp}}$ và $\mathcal{T}_{\text{sp}}$ chỉ được xây dựng từ **7.272 mẫu của tập train** (`data/splits/diversevul_seen_project/train.txt`).
3. **Xử lý Out-of-Vocabulary (OOV)**: Mọi token hoặc node type xuất hiện trong validation/test mà không có trong tập train tương ứng sẽ được ánh xạ về token đặc biệt `"<UNK>"`.
4. **Lưu trữ artifact từ vựng**: File từ vựng được xuất độc lập theo tên protocol:
   - `outputs/vocab/vocab_project_wise.json`
   - `outputs/vocab/vocab_seen_project.json`

---

## 5. Nhãn CWE và Ánh xạ Split

### 5.1 Ánh xạ mẫu (`sample_id`)
- Mỗi function trong 9.077 function của dataset có một định danh duy nhất: `sample_id` dạng `row-{index}` (ví dụ: `row-1`, `row-3`, `row-17543`).
- Khóa `sample_id` khớp chính xác với `sample_id` trong file manifest `data/splits/diversevul_experiment_manifest.csv`.
- Mọi artifact graph sẽ được đặt tên theo mẫu: `{sample_id}.json` (tầng trung gian) hoặc `{sample_id}.pt` (tầng tensor).

### 5.2 Bảng ánh xạ 23 nhãn CWE
Theo Task 2.2 (`docs/2_2_cwe_policy.md`), thí nghiệm dùng bài toán multiclass với đúng 23 CWE. Để đảm bảo tính tái lập tuyệt đối, bảng ánh xạ từ nhãn chuỗi gốc sang class index số nguyên $y \in [0, 22]$ được sắp xếp theo thứ tự bảng chữ cái cố định:

| Index ($y$) | Mã CWE | Tên MITRE | Số mẫu Single-label | Tỷ lệ trong 9.077 mẫu |
| :---: | :--- | :--- | :---: | :---: |
| **0** | `CWE-119` | Bounds of a Memory Buffer | 697 | 7,68% |
| **1** | `CWE-120` | Classic Buffer Overflow | 145 | 1,60% |
| **2** | `CWE-125` | Out-of-bounds Read | 1.101 | 12,13% |
| **3** | `CWE-189` | Numeric Errors | 255 | 2,81% |
| **4** | `CWE-190` | Integer Overflow | 441 | 4,86% |
| **5** | `CWE-20` | Improper Input Validation | 873 | 9,62% |
| **6** | `CWE-200` | Exposure of Sensitive Information | 500 | 5,51% |
| **7** | `CWE-22` | Path Traversal | 129 | 1,42% |
| **8** | `CWE-264` | Permissions and Access Controls | 209 | 2,30% |
| **9** | `CWE-295` | Improper Certificate Validation | 98 | 1,08% |
| **10** | `CWE-369` | Divide By Zero | 136 | 1,50% |
| **11** | `CWE-399` | Resource Management Errors | 329 | 3,62% |
| **12** | `CWE-400` | Uncontrolled Resource Consumption | 179 | 1,97% |
| **13** | `CWE-401` | Missing Release of Memory | 184 | 2,03% |
| **14** | `CWE-415` | Double Free | 191 | 2,10% |
| **15** | `CWE-416` | Use After Free | 751 | 8,27% |
| **16** | `CWE-476` | NULL Pointer Dereference | 736 | 8,11% |
| **17** | `CWE-59` | Link Following | 93 | 1,02% |
| **18** | `CWE-617` | Reachable Assertion | 102 | 1,12% |
| **19** | `CWE-703` | Exceptional Condition Check | 362 | 3,99% |
| **20** | `CWE-770` | Allocation Without Limits | 89 | 0,98% |
| **21** | `CWE-787` | Out-of-bounds Write | 1.368 | 15,07% |
| **22** | `CWE-835` | Infinite Loop | 109 | 1,20% |
| **Tổng** | **23 CWE** | — | **9.077** | **100,00%** |

### 5.3 Phân biệt nhãn gốc trong Manifest và nhãn mô hình
- **Nhãn gốc trong Manifest** (`cwe`): Chuỗi ký tự biểu diễn mã lỗ hổng (ví dụ: `"CWE-787"`).
- **Nhãn số hóa cho Huấn luyện** (`y`): Giá trị vô hướng kiểu nguyên (`torch.long`) trong đoạn $[0, 22]$. Ánh xạ hai chiều được thực hiện qua dictionary:
  - $\text{encode}(c) = \text{CWE\_TO\_ID}[c]$
  - $\text{decode}(i) = \text{ID\_TO\_CWE}[i]$

### 5.4 Ánh xạ với hai Protocol Split đã chốt
Mỗi graph được liên kết trực tiếp với metadata phân chia qua `sample_id`:
1. **Protocol 1: Project-wise** (`data/splits/diversevul_project_wise/`):
   - `train.txt`: 6.983 samples (468 projects).
   - `validation.txt`: 1.047 samples (37 projects).
   - `test.txt`: 1.047 samples (33 projects).
2. **Protocol 2: Seen-project** (`data/splits/diversevul_seen_project/`):
   - `train.txt`: 7.272 samples.
   - `validation.txt`: 902 samples.
   - `test.txt`: 903 samples.

---

## 6. Định dạng dữ liệu và Cấu trúc Artifacts

Hệ thống sử dụng **kiến trúc dữ liệu 2 tầng (Two-Tier Architecture)** để tách biệt việc phân tích tĩnh (Static Analysis) khỏi việc nạp mô hình học sâu (GNN Training):

```text
C/C++ Source Code
       │
       ▼ (Task 3.2 / Extractor)
[Tầng 1: Intermediate Graph Artifact (JSON)] ─── Độc lập mô hình, lưu trữ thuộc tính text chuẩn hóa
       │
       ▼ (Task 4.x / PyG Dataset Builder + Split Train Vocab)
[Tầng 2: Processed Graph Tensor (PyG .pt)]   ─── Sẵn sàng nạp vào DataLoader, chống rò rỉ dữ liệu
```

### 6.1 Tầng 1: Định dạng Intermediate Graph (JSON)
Lưu trữ toàn bộ cấu trúc đồ thị trích xuất được dưới định dạng JSON có schema kiểm tra chặt chẽ.

#### Cấu trúc JSON Schema:
```json
{
  "sample_id": "row-1",
  "graph_type": "graph_b",
  "status": "SUCCESS",
  "num_nodes": 4,
  "num_edges": 4,
  "nodes": [
    {
      "id": 0,
      "type": "Method",
      "token": "process_packet",
      "line": 1,
      "rel_line": 0.1
    },
    {
      "id": 1,
      "type": "Call",
      "token": "malloc",
      "line": 3,
      "rel_line": 0.3
    },
    {
      "id": 2,
      "type": "Identifier",
      "token": "buf",
      "line": 3,
      "rel_line": 0.3
    },
    {
      "id": 3,
      "type": "Call",
      "token": "free",
      "line": 8,
      "rel_line": 0.8
    }
  ],
  "edges": [
    {
      "src": 0,
      "dst": 1,
      "type": 0
    },
    {
      "src": 1,
      "dst": 2,
      "type": 0
    },
    {
      "src": 1,
      "dst": 3,
      "type": 1
    },
    {
      "src": 2,
      "dst": 3,
      "type": 2
    }
  ]
}
```

### 6.2 Tầng 2: Định dạng Processed Graph (PyTorch Geometric `Data` `.pt`)
File nhị phân PyTorch Geometric lưu trữ dưới dạng `torch.save(data, path)`:
- `data.x`: Tensor `[N, d_node]` kiểu `torch.float32`, trong đó mỗi dòng là vector feature kết hợp từ:
  - Token embedding (từ từ vựng train).
  - Node type embedding.
  - Vị trí tương đối `rel_line_number` (scalar 1 chiều).
- `data.edge_index`: Tensor `[2, E]` kiểu `torch.long`, trong đó dòng 0 là `src`, dòng 1 là `dst`.
- `data.edge_type`: Tensor `[E]` kiểu `torch.long` biểu diễn ID loại cạnh:
  - Graph A: Mọi giá trị đều là `0`.
  - Graph B: Giá trị nhận trong $\{0, 1, 2\}$ tương ứng AST, CFG, DATA_DEP.
- `data.y`: Tensor `[1]` kiểu `torch.long` chứa class index trong khoảng $[0, 22]$.
- `data.sample_id`: Chuỗi ký tự định danh mẫu (ví dụ: `"row-1"`).
- `data.num_nodes`: Số lượng node $N$.

### 6.3 Quy ước ID Node và Tham chiếu Cạnh
- **ID Node**: Bắt buộc là số nguyên liên tục, đánh số từ `0` đến `N - 1` trong phạm vi mỗi function.
- **Tham chiếu Cạnh**: Mỗi cạnh tham chiếu bằng cặp `(src, dst)` với điều kiện $0 \le src, dst < N$.
- **Không dùng ID toàn cục**: Không dùng ID nguyên bản của Joern (thường là số nguyên rất lớn và không liên tục như `1002345`) trong tensor PyG; phải ánh xạ về miền liên tục $[0, N-1]$.

### 6.4 Biểu diễn Graph Rỗng và Graph Không Hợp Lệ
Một đồ thị có thể không trích xuất được do nhiều nguyên nhân thực tế. Hệ thống quy định rõ các mã trạng thái (`status` enums):
- `SUCCESS`: Trích xuất thành công, $N > 0$ và $E \ge 0$.
- `EMPTY_GRAPH`: Trích xuất hoàn tất nhưng số node $N = 0$ (mã nguồn rỗng hoặc chỉ có comment).
- `PARSE_ERROR`: Lỗi cú pháp mã nguồn C/C++, parser Joern báo lỗi cú pháp hoặc crash.
- `TIMEOUT_ERROR`: Quá trình phân tích tĩnh vượt quá ngưỡng thời gian quy định (`120s`).
- `OVERSIZED_GRAPH`: Đồ thị sinh ra vượt quá trần kích thước quy định.

**Quy tắc xử lý bắt buộc**:
- **KHÔNG âm thầm drop mẫu lỗi**: Nếu xảy ra lỗi hoặc đồ thị rỗng, file trung gian vẫn được ghi lại với `num_nodes: 0, num_edges: 0, nodes: [], edges: []` kèm trường `"status"` tương ứng và lý do `"error_message"`.
- Trạng thái của từng mẫu được ghi đầy đủ vào file `manifest.csv` của thư mục graph để phục vụ việc kiểm tra Cổng (Gate check) và báo cáo coverage.

### 6.5 Giới hạn kích thước đồ thị (Graph Size Limits) và Cơ chế xử lý
Theo kết quả EDA (`docs/1_1_related_work.md`), mã nguồn có median 19 dòng, nhưng có outlier lên tới 24.047 dòng. Để bảo vệ GPU khỏi lỗi tràn bộ nhớ (Out-Of-Memory) và tránh làm chậm đột biến quá trình huấn luyện:
- **Ngưỡng trần kỹ thuật**:
  - `max_nodes`: **1.000 nodes**.
  - `max_edges`: **3.000 edges**.
  - `parse_timeout_seconds`: **120 giây**.
- **Chính sách xử lý đồ thị vượt ngưỡng (`OVERSIZED_GRAPH`)**:
  - Mẫu vượt trần được đánh dấu cờ `status: "OVERSIZED_GRAPH"` trong metadata manifest.
  - Cấu hình hỗ trợ hai chế độ xử lý trong file YAML:
    1. `flag_and_log` (Mặc định cho Gate Pilot): Ghi nhận số lượng mẫu vượt trần để đo lường độ lệch (skew) giữa các class CWE.
    2. `truncate_bfs` (Dự phòng cho GNN batching): Cắt tỉa đồ thị bằng thuật toán BFS bắt đầu từ root AST cho đến khi đạt tối đa 1.000 nodes, đảm bảo đồ thị con vẫn liên thông và bảo toàn vùng quan trọng nhất của hàm.

### 6.6 Cấu trúc thư mục Output trong Repository
Cấu trúc cây thư mục đầu ra được tổ chức chặt chẽ trong `data/graphs/`:
```text
data/graphs/
├── graph_a/
│   ├── manifest.csv               # Báo cáo trích xuất từng mẫu: sample_id, status, num_nodes, num_edges, time_sec
│   ├── raw/                       # Tầng 1: File JSON trung gian độc lập vocab
│   │   ├── row-1.json
│   │   ├── row-3.json
│   │   └── ...
│   └── processed/                 # Tầng 2: File PyG .pt theo từng split
│       ├── project_wise/
│       │   ├── row-1.pt
│       │   └── ...
│       └── seen_project/
│           ├── row-1.pt
│           └── ...
└── graph_b/
    ├── manifest.csv               # Báo cáo trích xuất Graph B
    ├── raw/
    │   ├── row-1.json
    │   └── ...
    └── processed/
        ├── project_wise/
        │   └── ...
        └── seen_project/
            └── ...
```

---

## 7. Kế hoạch kiểm chứng cho Pilot Joern (Chuẩn bị Task 3.2)

### 7.1 Vai trò của Joern
- **Joern là công cụ ứng viên cho giai đoạn pilot, chưa phải quyết định cố định cuối cùng.**
- Nếu pilot cho thấy Joern thất bại nghiêm trọng trên các hàm C/C++ rời rạc của DiverseVul, nhóm nghiên cứu sẽ đánh giá giải pháp thay thế (ví dụ: Tree-sitter cho AST + custom CFG builder hoặc Clang LibTooling).

### 7.2 Manifest Pilot
Pilot ở Task 3.2 sẽ được thực hiện trên đúng tập **30 function đại diện** đã chuẩn bị tại:
`data/sample_manifests/diversevul_graph_sample.csv`.

### 7.3 Các điểm kỹ thuật cần kiểm chứng trong Task 3.2
1. **Phương thức trích xuất và Query Joern**:
   - Thử nghiệm CLI `joern-parse` + `joern-export --repr cpg14/ast/cfg/pdg`.
   - Kiểm chứng lệnh query interactive / script Scala của Joern để xuất đúng 3 lớp quan hệ (`cpg.method.ast`, `cpg.method.cfgFirst`, `cpg.method.reachingDef`) trên cùng một tập node định danh.
2. **Khả năng chia sẻ miền node giữa AST, CFG và DDG**:
   - Xác minh xem các node trong kết quả CFG và PDG của Joern có ánh xạ 1-1 ngược lại các node trong cây AST hay không để đảm bảo $V_B \equiv V_A$.
3. **Các tình huống biên phức tạp của mã nguồn C/C++ trong DiverseVul**:
   - **Hàm rời rạc (Incomplete/Standalone function)**: Hàm thiếu khai báo thư viện `#include`, thiếu định nghĩa `struct`, `typedef`, biến toàn cục. Kiểm tra Joern có parse được cấu trúc AST cơ bản hay bị lỗi dừng hoàn toàn.
   - **Macro tiền xử lý (`#define`, `#ifdef`)**: Hàm chứa macro phức tạp chưa qua preprocessor. Kiểm tra xem Joern có xử lý được hay cần một bước tiền xử lý bọc code (code wrapper).
   - **C++ hiện đại**: Mã nguồn chứa templates, class methods, namespace, toán tử nạp chồng. Kiểm tra tỷ lệ parse thành công trên các mẫu C++ so với C.
4. **Các chỉ số cổng (Pilot Gate Metrics)** cần đo lường:
   - Tỷ lệ parse thành công trên 30 mẫu pilot.
   - Thời gian trích xuất trung bình và bộ nhớ đỉnh cho mỗi function.
   - Dung lượng đĩa trung bình của từng file graph JSON.
   - Phân bố số lượng node và số lượng cạnh của Graph A so với Graph B.

---

## 8. Tóm tắt các quyết định Schema quan trọng

1. **Graph A**: Baseline AST có hướng (`parent -> child`), không lưu cạnh ngược.
2. **Graph B**: Semantic graph tối thiểu, **tái sử dụng 100% miền node của Graph A** ($V_B \equiv V_A$), bổ sung cạnh CFG (`predecessor -> successor`) và Data Dependence (`def -> use`).
3. **Loại trừ**: Tuyệt đối không đưa Call Graph, Slicing, Dominator edges, hoặc các layer overlay CPG mở rộng vào graph lõi.
4. **Node Feature**: `node_type`, `code_token` (chuẩn hóa bảo thủ: tách subtoken identifier, hằng số/chuỗi đại diện), `line_number`, `rel_line_number`. Cấm tuyệt đối project, commit, CVE, CWE.
5. **Anti-Leakage Vocabulary**: Vocabulary/tokenizer chỉ được fit trên tập train của đúng protocol đang chạy (Project-wise train: 6.983 mẫu; Seen-project train: 7.272 mẫu).
6. **Nhãn**: Ánh xạ 23 CWE sang class index $[0, 22]$ theo thứ tự bảng chữ cái cố định; giữ nguyên 9.077 function và hai bộ split đã chốt.
7. **Định dạng dữ liệu**: Kiến trúc 2 tầng (Intermediate JSON $\rightarrow$ Processed PyG `.pt`). Giới hạn trần 1.000 nodes và 3.000 edges. Không âm thầm loại bỏ mẫu lỗi.

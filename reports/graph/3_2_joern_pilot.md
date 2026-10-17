# Task 3.2 — Báo cáo thí điểm trích xuất Graph A/B bằng Joern

Joern `4.0.654`; Query V2: `_joern_script()` trong [`src/graph/joern.py`](../../src/graph/joern.py). SHA256 Query: `5130aa0cef583e99e6ef7f64f13e51473a05f8ebc1a454addb4139f741a22bb5`.

## 1. Giới thiệu

Task 3.2 triển khai và đánh giá khả năng trích xuất đồ thị từ đúng 30 function DiverseVul trong manifest thí điểm, làm căn cứ quyết định trước khi mở rộng ở Task 3.3. Phạm vi chỉ gồm JSON trung gian Tier-1 và phân tích khả năng trích xuất; chưa tạo tensor PyG, ánh xạ nhãn sang chỉ số lớp, huấn luyện hoặc đánh giá mô hình.

Hai biểu diễn tuân theo [đặc tả Task 3.1](../../docs/3_1_graph_schema.md) và [yêu cầu lựa chọn đồ thị](../../docs/1_3_1_4_graph.md):

- Graph A là đồ thị AST có hướng, chỉ chứa quan hệ cha–con cú pháp.
- Graph B dùng chính xác miền nút của Graph A, bổ sung CFG và phụ thuộc dữ liệu DATA_DEP. Mã quan hệ lần lượt là `0` (AST), `1` (CFG), `2` (DATA_DEP).

Kết quả cuối cùng gồm 25 SUCCESS, 3 FAILED, 2 UNSUPPORTED và 0 NOT_RUN. Việc hoàn tất thí điểm chẩn đoán không đồng nghĩa đã xác lập tính đầy đủ ngữ nghĩa hoặc đủ điều kiện mở rộng.

## 2. Công cụ và phương pháp thực hiện

### 2.1. Công cụ và Query

Môi trường đã dùng gồm Joern `4.0.654`, JDK Temurin `21.0.5+11 LTS`, Python 3.14 trên Windows và Ubuntu WSL. Thời hạn là 120 giây cho mỗi giai đoạn phân tích cú pháp/trích xuất. Ngưỡng cảnh báo kích thước là hơn 1.000 nút hoặc 3.000 cạnh; vượt ngưỡng không làm mất cạnh, cắt đồ thị hoặc loại mẫu.

Quy trình dùng `joern-parse` tạo Code Property Graph (CPG), sau đó chạy Query Scala đã định danh ở đầu báo cáo. Query nhập CPG với `enhance = false`, chuẩn bị các lớp `base`, `typerel` (qua `run.typerelations`), `callgraph`, `controlflow`, chọn duy nhất `cpg.method.nameExact(functionName)`, kiểm tra liên kết `METHOD_REF`/`REF` trên CPG, rồi chạy `ossdataflow` khi cần. Không tạo liên kết giả để vượt kiểm tra.

Trích đoạn Query sau thể hiện miền nút và các quan hệ được đọc; điều kiện tiên quyết, kiểm tra lựa chọn Method và toàn bộ nội dung nằm trong mã nguồn được liên kết ở trên:

```scala
val astNodes = method.ast.l
def edgePairs(edgeType: String) = astNodes.flatMap { node =>
  node.outE(edgeType).l.map(edge => (edge.src.id, edge.dst.id))
}
val astEdges = edgePairs(EdgeTypes.AST)
val cfgEdges = edgePairs(EdgeTypes.CFG)
val ddgEdges = edgePairs(EdgeTypes.REACHING_DEF)
```

`REACHING_DEF` được xuất thành DATA_DEP. Chỉ giữ cạnh có cả hai đầu mút ánh xạ vào miền AST; khử cạnh trùng cùng `(src, dst, type)` và loại cạnh tự nối. Tệp lưu trữ không tự thêm cạnh ngược, cạnh liên hàm hoặc các lớp quan hệ CPG khác.

### 2.2. Định danh, xử lý kết quả và triển khai

`row-N` là chỉ số bản ghi chuẩn N bắt đầu từ không, tương ứng dòng vật lý N+1 của dữ liệu JSONL. Mỗi mẫu được đối chiếu `sample_id`, metadata và SHA256 của toàn bộ chuỗi `func` sau giải mã JSON, mã hóa UTF-8, không cắt khoảng trắng, chuẩn hóa xuống dòng hoặc sửa mã nguồn. Phân giải tĩnh và ràng buộc chữ ký hàm có trước kiểm tra Method khi thực thi; hai kiểm tra này không tương đương.

Đồ thị dùng ID nút cục bộ liên tục, cùng thứ tự và miền nút giữa Graph A/B. JSON ghi `sample_id`, `cwe`, `project_wise_split`, `seen_project_split`, `status`, `ddg_status`, `num_nodes`, `num_edges`, các mảng `nodes`/`edges` và `error_message` khi có lỗi. Hai trường split của thí điểm là `null` trong JSON và để trống trong CSV; CWE không phải đặc trưng nút. Nhãn gốc chưa được ánh xạ sang chỉ số lớp.

Mẫu thất bại hoặc không được hỗ trợ vẫn có kết quả trong cả hai manifest và JSON tương ứng. Ba trường hợp FAILED giữ phân loại `AST_EXTRACTION_ERROR`, `ddg_status = NOT_COMPUTED`, mảng nút/cạnh rỗng và lý do lỗi; không được xem là đồ thị được chấp nhận. Hai fragment không có định nghĩa hàm duy nhất được ghi `UNSUPPORTED_SOURCE_REPRESENTATION`, không đoán tên hoặc thêm wrapper. Đồ thị vượt ngưỡng giữ nguyên nội dung với `status = OVERSIZED_GRAPH` và vẫn thuộc nhóm được chấp nhận.

Triển khai tương ứng: [bộ trích xuất Joern](../../src/graph/joern.py), [CLI trích xuất một hàm](../../scripts/extract_graphs.py), [trình điều phối thí điểm](../../scripts/run_graph_extraction.py), [bộ xuất gói bàn giao](../../scripts/export_pilot_delivery.py) và [cấu hình lược đồ](../../configs/graph/schema_spec.yaml). Vị trí cài Joern/JDK có thể cấu hình qua `--joern`, `--joern-parse`, `--java-home` và `--wsl-distro`; không phụ thuộc tên người dùng cụ thể.

## 3. Dữ liệu thí điểm

Nguồn là DiverseVul của dự án `wagner-group/diversevul`, được ghi nhận tại [README của kho mã](../../README.md). Thí điểm dùng đúng [manifest 30 function](../../data/sample_manifests/diversevul_graph_sample.csv), giữ nguyên thứ tự, `sample_id`, dự án, commit, nhãn `vulnerable` và CWE. Manifest nguồn chứa `source_reference` và `source_sha256` để truy nguyên về mã nguồn gốc; không đưa dữ liệu thô vào gói bàn giao.

Chuỗi CWE rỗng được giữ là `""`; chuỗi đa nhãn giữ nguyên thứ tự và dấu phân cách `|`. Không chọn CWE đầu tiên, điền nhãn thiếu hoặc áp dụng bộ lọc 23 lớp của thí nghiệm chính. Không loại bỏ ba mẫu thất bại hay hai fragment không được hỗ trợ.

### 3.1. Danh sách mẫu và kết quả cuối cùng

| sample_id | Function / biểu diễn | Dự án | CWE gốc | Dòng | Parser / kết quả |
| --- | --- | --- | --- | ---: | --- |
| `row-17543` | `pci_populate_msixcap` | acrn-hypervisor | CWE-617\|CWE-703 | 24 | 0 / SUCCESS |
| `row-13809` | `__skb_get_nlattr` | linux | CWE-416\|CWE-125\|CWE-189 | 17 | 0 / SUCCESS |
| `row-12897` | `strings` | rizin | CWE-200\|CWE-787 | 11 | 0 (tái dùng CPG) / SUCCESS |
| `row-4824` | `jas_iccgetuint` | jasper | CWE-20\|CWE-190 | 14 | 0 / SUCCESS |
| `row-8688` | `removePrefix` | envoy | CWE-400\|CWE-703 | 17 | 0 / SUCCESS |
| `row-12023` | `nfc_unregister_device` | linux | "" | 31 | 0 / SUCCESS |
| `row-8932` | đoạn `switch` | libnbd | "" | 8 | NOT_RUN / UNSUPPORTED |
| `row-16198` | đoạn `switch` | re2c | CWE-787 | 4 | NOT_RUN / UNSUPPORTED |
| `row-567` | `_hb_buffer_replace_glyph` | pango | "" | 18 | 0 / SUCCESS |
| `row-13727` | `readDataAvailable` | folly | CWE-125 | 14 | 0 / SUCCESS |
| `row-15771` | `Eval` | tensorflow | CWE-125\|CWE-787 | 51 | 0 / SUCCESS |
| `row-5087` | `git_pkt_parse_line` | libgit2 | CWE-119\|CWE-787 | 77 | 0 / SUCCESS |
| `row-15766` | `EvalImpl` | tensorflow | CWE-125\|CWE-787 | 37 | 0 / SUCCESS |
| `row-4243` | `check_compat_entry_size_and_hooks` | linux | CWE-119\|CWE-787 | 71 | 0 / SUCCESS |
| `row-5662` | `__videobuf_mmap_mapper` | linux | CWE-119\|CWE-787 | 70 | 0 / SUCCESS |
| `row-12672` | `resolve_handle_call` | jdk8u | "" | 15 | 0 / SUCCESS |
| `row-12144` | `ico_read_png` | gimp | "" | 88 | 0 / SUCCESS |
| `row-832` | `suhosin_encrypt_single_cookie` | suhosin | CWE-119 | 52 | 0 / FAILED |
| `row-8975` | `soup_ntlm_response` | libsoup | CWE-125 | 73 | 0 / SUCCESS |
| `row-18735` | `drv_do_color` | ncurses | "" | 80 | 0 / SUCCESS |
| `row-4225` | `ReadWPGImage` | ImageMagick | CWE-119\|CWE-787 | 615 | 0 / SUCCESS |
| `row-16083` | `Compute` | tensorflow | CWE-125\|CWE-824 | 234 | 0 / SUCCESS |
| `row-4718` | `gre_gro_receive` | linux | CWE-400\|CWE-703 | 106 | 0 / SUCCESS |
| `row-3732` | `rename_principal_2_svc` | krb5 | CWE-119\|CWE-772\|CWE-401 | 96 | 0 / SUCCESS |
| `row-16513` | `arp_print` | tcpdump | CWE-125\|CWE-787 | 115 | 0 / SUCCESS |
| `row-145` | `__blockdev_direct_IO` | linux-2.6 | "" | 111 | 0 / SUCCESS |
| `row-6038` | `processCanonCameraInfo` | LibRaw | CWE-119 | 215 | 0 / FAILED |
| `row-1601` | `apply_tiff` | LibRaw | "" | 183 | 0 / FAILED |
| `row-11455` | `lys_extension_instances_free` | libyang | CWE-617 | 194 | 0 / SUCCESS |
| `row-11987` | `libxlDomainEventHandler` | libvirt | CWE-667 | 74 | 0 / SUCCESS |

Cột Parser / kết quả ghi mã thoát Parser và trạng thái cuối của mẫu; `NOT_RUN` nghĩa là chưa thực thi. Độ dài được tính bằng `len(func.splitlines())`, kể cả dòng trống, chú thích và chỉ thị tiền xử lý. Các nhóm CWE, dự án và độ dài cùng kết quả theo nhóm được trình bày một lần tại mục 4.

## 4. Kết quả thực nghiệm

### 4.1. Kết quả tổng thể

Phân tích cú pháp thành công chỉ có nghĩa tiến trình Parser hoàn tất; không chứng minh hàm đích được frontend biểu diễn thành METHOD hoặc đồ thị được chấp nhận. Mẫu số toàn tập là 30; mẫu số thực sự chạy Joern là 28. Lần lặp dùng lại CPG của `row-12897` kế thừa bằng chứng Parser gốc, không được tính thành mẫu hoặc lần phân tích cú pháp mới.

| Đại lượng | Kết quả | Diễn giải |
| --- | ---: | --- |
| SUCCESS được chấp nhận | 25/30 (83.33%) | toàn tập mẫu; gồm cảnh báo vượt ngưỡng kích thước |
| FAILED | 3/30 (10.00%) | lỗi chọn chính xác phương thức ở lần thực thi mới nhất |
| UNSUPPORTED | 2/30 (6.67%) | chính sách đối với đoạn mã gốc; chưa từng đưa vào Joern |
| NOT_RUN | 0/30 (0%) | không còn trường hợp hợp lệ chưa thực thi |
| Mẫu đã thực thi | 28/30 (93.33%) | số mẫu phân biệt đã chạy, không phải số lần thử lịch sử |
| Tiến trình phân tích cú pháp thành công | 28/28 (100.00%) | mẫu phân biệt có bằng chứng phân tích cú pháp thành công thực tế |
| Tiến trình phân tích cú pháp thất bại | 0/28 (0%) | không có lỗi Parser trong 28 mẫu đã chạy |
| Trích xuất đúng phương thức / chấp nhận cấu trúc | 25/28 (89.29%) | mẫu số đã thực thi; 25/30 trên toàn tập |
| Trích xuất đúng phương thức thất bại | 3/28 (10.71%) | không có METHOD phù hợp khi thực thi |

Ở lần thử liên quan mới nhất, số thất bại theo giai đoạn là: phân tích cú pháp 0; nhập CPG/điều kiện tiên quyết 0; chọn chính xác METHOD 3; METHOD_REF/luồng dữ liệu 0. Lịch sử các lần thử không được cộng vào số mẫu cuối cùng.

### 4.2. Kết quả theo CWE

CWE được thống kê theo từng nhãn thành phần: một mẫu đa nhãn đóng góp một lần vào mỗi CWE của nó; nhóm `""` giữ riêng nhãn rỗng. Do các nhóm chồng lấp, không cộng các dòng để suy ra tổng mẫu. Danh sách ở mục 3 giữ nguyên tổ hợp CWE gốc, tránh làm sai nhãn khi diễn giải.

Trong các bảng dưới, `n` là số mẫu của nhóm; cột Parser dùng mẫu số đã chạy, hai cột chấp nhận lần lượt dùng toàn nhóm và mẫu đã chạy. Mọi tiến trình Parser đã chạy trong mỗi nhóm đều thành công; N/A biểu thị không có lần chạy.

| Nhóm | n | Parser / đã chạy | Chấp nhận / n | Chấp nhận / đã chạy | FAILED | UNSUPPORTED |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| "" (rỗng) | 8 | 7/7 (100.00%) | 6/8 (75.00%) | 6/7 (85.71%) | 1 | 1 |
| CWE-119 | 7 | 7/7 (100.00%) | 5/7 (71.43%) | 5/7 (71.43%) | 2 | 0 |
| CWE-125 | 7 | 7/7 (100.00%) | 7/7 (100.00%) | 7/7 (100.00%) | 0 | 0 |
| CWE-189 | 1 | 1/1 (100.00%) | 1/1 (100.00%) | 1/1 (100.00%) | 0 | 0 |
| CWE-190 | 1 | 1/1 (100.00%) | 1/1 (100.00%) | 1/1 (100.00%) | 0 | 0 |
| CWE-20 | 1 | 1/1 (100.00%) | 1/1 (100.00%) | 1/1 (100.00%) | 0 | 0 |
| CWE-200 | 1 | 1/1 (100.00%) | 1/1 (100.00%) | 1/1 (100.00%) | 0 | 0 |
| CWE-400 | 2 | 2/2 (100.00%) | 2/2 (100.00%) | 2/2 (100.00%) | 0 | 0 |
| CWE-401 | 1 | 1/1 (100.00%) | 1/1 (100.00%) | 1/1 (100.00%) | 0 | 0 |
| CWE-416 | 1 | 1/1 (100.00%) | 1/1 (100.00%) | 1/1 (100.00%) | 0 | 0 |
| CWE-617 | 2 | 2/2 (100.00%) | 2/2 (100.00%) | 2/2 (100.00%) | 0 | 0 |
| CWE-667 | 1 | 1/1 (100.00%) | 1/1 (100.00%) | 1/1 (100.00%) | 0 | 0 |
| CWE-703 | 3 | 3/3 (100.00%) | 3/3 (100.00%) | 3/3 (100.00%) | 0 | 0 |
| CWE-772 | 1 | 1/1 (100.00%) | 1/1 (100.00%) | 1/1 (100.00%) | 0 | 0 |
| CWE-787 | 9 | 8/8 (100.00%) | 8/9 (88.89%) | 8/8 (100.00%) | 0 | 1 |
| CWE-824 | 1 | 1/1 (100.00%) | 1/1 (100.00%) | 1/1 (100.00%) | 0 | 0 |

### 4.3. Kết quả theo dự án

| Nhóm | n | Parser / đã chạy | Chấp nhận / n | Chấp nhận / đã chạy | FAILED | UNSUPPORTED |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ImageMagick | 1 | 1/1 (100.00%) | 1/1 (100.00%) | 1/1 (100.00%) | 0 | 0 |
| LibRaw | 2 | 2/2 (100.00%) | 0/2 (0.00%) | 0/2 (0.00%) | 2 | 0 |
| acrn-hypervisor | 1 | 1/1 (100.00%) | 1/1 (100.00%) | 1/1 (100.00%) | 0 | 0 |
| envoy | 1 | 1/1 (100.00%) | 1/1 (100.00%) | 1/1 (100.00%) | 0 | 0 |
| folly | 1 | 1/1 (100.00%) | 1/1 (100.00%) | 1/1 (100.00%) | 0 | 0 |
| gimp | 1 | 1/1 (100.00%) | 1/1 (100.00%) | 1/1 (100.00%) | 0 | 0 |
| jasper | 1 | 1/1 (100.00%) | 1/1 (100.00%) | 1/1 (100.00%) | 0 | 0 |
| jdk8u | 1 | 1/1 (100.00%) | 1/1 (100.00%) | 1/1 (100.00%) | 0 | 0 |
| krb5 | 1 | 1/1 (100.00%) | 1/1 (100.00%) | 1/1 (100.00%) | 0 | 0 |
| libgit2 | 1 | 1/1 (100.00%) | 1/1 (100.00%) | 1/1 (100.00%) | 0 | 0 |
| libnbd | 1 | N/A | 0/1 (0.00%) | N/A | 0 | 1 |
| libsoup | 1 | 1/1 (100.00%) | 1/1 (100.00%) | 1/1 (100.00%) | 0 | 0 |
| libvirt | 1 | 1/1 (100.00%) | 1/1 (100.00%) | 1/1 (100.00%) | 0 | 0 |
| libyang | 1 | 1/1 (100.00%) | 1/1 (100.00%) | 1/1 (100.00%) | 0 | 0 |
| linux | 5 | 5/5 (100.00%) | 5/5 (100.00%) | 5/5 (100.00%) | 0 | 0 |
| linux-2.6 | 1 | 1/1 (100.00%) | 1/1 (100.00%) | 1/1 (100.00%) | 0 | 0 |
| ncurses | 1 | 1/1 (100.00%) | 1/1 (100.00%) | 1/1 (100.00%) | 0 | 0 |
| pango | 1 | 1/1 (100.00%) | 1/1 (100.00%) | 1/1 (100.00%) | 0 | 0 |
| re2c | 1 | N/A | 0/1 (0.00%) | N/A | 0 | 1 |
| rizin | 1 | 1/1 (100.00%) | 1/1 (100.00%) | 1/1 (100.00%) | 0 | 0 |
| suhosin | 1 | 1/1 (100.00%) | 0/1 (0.00%) | 0/1 (0.00%) | 1 | 0 |
| tcpdump | 1 | 1/1 (100.00%) | 1/1 (100.00%) | 1/1 (100.00%) | 0 | 0 |
| tensorflow | 3 | 3/3 (100.00%) | 3/3 (100.00%) | 3/3 (100.00%) | 0 | 0 |

### 4.4. Kết quả theo độ dài function

| Nhóm | n | Parser / đã chạy | Chấp nhận / n | Chấp nhận / đã chạy | FAILED | UNSUPPORTED |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1–25 | 10 | 8/8 (100.00%) | 8/10 (80.00%) | 8/8 (100.00%) | 0 | 2 |
| 26–100 | 12 | 12/12 (100.00%) | 11/12 (91.67%) | 11/12 (91.67%) | 1 | 0 |
| 101–250 | 7 | 7/7 (100.00%) | 5/7 (71.43%) | 5/7 (71.43%) | 2 | 0 |
| >250 | 1 | 1/1 (100.00%) | 1/1 (100.00%) | 1/1 (100.00%) | 0 | 0 |

### 4.5. Phân tích thất bại và fragment

Cả ba mẫu sau đều qua đối chiếu nguồn, phân giải tĩnh và ràng buộc chữ ký; Parser có mã thoát 0, trích xuất có mã thoát 1. Các lớp tiên quyết hoàn tất nhưng không tìm thấy đúng Method, nên thất bại trước kiểm tra METHOD_REF và `ossdataflow`.

| sample_id | Function | Giai đoạn lỗi | Chẩn đoán |
| --- | --- | --- | --- |
| `row-832` | `suhosin_encrypt_single_cookie` | Chọn METHOD | Tên hàm khớp tĩnh nhưng tìm thấy 0 Method khi thực thi. |
| `row-6038` | `processCanonCameraInfo` | Chọn METHOD | Tên hàm khớp tĩnh nhưng tìm thấy 0 Method khi thực thi. |
| `row-1601` | `apply_tiff` | Chọn METHOD | Tên hàm khớp tĩnh nhưng tìm thấy 0 Method khi thực thi. |

Thông báo chung là `Expected exactly one method named <functionName>, found 0`. Ngữ cảnh macro/tệp tiêu đề hoặc hành vi tiền xử lý là giả thuyết có thể giải thích việc thiếu METHOD, chưa phải nguyên nhân đã chứng minh. Không dùng tên thay thế, chế độ Parser khác hoặc hiệu chỉnh nguồn để buộc chấp nhận.

`row-8932` và `row-16198` là đoạn `switch` không có định nghĩa hàm tường minh duy nhất, chưa từng đưa vào Joern. UNSUPPORTED là kết quả của chính sách biểu diễn, không phải lỗi Parser quan sát được. Wrapper hoặc bổ sung context có thể là hướng nghiên cứu riêng, nhưng sẽ thay đổi đầu vào; thí điểm hiện tại không thực hiện các biến đổi đó.

## 5. Phân tích và so sánh Graph A/B

### 5.1. Quy mô và quan hệ đồ thị

| Đại lượng | n | Nhỏ nhất | Trung vị | Trung bình | Lớn nhất | Tổng |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Nút dùng chung | 25 | 5 | 185 | 271.080 | 1863 | 6777 |
| Cạnh A / AST của B | 25 | 4 | 184 | 270.080 | 1862 | 6752 |
| B CFG | 25 | 1 | 152 | 240.360 | 1770 | 6009 |
| B DATA_DEP | 25 | 3 | 342 | 870.400 | 7176 | 21760 |
| Cạnh B | 25 | 8 | 658 | 1380.840 | 10808 | 34521 |

Graph A và Graph B có 6,777 nút trong mỗi tập được chấp nhận, cùng 6,752 cạnh AST. Graph B bổ sung 6,009 CFG và 21,760 DATA_DEP, đạt 34,521 cạnh. Tỷ số tổng cạnh Graph B/A là 5.113; phần tăng là CFG + DATA_DEP. Hai loại dùng chung nút nên không cộng tổng nút của chúng thành số nút phân biệt.

| sample_id | Nút A = B | AST A = B | CFG B | DATA_DEP B | Tổng cạnh B |
| --- | ---: | ---: | ---: | ---: | ---: |
| `row-17543` | 51 | 50 | 39 | 105 | 194 |
| `row-13809` | 75 | 74 | 57 | 119 | 250 |
| `row-12897` | 28 | 27 | 19 | 30 | 76 |
| `row-4824` | 51 | 50 | 36 | 89 | 175 |
| `row-8688` | 11 | 10 | 4 | 13 | 27 |
| `row-12023` | 92 | 91 | 81 | 228 | 400 |
| `row-567` | 49 | 48 | 40 | 79 | 167 |
| `row-13727` | 5 | 4 | 1 | 3 | 8 |
| `row-15771` | 193 | 192 | 159 | 282 | 633 |
| `row-5087` | 249 | 248 | 208 | 501 | 957 |
| `row-15766` | 185 | 184 | 152 | 417 | 753 |
| `row-4243` | 258 | 257 | 222 | 392 | 871 |
| `row-5662` | 279 | 278 | 246 | 578 | 1102 |
| `row-12672` | 47 | 46 | 27 | 172 | 245 |
| `row-12144` | 253 | 252 | 213 | 535 | 1000 |
| `row-8975` | 318 | 317 | 279 | 1099 | 1695 |
| `row-18735` | 168 | 167 | 134 | 329 | 630 |
| `row-4225` | 1863 | 1862 | 1770 | 7176 | 10808 |
| `row-16083` | 5 | 4 | 1 | 3 | 8 |
| `row-4718` | 279 | 278 | 238 | 620 | 1136 |
| `row-3732` | 367 | 366 | 318 | 1356 | 2040 |
| `row-16513` | 323 | 322 | 295 | 675 | 1292 |
| `row-145` | 343 | 342 | 282 | 874 | 1498 |
| `row-11455` | 1111 | 1110 | 1045 | 5743 | 7898 |
| `row-11987` | 174 | 173 | 143 | 342 | 658 |

Tất cả 25 Graph B được chấp nhận có `ddg_status = EDGES_PRESENT`. Trạng thái này kết hợp cạnh được giữ với bằng chứng bắt đầu Method/số definition, lượt phân tích trở về bình thường và overlay cần thiết; không khẳng định phân tích phụ thuộc đầy đủ cho từng Method hoặc toàn mã nguồn.

### 5.2. Đồ thị rỗng, ngoại lệ kích thước và độ bao phủ

Trong các đồ thị được chấp nhận, số trường hợp không nút là 0/25, không cạnh là 0/25; không tính các payload lỗi rỗng vào thống kê này. Hai mẫu `row-4225` và `row-11455` mang `OVERSIZED_GRAPH`, tương ứng 2/25 (8.00%) mẫu được chấp nhận và 2/30 (6.67%) toàn tập. Chúng được giữ đầy đủ, không cắt bớt; không làm tăng số FAILED.

`row-4225` có 1,863 nút và 10,808 cạnh Graph B; `row-11455` có 1,111 nút và 7,898 cạnh Graph B. Ở phía nhỏ, `row-13727` và `row-16083` chỉ có năm nút dù mã nguồn lần lượt dài 14 và 234 dòng. `row-8688` dài 17 dòng nhưng có 11 nút. Số nút nhỏ không chứng minh frontend đúng; các trường hợp này cần kiểm tra độ bao phủ ngữ nghĩa.

### 5.3. Ánh xạ cạnh và kiểm chứng tính nhất quán

| Loại | Thô | Được giữ | Ngoài miền/không ánh xạ được | Trùng lặp | Tự nối |
| --- | ---: | ---: | ---: | ---: | ---: |
| AST | 6752 | 6752 | 0 | 0 | 0 |
| CFG | 6009 | 6009 | 0 | 0 | 0 |
| DATA_DEP | 21877 | 21760 | 22 | 95 | 0 |

Thống kê thô chỉ liệt kê cạnh đi ra từ miền AST được chọn, không phải toàn bộ quan hệ CPG. Với `row-8688`, 37 DATA_DEP thô còn 13 sau khi loại 22 cạnh do miền/không ánh xạ được và 2 cạnh trùng. Không đủ bằng chứng để kết luận cả 22 cạnh đều thuộc thân lambda; miền bị thiếu có thể không sinh ứng viên nào để thống kê.

Cả 25 cặp kết quả gốc được chấp nhận đã qua `validate_artifacts` với nguồn/manifest gốc và `JoernConfig` đóng băng. Kiểm tra xác nhận ID liên tục, trường lược đồ, số lượng khớp mảng, đầu mút hợp lệ, kiểu cạnh cho phép, tập nút và cạnh AST giống nhau giữa A/B, cùng bằng chứng giai đoạn thành công/DDG. Đây là xác nhận cấu trúc và định danh, không phải chứng minh ngữ nghĩa.

Gói bàn giao giữ đủ 30 JSON và một manifest cho mỗi loại. [Manifest Graph A](3_2_pilot/graph_a/manifest.csv) và [manifest Graph B](3_2_pilot/graph_b/manifest.csv) đối chiếu từng `sample_id`, CWE, thứ tự nguồn, trạng thái, tệp JSON, kích thước và SHA256. Kết quả thành công/thất bại giữ đối tượng gốc, bổ sung `source_reference` và `record_kind`; riêng thông điệp lỗi bàn giao dùng định danh nhật ký chỉ lưu cục bộ để tránh lộ đường dẫn cá nhân, không thay phân loại lỗi hoặc đồ thị.

## 6. Thời gian và tài nguyên thực thi

### 6.1. Số liệu theo function

Bảng sau ghi các lần thử đại diện được chấp nhận. Thời gian tính bằng giây; dung lượng là byte của JSON trích xuất gốc trước khi bổ sung metadata bàn giao. Tổng năm tệp gồm hai JSON đồ thị, JSON số liệu đo, `identity.json` và `stages.jsonl`; không bao gồm CPG tạm hoặc cài đặt Joern.

| sample_id | Parser (s) | Trích xuất (s) | Tổng (s) | A gốc (byte) | B gốc (byte) | Năm tệp gốc (byte) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `row-17543` | 21.622 | 30.170 | 51.821 | 13324 | 23062 | 60758 |
| `row-13809` | 7.542 | 31.644 | 39.235 | 19128 | 31041 | 74900 |
| `row-12897` | N/A | 39.927 | 39.992 | 7434 | 10732 | 41161 |
| `row-4824` | 7.330 | 29.422 | 36.796 | 12518 | 20979 | 56591 |
| `row-8688` | 11.191 | 20.863 | 32.074 | 4486 | 5610 | 36834 |
| `row-12023` | 19.565 | 31.020 | 50.642 | 24521 | 45433 | 99075 |
| `row-567` | 7.767 | 29.096 | 36.906 | 13289 | 21321 | 58935 |
| `row-13727` | 7.022 | 31.263 | 38.314 | 1429 | 1694 | 22911 |
| `row-15771` | 7.062 | 29.257 | 36.393 | 54495 | 84655 | 166147 |
| `row-5087` | 6.238 | 25.443 | 31.737 | 67241 | 116134 | 213230 |
| `row-15766` | 8.515 | 28.142 | 36.795 | 48549 | 87666 | 166315 |
| `row-4243` | 8.932 | 37.222 | 46.219 | 66604 | 108905 | 211451 |
| `row-5662` | 7.344 | 27.954 | 35.367 | 70782 | 127720 | 236086 |
| `row-12672` | 6.726 | 29.732 | 36.498 | 13280 | 26762 | 64302 |
| `row-12144` | 7.227 | 29.808 | 37.115 | 66232 | 117634 | 215192 |
| `row-8975` | 16.071 | 31.908 | 48.073 | 80931 | 176568 | 288552 |
| `row-18735` | 7.170 | 30.936 | 38.192 | 43513 | 75216 | 145000 |
| `row-4225` | 8.063 | 37.932 | 46.326 | 492806 | 1125115 | 1706170 |
| `row-16083` | 7.698 | 26.523 | 34.272 | 1496 | 1761 | 22975 |
| `row-4718` | 6.748 | 28.204 | 35.033 | 72000 | 131363 | 238810 |
| `row-3732` | 7.950 | 25.252 | 33.292 | 94358 | 210717 | 343447 |
| `row-16513` | 6.620 | 26.541 | 33.248 | 84710 | 151726 | 267250 |
| `row-145` | 6.939 | 28.294 | 35.348 | 89926 | 170075 | 293811 |
| `row-11455` | 7.960 | 28.992 | 37.166 | 292245 | 766432 | 1101965 |
| `row-11987` | 7.400 | 32.655 | 40.133 | 46432 | 79745 | 158238 |

`row-12897` dùng lần lặp 2 trên CPG được lưu, không phân tích cú pháp lại: thời gian Parser là N/A, tổng chỉ gồm tăng cường/trích xuất. Không cộng các phiên bản hoặc lần lặp thành mẫu bổ sung.

Ba lần thất bại mới nhất có số liệu sau. Sáu tệp gốc gồm `identity.json`, `source.c`, `stages.jsonl`, JSON số liệu đo và hai JSON lỗi; đây là dung lượng bằng chứng cục bộ, không phải kích thước JSON lỗi bàn giao đã loại bỏ đường dẫn cá nhân.

| sample_id | Parser (s) | Trích xuất (s) | Tổng (s) | A gốc (byte) | B gốc (byte) | Số liệu đo (byte) | Sáu tệp gốc (byte) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `row-832` | 6.759 | N/A | 35.313 | 481 | 481 | 862 | 20637 |
| `row-6038` | 5.817 | N/A | 31.086 | 483 | 483 | 860 | 26172 |
| `row-1601` | 6.579 | N/A | 24.565 | 484 | 484 | 864 | 25860 |

`row-8932` và `row-16198` không được thực thi: thời gian Parser, trích xuất và tổng đều N/A. RAM đỉnh của mọi mẫu là N/A (`null`/`not_measured`). Giá trị thiếu không được thay bằng 0; không lấy tổng trừ thời gian Parser để suy ra thời gian trích xuất bị thiếu.

### 6.2. Thống kê tài nguyên và giới hạn đo lường

| Phạm vi / đại lượng (giây) | n | Nhỏ nhất | Trung vị | Trung bình | Lớn nhất | Tổng |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Được chấp nhận / `parse_seconds` | 24 | 6.238 | 7.471 | 9.029 | 21.622 | 216.702 |
| Được chấp nhận / `extraction_seconds` | 25 | 20.863 | 29.422 | 29.928 | 39.927 | 748.200 |
| Được chấp nhận / `total_seconds` | 25 | 31.737 | 36.906 | 38.679 | 51.821 | 966.983 |
| Thất bại / `parse_seconds` | 3 | 5.817 | 6.579 | 6.385 | 6.759 | 19.154 |
| Thất bại / `extraction_seconds` | 0 | N/A | N/A | N/A | N/A | N/A |
| Thất bại / `total_seconds` | 3 | 24.565 | 31.086 | 30.321 | 35.313 | 90.964 |

| Dung lượng gốc (byte) | n | Nhỏ nhất | Trung vị | Trung bình | Lớn nhất | Tổng |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Byte Graph A | 25 | 1429 | 48549 | 71269.160 | 492806 | 1781729 |
| Byte Graph B | 25 | 1694 | 84655 | 148722.640 | 1125115 | 3718066 |
| Byte của năm tệp kết quả công bố | 25 | 22911 | 166147 | 251604.240 | 1706170 | 6290106 |

Đồ thị lớn nhất `row-4225` có JSON A gốc 492806 byte và JSON B gốc 1125115 byte. Dung lượng gói bàn giao có thể khác bảng gốc do metadata và cách trình bày lỗi; kích thước thực của từng JSON bàn giao nằm trong hai manifest.

Tổng thời gian đại diện không phải thời gian thực liên tục của toàn bộ thí điểm và không bao gồm lịch sử các lần thử. Các nhật ký giai đoạn mới nhất được kiểm tra không ghi nhận hết thời gian. Chưa có phép đo RAM đỉnh, kết luận hiệu quả bộ nhớ hoặc giới hạn tài nguyên đáng tin cho toàn bộ tập dữ liệu.

## 7. Đánh giá và hạn chế

- Mức hoàn tất: mọi mẫu gốc đều có kết quả A/B và truy nguyên đúng định danh, nguồn, CWE; 25/30 được chấp nhận. Không loại thất bại, fragment hoặc đồ thị vượt ngưỡng để làm tăng tỷ lệ thành công.
- Giới hạn đầu vào: phân giải tĩnh không bảo đảm frontend tạo Method tương ứng. Macro, khai báo thư viện, `struct`, `typedef` hoặc context dự án có thể ảnh hưởng biểu diễn; ba thất bại cuối chưa có nguyên nhân frontend được chứng minh. Hai fragment cần chính sách wrapper/context riêng nếu khảo sát tiếp.
- Giới hạn miền: miền dùng chung là AST của một METHOD được chọn, không tự mở rộng sang METHOD lambda lồng nhau, biến được bắt giữ hoặc toàn bộ phạm vi hàm theo văn bản. Lọc đầu mút ngoài miền có thể mất phụ thuộc liên quan đến bảo mật, dù hợp lệ về cấu trúc.
- Giới hạn ánh xạ/DDG: mô tả ánh xạ dự phòng tổng quát trong schema và cơ chế hiện hành chỉ dựa trên ID không hoàn toàn tương đương. `EDGES_PRESENT` không chứng minh độ đầy đủ; ngữ nghĩa bí danh/lời gọi và tác động liên kết tiền xử lý còn bất định. Khác biệt tập phụ thuộc V1/V2 không đủ xác lập nguyên nhân. Các lần lặp cùng cấu hình chỉ hỗ trợ tính lặp lại đồ thị đã quan sát; thứ tự DDG thô và byte CPG tăng cường có thể khác.
- Giới hạn suy rộng: tập mẫu nhỏ được chọn và toàn bộ nhãn gốc là `vulnerable`; tỷ lệ theo CWE/dự án/độ dài chỉ mang tính mô tả. FAILED và UNSUPPORTED không phải nhãn âm của mô hình. Chưa có bằng chứng Graph B dự đoán CWE tốt hơn Graph A.
- Khoảng trống đo lường: thiếu RAM đỉnh, thời gian trích xuất riêng của ba lần thất bại và so sánh C/C++ dựa trên nhãn ngôn ngữ đáng tin. Không thể kết luận về hiệu quả bộ nhớ hoặc so sánh tỷ lệ thành công theo ngôn ngữ từ bằng chứng hiện có.
- Tái lập và công bố: mã nguồn, Query, cấu hình, manifest và gói JSON đủ để kiểm tra cấu trúc, nhãn và SHA256 tệp bàn giao từ bản checkout bảo toàn byte. Tái lập thực thi gốc còn cần dữ liệu thô, Joern/JDK tương ứng và bằng chứng lịch sử chỉ lưu cục bộ; không đưa `data/graphs/`, cài đặt runtime hoặc `.cpg` vào PR. Loại bỏ đường dẫn cá nhân không xác lập quyền phân phối lại DiverseVul/mã nguồn dự án gốc; vẫn cần phê duyệt quyền và ghi nhận nguồn.

## 8. Kết luận

Task 3.2 đã hoàn tất triển khai thí điểm chẩn đoán và các đầu ra bàn giao: `src/graph/joern.py`, `scripts/extract_graphs.py`, báo cáo này, hai manifest và 60 JSON trong `reports/graph/3_2_pilot/`. Mỗi loại đồ thị có 30 kết quả theo đúng tập mẫu gốc: 25 SUCCESS, 3 FAILED, 2 UNSUPPORTED, 0 NOT_RUN. Parser thành công ở 28/28 mẫu đã thực thi; chấp nhận đồ thị đạt 25/28 mẫu đã chạy và 25/30 toàn tập.

Các yêu cầu báo cáo cốt lõi về tỷ lệ Parser theo mẫu/CWE/dự án/độ dài, giai đoạn lỗi, quy mô/loại cạnh, ngoại lệ kích thước, thời gian/dung lượng và truy nguyên nhãn đã được đáp ứng. Những khoảng trống về RAM đỉnh, thời gian riêng bị thiếu, so sánh ngôn ngữ và độ đầy đủ ngữ nghĩa được giữ là giới hạn; không diễn giải chúng thành phép đo hoặc khẳng định đã có.

Quyết định cho Task 3.3 vẫn là NO-GO đối với trích xuất ngay 9,077 bản ghi. Đây là giới hạn mở rộng, không phải phủ nhận việc hoàn tất Task 3.2. Trước khi mở rộng cần:

1. Đối chiếu thủ công mã nguồn với miền nút/phụ thuộc ở `row-8688`, hai trường hợp năm nút, một đồ thị vượt ngưỡng và một đối chứng thông thường; thống nhất tiêu chí đầy đủ ngữ nghĩa.
2. Làm rõ ba thất bại chọn Method và chính sách đối với fragment, macro hoặc context mà không sửa âm thầm đầu vào.
3. Đo RAM đỉnh, bổ sung số liệu tài nguyên còn thiếu và lập kế hoạch quy mô dựa trên thí nghiệm giới hạn được phê duyệt riêng.

Không tự động chuyển sang trích xuất toàn bộ tập dữ liệu, huấn luyện hoặc đánh giá mô hình.

# Quy ước cho 4.1b, 4.1c, 4.2, 4.3, 4.5 (và 5.x dùng lại kết quả)

Đọc trước khi chạy, theo thứ tự:
1. `docs/4_0_data_interface_spec.md` (v1.2): định dạng dữ liệu.
2. `reports/graph/4_0_processed_data.md`: số liệu và giới hạn của dữ liệu.
3. `reports/graph/4_1a_baselines_gnn.md`: kết quả mặc định, mục 5 là gợi ý tinh chỉnh.
4. Xem `notebooks/4_1a_gnn.ipynb` làm mẫu cho notebook mới.

## Dữ liệu
- Input duy nhất: Kaggle Dataset `DiverseVul 9077 - Processed Graph Data`. Không xử lý lại graph, không dùng bản xử lý riêng.
- Không sửa tệp `.pt`, không chia lại split. Cần thêm trường hoặc đổi cách xử lý thì báo Mai, sửa `src/graph/processed.py`, tăng phiên bản spec, chạy lại notebook `4_0_build_processed`.
- Protocol chính là `project_wise` (không dự án nào lặp giữa train và test). `seen_project` có 5 mẫu validation và 6 mẫu test trùng input với train, nêu rõ khi báo cáo.
- Graph quá lớn mặc định giữ nguyên. Dùng `--max-nodes` thì ghi ngưỡng trong báo cáo, cột `max_nodes` của `results.csv` đã có sẵn.

## Mã và Git
- Mã nằm trong `src/` và `scripts/` trên `main`. Notebook chỉ clone `main` rồi gọi script, không nhúng mã vào notebook.
- Cần tính năng mới thì sửa một lần trong `src/`, `scripts/`, có test, rồi mọi notebook dùng chung. Không copy mã sang chỗ khác.
- Mỗi task một nhánh `feature/<tên task>`. Chỉ mở PR khi task xong, rồi merge luôn. Không mở PR cho từng bước.
- Commit ký tên người làm, không thêm Co-Authored-By hay dòng trailer của công cụ. Thông điệp commit ngắn, trung tính.
- Notebook đã chạy (có log) commit vào `reports/graph/`, kèm thư mục kết quả như `4_1a_results/`.

## Cách chạy và so sánh
- Seed 42, 43, 44. Báo trung bình ± độ lệch chuẩn. Chênh lệch nhỏ hơn độ lệch chuẩn giữa seed thì không kết luận hơn hay kém.
- Chọn cấu hình và epoch theo validation. Test chỉ dùng để báo cáo cấu hình đã chọn, không chọn cấu hình theo test.
- Mỗi lần chỉ đổi một thứ so với mặc định. Ghi giả thuyết trước khi chạy, ghi mọi cấu hình đã thử kể cả cấu hình không tốt hơn.
- Trước khi chạy, Mai và Hoàng thống nhất số cấu hình sẽ thử cho 4.1b và 4.2, để so sánh công bằng. Ghi con số này vào báo cáo.
- Chạy cả hai protocol, cả hai loại graph theo đúng mô tả task trong plan.
- Metric: Macro-F1 tính trên cả 23 nhãn (chính), weighted-F1, MCC, accuracy, per-CWE, confusion matrix, thời gian, VRAM, số tham số.
- Mốc phải đặt cạnh: bản mặc định của 4.1a và baseline token (test: 0,100 cho project_wise, 0,170 cho seen_project).

## Đầu ra
- Dùng đúng tên và cột như 4.1a: `results.csv`, `per_class.csv`, `confusion_matrices.json`, `training_history.json`, `summary.md`, để gộp và so sánh được.
- Báo cáo `.md` theo bố cục của báo cáo 4.1a: cấu hình, kết quả, nhận xét, giới hạn. Nêu rõ điều chưa kiểm chứng. Không ước lượng số liệu.
- Notebook mới đặt tên theo plan (`4_1b_gcn_tuning`, `4_2_ggnn_tuning`), có bảng đầu notebook gồm Mục đích, Đầu vào, Đầu ra, Máy chạy. Chạy GPU, bật Internet, thư mục tạm đặt ngoài `/kaggle/working`.

## Riêng từng task
- 4.1b, 4.1c: GCN bỏ qua loại cạnh. 4.1c dùng đúng cấu hình đã chọn ở 4.1b.
- 4.2: so GGNN-B với GCN-A, GCN-B sau tinh chỉnh, với mặc định và với baseline token.
- 4.3: thử nghiệm theo bài báo, **thiết kế khác 4.1b và 4.2**. Đây là bài toán đo tác động, không phải chọn cấu hình: ba nhánh C0, P1, P2 được đăng ký trước cùng giả thuyết trong `src/training/paper_experiments.py`, mỗi nhánh chạy ba seed, và test được báo cáo cho **cả ba** nhánh. Không nhánh nào được chọn làm mô hình của nhóm dựa trên điểm test, và không thêm bớt nhánh sau khi đã thấy kết quả.
  - C0 là nhóm đối chứng, dùng cấu hình L1 đã cố định ở 4.2 và **phải chạy lại trong cùng phiên** với P1 và P2. Lý do: 4.2 cho thấy cùng cấu hình B0, cùng seed, cùng phiên bản torch nhưng chạy ở hai phiên khác nhau lệch tới 0,011 Macro-F1, ngang với mọi chênh lệch cần đo. Số của 4.1a, 4.1b và 4.2 chỉ dùng làm tham chiếu lịch sử.
  - P1 đổi đúng một yếu tố: khởi tạo embedding token bằng CodeBERT, qua `scripts/export_token_embeddings.py` rồi `--token-init`. Mỗi protocol có vocabulary riêng nên cần một tệp khởi tạo riêng.
  - P2 đổi đúng một yếu tố: `--loss adaptive`, label smoothing cho nhóm lớp đầu và focal cho nhóm lớp đuôi, cường độ tăng dần theo epoch.
  - Giữ nguyên split, 23 CWE, seed 42, 43, 44 và hai protocol. Ghi cả kết quả không tốt hơn. Kết luận "có tác động" chỉ đưa ra khi trị tuyệt đối của chênh lệch với C0 vượt độ lệch chuẩn lớn hơn giữa hai nhóm.
  - Riêng với P2, phải kiểm tra F1 theo nhóm lớp đầu, giữa, đuôi, vì giả thuyết của nó nói về lớp ít mẫu chứ không chỉ về Macro-F1 tổng.
- 4.5: baseline mô hình text pretrained, **thiết kế khác mọi task trước**. Không dò siêu tham số và không có nhóm đối chứng: cấu hình được chốt một lần từ bài báo trong `src/training/text_experiments.py`, chạy đủ hai protocol với ba seed, test được báo cáo cho đúng cấu hình đó. Mục đích là trả lời "mô hình text pretrained mạnh tới đâu trên split của nhóm", không phải tìm cấu hình text tốt nhất.
  - **Dữ liệu khác mọi task trước.** Mô hình text cần mã nguồn gốc, mà Kaggle Dataset `DiverseVul 9077 - Processed Graph Data` chỉ chứa id token theo vocabulary tự học. Chạy `scripts/build_text_dataset.py` để ghép jsonl DiverseVul thô, manifest split của 2.3 và danh sách mẫu lỗi của 3.3 thành một tệp `.jsonl.gz`, rồi đẩy tệp đó lên Kaggle làm input. Script dừng nếu số mẫu từng split lệch khỏi dữ liệu đã xử lý của 4.0, vì khi đó số của 4.5 không đặt cạnh số của 4.1 đến 4.3 được.
  - Hàm dài hơn 512 token được cắt thành nhiều đoạn 512 rồi max-pooling, theo EMNLP 2024. Bài báo cắt làm hai đoạn nên `max_chunks` mặc định là 2. Phải báo cáo tỷ lệ hàm bị cắt bỏ một phần cùng tỷ lệ token giữ lại, vì đây là giới hạn của baseline này.
  - Learning rate 2e-5 và tối đa 10 epoch lấy từ PrimeVul. Bài EMNLP 2024 không công bố learning rate, batch size hay optimizer, nên những giá trị còn lại là thông lệ fine-tune transformer và phải ghi rõ là thông lệ chứ không phải trích từ bài báo.
  - Giữ class-weighted cross-entropy, 23 CWE, seed 42, 43, 44 và hai protocol như mọi task trước. Metric chính vẫn là Macro-F1. Bài EMNLP 2024 báo accuracy và weighted-F1 trên dataset khác với split ngẫu nhiên, nên **không so trực tiếp con số của họ với con số của nhóm**.
  - Mốc phải đặt cạnh: baseline token của 4.1a, GNN mặc định của 4.1a, GCN-A tinh chỉnh của 4.1b, GGNN-B tinh chỉnh của 4.2 và ba nhánh của 4.3. Notebook đọc thẳng các số này từ tệp kết quả đã commit qua `text_experiments.reference_results`, không chép tay.
- 5.2, 5.3: dùng kết quả và cấu hình đã chốt ở 4.2, không chạy lại với cấu hình khác mà không ghi lý do.
- 5.3: bỏ CFG hoặc DATA_DEP bằng `--edge-types` (ví dụ `--edge-types 0 2` bỏ CFG, `--edge-types 0 1` bỏ DATA_DEP) trên Graph B, so với GGNN đủ ba loại cạnh ở 4.2.

# Quy ước cho 4.1b, 4.1c, 4.2, 4.3 (và 5.x dùng lại kết quả)

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
- 4.3: chỉ mở khi validation của 4.2 lộ lỗi cụ thể. Giữ nguyên split và 23 CWE, ghi giả thuyết trước khi chạy.
- 5.2, 5.3: dùng kết quả và cấu hình đã chốt ở 4.2, không chạy lại với cấu hình khác mà không ghi lý do.
- 5.3: bỏ CFG hoặc DATA_DEP bằng `--edge-types` (ví dụ `--edge-types 0 2` bỏ CFG, `--edge-types 0 1` bỏ DATA_DEP) trên Graph B, so với GGNN đủ ba loại cạnh ở 4.2.

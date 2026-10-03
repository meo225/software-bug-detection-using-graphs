# Audit dataset DiverseVul

**Trạng thái: BLOCKED - chưa có dữ liệu thô.**

Chưa có thống kê DiverseVul nào được tính. Các file CSV và PNG trong thư mục báo cáo được đánh dấu rõ là file giữ chỗ để tránh hiểu nhầm dữ liệu đầu vào bị thiếu thành kết quả có giá trị bằng 0.

## File dataset thực tế đã sử dụng

Không có. Thư mục dữ liệu thô đã kiểm tra là `D:/PROJECT/software-bug-detection-using-graphs/data/raw/diversevul` và không chứa file dataset thuộc định dạng được hỗ trợ.

Nguyên nhân: `Thư mục dữ liệu thô DiverseVul không tồn tại: D:\PROJECT\software-bug-detection-using-graphs\data\raw\diversevul. Xem hướng dẫn tại data/raw/README.md.`

## Cách cung cấp dữ liệu

1. Tải dataset chính từ đường dẫn trong repository DiverseVul chính thức.
2. Có thể tải thêm metadata commit/repository và bảng label-noise riêng.
3. Đặt các file trong `data/raw/diversevul/`; không commit chúng.
4. Chạy `python scripts/run_diversevul_eda.py --strict` từ thư mục gốc repository.
5. Chạy toàn bộ `notebooks/01_diversevul_eda.ipynb` từ đầu đến cuối để kiểm tra khả năng tái lập ở lớp trình bày.

Runner hỗ trợ CSV, JSON, JSONL/NDJSON, Parquet và file pickle từ nguồn chính thức. Dùng `--dataset-file PATH` nếu có nhiều file có thể là dataset chính. Chỉ dùng pickle từ bản phát hành chính thức đáng tin cậy vì quá trình load pickle có thể thực thi code.

## Schema

Chưa quan sát được. Pipeline sẽ in và xuất các cột, dtype, shape, missingness, ví dụ và ánh xạ đã xác định cho source/label/CWE/project/commit/hash/CVE/repository. Pipeline báo lỗi thay vì tự tạo field bắt buộc không có trong dữ liệu.

## Các kiểm tra đã chuẩn bị nhưng chưa chạy trên DiverseVul

- so sánh số record, vulnerable, non-vulnerable, project, commit và CWE giữa paper và bản dữ liệu thực tế
- coverage CWE chỉ trên vulnerable sample, Top 10/20, phân bố long-tail và coverage tích lũy
- các threshold 20/50/100/200 mà không tự chọn threshold cuối cùng
- tỷ lệ sample có 0, 1 hoặc nhiều CWE và các ví dụ giới hạn
- mức tập trung theo project/CWE và tính khả thi của split tại 2/3/5/10 project
- duplicate chính xác, duplicate sau normalization bảo thủ và label conflict
- source bị thiếu cùng các phân vị độ dài theo ký tự/dòng
- manifest 30 function xác định bằng seed cố định để thử graph
- độ bao phủ khi join metadata và các URL bị thiếu

## Bối cảnh từ paper, không phải kết quả EDA

Baseline so sánh được mã hóa trong audit gồm 349.437 function, 18.945 vulnerable function, 330.492 non-vulnerable function, 797 project, 7.514 commit và 150 CWE. Các số này không bao giờ được dùng thay cho phép đo trên dataset bị thiếu.

Phân tích thủ công trong paper báo cáo độ chính xác của vulnerable-function label chỉ khoảng 60%. Đây là hạn chế của label suy ra từ fixing commit, không phải thống kê được tính lại trên full dataset đang vắng mặt. Repository chính thức cũng cho biết metadata bao phủ 7.512 commit và thiếu ba commit URL so với dataset đã trích xuất.

## Trả lời các câu hỏi nghiên cứu

Q1-Q13 vẫn ở trạng thái **chưa đo được** đối với bản dữ liệu local. Bằng chứng hiện tại chưa đủ để kết luận có bao nhiêu CWE usable, project-wise split có khả thi hay bản DiverseVul này đã sẵn sàng cho bước tạo graph hay chưa.

## Các quyết định nghiên cứu còn mở

Audit không tự chọn Top-K/threshold, chính sách single-label hay multi-label, final split, graph representation, cấu hình Joern hoặc kiến trúc GNN.

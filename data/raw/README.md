# Thiết lập dữ liệu thô

Dữ liệu thô được Git chủ động bỏ qua.

Với DiverseVul, tạo thư mục `data/raw/diversevul/` và đặt file dataset chính thức vào đó. Metadata riêng về commit/repository và bản xuất label-noise chính thức là tùy chọn; có thể đặt cùng thư mục với tên dễ nhận biết chứa `metadata` hoặc `label_noise`.

Nguồn chính thức và đường dẫn tải hiện tại: <https://github.com/wagner-group/diversevul>

Sau đó chạy:

```powershell
python scripts/run_diversevul_eda.py --strict
```

Các định dạng file chính được hỗ trợ gồm CSV, JSON, JSONL/NDJSON, Parquet và pickle. Chỉ load pickle từ bản phát hành chính thức đáng tin cậy. Nếu quá trình dò tìm thấy nhiều file có thể là dataset chính, chỉ định file cần dùng bằng `--dataset-file`.

Không đổi tên field để khớp với pipeline. Quy trình audit ghi nhận schema thực tế và chỉ ánh xạ field khi tên cột đã biết, không mơ hồ hoặc được khai báo tường minh trong config.

# Task 3.3: kế hoạch chạy bù và gộp kết quả

## 1. Hiện trạng sau ba lần chạy đầu

Đối chiếu từng dòng log với `data/splits/diversevul_experiment_manifest.csv` (9.077 mẫu, chỉ số từ 0). Mẫu đã in tiến độ thì cả `graph_a` và `graph_b` đã được ghi xong. Mỗi log là một khoảng liên tục, không có lỗ hổng.

| Lần chạy | Chỉ số đã xong | Sample ID | Số mẫu | Dừng vì |
| :--- | :--- | :--- | ---: | :--- |
| Phân đoạn 1 | 0 đến 767 | `row-1` đến `row-1354` | 768 | Log kết thúc ở 9.934 giây, chưa rõ nguyên nhân |
| Phân đoạn 2 | 3000 đến 5699 | `row-6170` đến `row-10991` | 2.700 | Giới hạn 12 giờ của Kaggle |
| Phân đoạn 3 | 6000 đến 8436 | `row-11507` đến `row-16961` | 2.437 | Giới hạn 12 giờ của Kaggle |

Tổng đã xong: 5.905 mẫu. Còn thiếu 3.172 mẫu:

| Lượt chạy | Chỉ số | Số mẫu | Ước tính |
| :--- | :--- | ---: | :--- |
| `RUN = 1` | 768 đến 1883 | 1.116 | 4 đến 5,5 giờ |
| `RUN = 2` | 1884 đến 2999 | 1.116 | 4 đến 5,5 giờ |
| `RUN = 3` | 5700 đến 5999 | 300 | 1 đến 1,5 giờ |
| `RUN = 4` | 8437 đến 9076 | 640 | 2,5 đến 3,5 giờ |

Ước tính theo tốc độ đo được trong log: 200 đến 280 mẫu mỗi giờ với 4 tiến trình. Đây là ước tính, chưa phải số đo của các lượt này.

Các mẫu đang chạy dở lúc phiên bị dừng (tối đa 4 mẫu ngay sau mỗi đoạn đã xong) có thể có `graph_a` mà thiếu hoặc ghi dở `graph_b`. Chúng nằm trong các đoạn còn thiếu ở trên và sẽ được chạy lại.

## 2. Chạy bù

Dùng `notebooks/3_3_graph_extraction.ipynb`. Mỗi lượt là một version Kaggle riêng:

1. Đổi `RUN` ở mục 4 (1 đến 4), chọn Save & Run All.
2. Sau khi chạy xong, kiểm tra cell cuối: số `graph_a` và `graph_b` phải bằng số mẫu mong đợi.
3. Nếu lượt chạy dừng sớm do `--max-runtime-hours`, chạy lại cùng `RUN`. Mẫu đã xong được bỏ qua.

Notebook ghim Joern `v4.0.654`. Ba lần chạy đầu không ghim phiên bản nên đã cài bản Joern mới nhất tại thời điểm chạy (22/10/2026), chưa rõ số phiên bản. Ghi điều này vào báo cáo khi dùng lại kết quả cũ.

## 3. Gộp kết quả

Nên gộp ngay trên Kaggle để không phải tải hàng nghìn tệp về máy. Tạo một notebook mới, Add Input toàn bộ output của ba lần chạy đầu và bốn lượt chạy bù, rồi chạy:

```python
import subprocess
from pathlib import Path

subprocess.run(["git", "clone", "--branch", "feature/3_3_graph-extract",
                "https://github.com/meo225/software-bug-detection-using-graphs.git",
                "/kaggle/working/repo"], check=True)

# Thứ tự quan trọng: output_batch_* (cũ) trước, output_range_* (mới) sau.
# Tệp trùng tên được ghi đè bởi thư mục đứng sau, nên bản chạy bù thay cho bản ghi dở.
dirs = sorted(
    {p.parent for p in Path("/kaggle/input").rglob("graph_a") if (p.parent / "graph_b").is_dir()},
    key=lambda p: p.name,
)
print(*dirs, sep="\n")
```

```python
%cd /kaggle/working/repo
!python scripts/merge_and_report_3_3.py --batch-dirs {" ".join(map(str, dirs))} --output-dir /kaggle/working/subset_9077 --report-out /kaggle/working/3_3_extraction.md --joern-version "4.0.654 (ba lần chạy đầu không ghim phiên bản)"
```

Kết quả: `subset_9077/graph_a`, `subset_9077/graph_b` (kèm `manifest.csv`), `3_3_extraction.md` và `3_3_failed_samples.csv`.

Điều kiện nghiệm thu: báo cáo ghi "Tỷ lệ bao phủ: 100%" và hợp lệ cộng bị loại bằng 9.077. Nếu còn "mẫu chưa xử lý", danh sách nằm trong `3_3_failed_samples.csv` với trạng thái `NOT_PROCESSED`; chạy bù các mẫu đó rồi gộp lại.

## 4. Lưu trữ và commit

Theo yêu cầu của task, graph không được commit.

- Commit lên nhánh: `3_3_extraction.md` vào `reports/graph/` và `3_3_failed_samples.csv` cùng thư mục.
- Không commit: `subset_9077/` và các thư mục `output_*`.
- Dữ liệu graph: lưu thành Kaggle Dataset riêng tư (Save Version, rồi New Dataset từ Output của notebook gộp), chia sẻ cho cả nhóm. Phase 4 huấn luyện trên Kaggle nên đọc trực tiếp từ dataset này. Nên tải thêm một bản zip lên Google Drive của nhóm để dự phòng.

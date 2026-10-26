# Task 3.3: kế hoạch chạy bù và gộp kết quả

## 1. Hiện trạng sau ba lần chạy đầu

Đối chiếu từng dòng log và `manifest_batch_N.csv` với `data/splits/diversevul_experiment_manifest.csv` (9.077 mẫu, chỉ số từ 0). Log và manifest khớp hoàn toàn về tập mẫu, trạng thái và số node, số cạnh. Mẫu đã có dòng trong manifest thì cả `graph_a` và `graph_b` đã được ghi xong. Mỗi lần chạy là một khoảng liên tục, không có lỗ hổng.

| Lần chạy | Chỉ số đã xong | Số mẫu | Output | Ghi chú |
| :--- | :--- | ---: | :--- | :--- |
| Phân đoạn 1 | 0 đến 767 (`row-1` đến `row-1354`) | 768 | Không còn | Log kết thúc ở 9.934 giây, không có output nên chạy lại toàn bộ chỉ số 0 đến 2999 |
| Phân đoạn 2 | 3000 đến 5699 (`row-6170` đến `row-10991`) | 2.700 | Còn | Dừng ở giới hạn 12 giờ của Kaggle |
| Phân đoạn 3 | 6000 đến 8436 (`row-11507` đến `row-16961`) | 2.437 | Còn | Dừng ở giới hạn 12 giờ của Kaggle |

Hiện có 5.137 mẫu. Còn thiếu 3.940 mẫu: 0 đến 2999, 5700 đến 5999 và 8437 đến 9076.

## 2. Chạy bù

| Lượt chạy | Chỉ số | Số mẫu | Ước tính |
| :--- | :--- | ---: | :--- |
| `RUN = 1` | 0 đến 999 | 1.000 | 3,5 đến 5 giờ |
| `RUN = 2` | 1000 đến 1999 | 1.000 | 3,5 đến 5 giờ |
| `RUN = 3` | 2000 đến 2999 | 1.000 | 3,5 đến 5 giờ |
| `RUN = 4` | 5700 đến 5999 | 300 | 1 đến 1,5 giờ |
| `RUN = 5` | 8437 đến 9076 | 640 | 2,5 đến 3,5 giờ |

Ước tính theo tốc độ đo được trong log: 200 đến 280 mẫu mỗi giờ với 4 tiến trình. Đây là ước tính, chưa phải số đo của các lượt này.

Các mẫu đang chạy dở lúc phiên bị dừng (tối đa 4 mẫu ngay sau mỗi đoạn đã xong) có thể có `graph_a` mà thiếu hoặc ghi dở `graph_b`. Chúng nằm trong các đoạn còn thiếu ở trên và sẽ được chạy lại.

Dùng `notebooks/3_3_graph_extraction.ipynb`. Mỗi lượt là một version Kaggle riêng:

1. Đổi `RUN` ở mục 4 (1 đến 5), chọn Save & Run All.
2. Sau khi chạy xong, kiểm tra cell cuối: số `graph_a` và `graph_b` phải bằng số mẫu mong đợi.
3. Nếu lượt chạy dừng sớm do `--max-runtime-hours`, chạy lại cùng `RUN`. Mẫu đã xong được bỏ qua nếu output cũ được Add Input và chỉ định bằng `--resume-from`.

Notebook ghim Joern `v4.0.654`. Hai lần chạy đầu còn output không ghim phiên bản nên đã cài bản Joern mới nhất tại thời điểm chạy (22/10/2026), chưa rõ số phiên bản. Ghi điều này vào báo cáo khi dùng lại kết quả cũ.

## 3. Gộp kết quả

Nên gộp ngay trên Kaggle để không phải tải hàng nghìn tệp về máy. Tạo một notebook mới, Add Input output của hai lần chạy còn output (phân đoạn 2 và 3) và năm lượt chạy bù, rồi chạy:

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
!python scripts/merge_and_report_3_3.py --batch-dirs {" ".join(map(str, dirs))} --output-dir /kaggle/working/subset_9077 --report-out /kaggle/working/3_3_extraction.md --joern-version "4.0.654 (các lần chạy đầu không ghim phiên bản)"
```

Kết quả: `subset_9077/graph_a`, `subset_9077/graph_b` (kèm `manifest.csv`), `3_3_extraction.md` và `3_3_failed_samples.csv`.

Về `manifest_*.csv`: mỗi dòng ghi một mẫu đã hoàn tất, được ghi và flush sau khi cặp `graph_a`, `graph_b` của mẫu đó đã lưu xong. Vì vậy manifest là sổ ghi các mẫu đã xong, tương đương log. Cơ chế resume không đọc manifest mà kiểm tra trực tiếp tệp graph, và manifest được dựng lại mỗi lần chạy. Khi gộp, script cảnh báo nếu một mẫu có trong manifest nhưng thiếu hoặc hỏng tệp graph, tức là output bị thiếu so với lần chạy gốc.

Điều kiện nghiệm thu: báo cáo ghi "Tỷ lệ bao phủ: 100%" và hợp lệ cộng bị loại bằng 9.077. Nếu còn "mẫu chưa xử lý", danh sách nằm trong `3_3_failed_samples.csv` với trạng thái `NOT_PROCESSED`; chạy bù các mẫu đó rồi gộp lại.

## 4. Lưu trữ và commit

Theo yêu cầu của task, graph không được commit.

- Commit lên nhánh: `3_3_extraction.md` vào `reports/graph/` và `3_3_failed_samples.csv` cùng thư mục.
- Không commit: `subset_9077/` và các thư mục `output_*`.
- Dữ liệu graph: lưu thành Kaggle Dataset riêng tư (Save Version, rồi New Dataset từ Output của notebook gộp), chia sẻ cho cả nhóm. Phase 4 huấn luyện trên Kaggle nên đọc trực tiếp từ dataset này. Nên tải thêm một bản zip lên Google Drive của nhóm để dự phòng.

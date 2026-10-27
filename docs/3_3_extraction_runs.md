# Task 3.3: kế hoạch chạy bù và gộp kết quả

## 1. Hiện trạng

Đối chiếu từng dòng log và `manifest_*.csv` với `data/splits/diversevul_experiment_manifest.csv` (9.077 mẫu, chỉ số từ 0). Mẫu đã có dòng trong manifest thì cả `graph_a` và `graph_b` đã được ghi xong.

| Lần chạy | Chỉ số | Số mẫu | Output | Ghi chú |
| :--- | :--- | ---: | :--- | :--- |
| Phân đoạn 1 cũ | 0 đến 767 | 768 | Không còn | Bị Kaggle hủy, không giữ output |
| Phân đoạn 2 cũ | 3000 đến 5699 | 2.700 | Còn | Dừng ở giới hạn 12 giờ |
| Phân đoạn 3 cũ | 6000 đến 8436 | 2.437 | Còn | Dừng ở giới hạn 12 giờ |
| Run 1 | 0 đến 767 | 768 | Không còn | Bị hủy sau mẫu thứ 768, cùng vị trí với phân đoạn 1 cũ |
| Run 2 | 1000 đến 1999 | 1.000 | Còn | Chạy xong sau 4h28 |
| Run 3 | 2000 đến 2999 | 1.000 | Còn | Chạy xong sau 4h36 |
| Run 4 | 5700 đến 5999 | 300 | Còn | Chạy xong sau 1h27 |
| Run 5 | 8437 đến 8677 | 241 | Không còn | Bị hủy sau 1h12 |

Còn thiếu 1.640 mẫu: chỉ số 0 đến 999 và 8437 đến 9076.

## 2. Sự cố bị hủy giữa chừng

Run 1 và Run 5 bị hủy khi đang chạy bình thường: không có traceback, không có timeout, không có lỗ hổng trong dãy mẫu đã xong, dòng log cuối trùng với thời điểm Kaggle ghi "Cancelled". Run 1 và phân đoạn 1 cũ dừng cùng ở mẫu thứ 768 (`row-1354`), nên nguyên nhân có thể phụ thuộc vào các mẫu đang chạy lúc đó (chỉ số 768 đến 771) khi bốn JVM chạy song song. Giả thuyết hết RAM chưa được kiểm chứng: các mẫu lớn hơn nhiều (ví dụ `row-17513`, 2.406 dòng) vẫn chạy xong.

Các thay đổi để chẩn đoán và giảm rủi ro:

- `--jvm-heap-gb` (mặc định 4) đặt trần heap cho mỗi JVM qua `JAVA_TOOL_OPTIONS`.
- Mỗi mẫu in dòng `Bắt đầu: <sample_id> ... RAM trống: ...` trước khi chạy và dòng tiến độ kèm RAM còn trống, để biết mẫu nào đang chạy nếu phiên bị hủy.
- Chia nhỏ các lượt chạy: phiên bị hủy không giữ output, nên mỗi lượt chỉ khoảng 1 đến 1,5 giờ chạy.

## 3. Chạy bù

Lượt thăm dò (vài phút mỗi lượt), chạy trước để tìm mẫu gây sự cố:

| Lượt | Chỉ số | Tiến trình | Mục đích |
| :--- | :--- | ---: | :--- |
| `P1` | 760 đến 779 | 4 | Tái hiện sự cố của Run 1 |
| `P2` | 770 | 1 | Mẫu `row-1357` chạy một mình |
| `P3` | 8670 đến 8699 | 4 | Tái hiện sự cố của Run 5 |
| `P4` | 8679 | 1 | Mẫu `row-17527` chạy một mình |

Lượt chạy thật:

| Lượt | Chỉ số | Số mẫu | Ước tính |
| :--- | :--- | ---: | :--- |
| `R1` | 0 đến 249 | 250 | 1 đến 1,5 giờ |
| `R2` | 250 đến 499 | 250 | 1 đến 1,5 giờ |
| `R3` | 500 đến 749 | 250 | 1 đến 1,5 giờ |
| `R4` | 750 đến 999 | 250 | 1 đến 1,5 giờ |
| `R5` | 8437 đến 8656 | 220 | 1 đến 1,3 giờ |
| `R6` | 8657 đến 8866 | 210 | 1 đến 1,3 giờ |
| `R7` | 8867 đến 9076 | 210 | 1 đến 1,3 giờ |

Ước tính theo tốc độ đo được: 200 đến 280 mẫu mỗi giờ khi chạy riêng, chậm hơn khi nhiều version chạy cùng lúc. Nên chạy tối đa 5 version song song.

Nếu một lượt bị hủy, đọc các dòng `Bắt đầu` cuối log để thấy mẫu đang chạy, rồi chạy riêng từng mẫu đó với một tiến trình.

Dùng `notebooks/3_3_graph_extraction.ipynb`. Mỗi lượt là một version Kaggle riêng:

1. Đổi `RUN` ở mục 4 (`P1` đến `P4`, `R1` đến `R7`), chọn Save & Run All.
2. Sau khi chạy xong, kiểm tra cell cuối: số `graph_a` và `graph_b` phải bằng số mẫu mong đợi.
3. Nếu lượt chạy dừng sớm do `--max-runtime-hours`, chạy lại cùng `RUN`. Mẫu đã xong được bỏ qua nếu output cũ được Add Input và chỉ định bằng `--resume-from`.

Notebook ghim Joern `v4.0.654`. Các lần chạy cũ (phân đoạn 2 và 3) không ghim phiên bản nên đã cài bản Joern mới nhất tại thời điểm chạy (22/10/2026), chưa rõ số phiên bản. Ghi điều này vào báo cáo khi dùng lại kết quả cũ.

## 3. Gộp kết quả

Nên gộp ngay trên Kaggle để không phải tải hàng nghìn tệp về máy. Tạo một notebook mới, Add Input output của các lần chạy còn output (phân đoạn 2 và 3 cũ, Run 2, Run 3, Run 4) và các lượt `R1` đến `R7` (các lượt thăm dò `P1` đến `P4` không cần), rồi chạy:

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

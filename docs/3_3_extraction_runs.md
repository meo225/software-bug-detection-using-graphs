# Task 3.3: kế hoạch chạy bù và gộp kết quả

## 0. Bảng theo dõi toàn bộ 9.077 mẫu

Chỉ số theo manifest (0-based). Cập nhật cột "Trạng thái" và "Output" sau mỗi lượt.

| Chỉ số | Sample ID | Lượt | Trạng thái | Output (Kaggle) |
| :--- | :--- | :--- | :--- | :--- |
| 0 đến 249 | `row-1` đến `row-368` | `R1` | Xong, có output | [362693328](https://www.kaggle.com/code/vtnmai/3-3-graph-extraction-fix?scriptVersionId=362693328) |
| 250 đến 499 | `row-369` đến `row-844` | `R2` | Xong, có output | [362693378](https://www.kaggle.com/code/vtnmai/3-3-graph-extraction-fix?scriptVersionId=362693378) |
| 500 đến 749 | `row-847` đến `row-1314` | `R3` | Xong, có output | [362693426](https://www.kaggle.com/code/vtnmai/3-3-graph-extraction-fix?scriptVersionId=362693426) |
| 750 đến 999 | `row-1315` đến `row-1920` | `R4` | Xong, có output (chạy lại với `--skip-samples`, cách ly `row-1355`) | [362879111](https://www.kaggle.com/code/vtnmai/3-3-graph-extraction-fix?scriptVersionId=362879111) |
| 1000 đến 1999 | `row-1921` đến `row-4197` | Run 2 | Xong, 1.000 mẫu | [version 362571092](https://www.kaggle.com/code/vtnmai/3-3-graph-extraction-fix?scriptVersionId=362571092) |
| 2000 đến 2999 | `row-4198` đến `row-6168` | Run 3 | Xong, 1.000 mẫu | [version 362571175](https://www.kaggle.com/code/vtnmai/3-3-graph-extraction-fix?scriptVersionId=362571175) |
| 3000 đến 5699 | `row-6170` đến `row-10991` | Phân đoạn 2 cũ | Xong, 2.700 mẫu | [version 361230135](https://www.kaggle.com/code/nth2k5/3-3-graph-extraction-1/output?scriptVersionId=361230135) |
| 5700 đến 5999 | `row-10992` đến `row-11506` | Run 4 | Xong, 300 mẫu | [version 362569418](https://www.kaggle.com/code/vtnmai/3-3-graph-extraction-fix?scriptVersionId=362569418) |
| 6000 đến 8436 | `row-11507` đến `row-16961` | Phân đoạn 3 cũ | Xong, 2.437 mẫu | [version 361232117](https://www.kaggle.com/code/nth2k5/3-3-graph-extraction-1/output?scriptVersionId=361232117) |
| 8437 đến 8656 | `row-16962` đến `row-17485` | `R5` | Xong, có output | [362693505](https://www.kaggle.com/code/vtnmai/3-3-graph-extraction-fix?scriptVersionId=362693505) |
| 8657 đến 8679 | `row-17486` đến `row-17527` | `R6a` | Xong, có output (`row-17527` và `row-17523` cách ly) | [362922434](https://www.kaggle.com/code/vtnmai/3-3-graph-extraction-fix?scriptVersionId=362922434) |
| 8680 đến 8682 | `row-17558` đến `row-17560` | `R6b` | Chưa chạy, 1 tiến trình. Chứa mẫu gây hủy phiên thứ hai | |
| 8683 đến 8866 | `row-17561` đến `row-18317` | `R6c` | Chưa chạy | |
| 8867 đến 9076 | `row-18344` đến `row-18936` | `R7` | Xong, có output (lần đầu bị Cancel, chạy lại xong) | [362714704](https://www.kaggle.com/code/vtnmai/3-3-graph-extraction-fix?scriptVersionId=362714704) |

Lượt thăm dò `P1` đến `P4` không cần đưa vào bước gộp (xem mục 3).

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

Run 1, Run 5, R4 và R6 bị Kaggle ghi "Cancelled" khi đang chạy bình thường: không có traceback, không có timeout, RAM trống còn khoảng 30 GB, mỗi JVM đã giới hạn heap 4 GB. Run 1 cũ và R4 chết cùng vùng chỉ số 768, Run 5 và R6 chết cùng nhóm 4 mẫu ở chỉ số 8678 đến 8681.

Lần chạy lại `R6` với `row-17527` bị cách ly vẫn bị hủy sau khi `row-17522` hoàn tất (nghi ngờ nằm trong nhóm đang chạy lúc đó: `row-17523`, `row-17558`, `row-17559`, `row-17560`; `row-17523` đã chạy xong khi chạy riêng ở `P2`). Vì vậy `R6` được chia thành `R6a`, `R6b` (1 tiến trình) và `R6c`.

`R6a` (8657 đến 8679, đã cách ly `row-17527`) vẫn bị hủy khi chỉ còn `row-17523` đang chạy, trong khi `row-17523` chạy riêng ở `P2` thì xong sau 18,9 giây. Hai kết quả này mâu thuẫn, nên chưa kết luận được `row-17523` tự nó gây lỗi; nguyên nhân có thể phụ thuộc vào trạng thái phiên hoặc thời điểm. `row-17523` tạm được thêm vào `SKIP_SAMPLES` để `R6a` hoàn tất. Lượt chẩn đoán `D1` chạy lại `R6a` không cách ly `row-17523`, kèm các dòng giám sát bên dưới.

Lượt thăm dò chạy ngày 27/10/2026:

| Lượt | Chỉ số | Tiến trình | Kết quả |
| :--- | :--- | ---: | :--- |
| `P1` | 768 đến 769 | 1 | `row-1355` bắt đầu rồi phiên bị hủy, chưa có mẫu nào xong |
| `P2` | 8678 đến 8681 | 1 | `row-17523` xong (SUCCESS, 322 node, 18,9 giây), rồi `row-17527` bắt đầu và phiên bị hủy |
| `P3` | 768 đến 771 | 4 | Bốn mẫu bắt đầu, phiên bị hủy |
| `P4` | 8678 đến 8681 | 4 | Bốn mẫu bắt đầu, phiên bị hủy |

Kết luận có bằng chứng: `row-1355` (openvpn, chỉ số 768) và `row-17527` (tensorflow, chỉ số 8679) mỗi mẫu một mình đã làm cả phiên Kaggle bị hủy. Đây không phải va chạm giữa các tiến trình và không phải hết RAM của container. Cơ chế cụ thể (bộ nhớ native của Joern, số luồng, hoặc cơ chế giám sát của Kaggle) chưa xác định. `row-1356`, `row-17523`, `row-17558`, `row-17559` chưa được thử riêng sau mẫu gây lỗi, nên chưa loại trừ hoàn toàn.

Xử lý: hai mẫu được cách ly bằng `--skip-samples` (trạng thái `QUARANTINED`, không gọi Joern) và tính vào nhóm mẫu thất bại trong báo cáo. `R4` đã chạy xong với danh sách này. Nếu một lượt khác lại bị hủy, đọc dòng `Bắt đầu` cuối cùng trong log, thêm mẫu đó vào `SKIP_SAMPLES` và chạy lại.

Các thay đổi để chẩn đoán và giảm rủi ro:

- `--jvm-heap-gb` (mặc định 4) đặt trần heap cho mỗi JVM qua `JAVA_TOOL_OPTIONS`.
- Mỗi mẫu in dòng `Bắt đầu: <sample_id> ... RAM trống: ...` trước khi chạy và dòng tiến độ kèm RAM còn trống, để biết mẫu nào đang chạy nếu phiên bị hủy.
- `--skip-samples` cách ly mẫu gây lỗi.
- `--monitor-interval` (mặc định 3 giây) in dòng `Giám sát:` gồm RAM trống, số tiến trình con và luồng, RSS tổng và lớn nhất của các JVM, dung lượng trống của đĩa output và `/tmp`. Dòng cuối trong log trước khi phiên chết cho biết tài nguyên nào bùng nổ.
- Tiến trình cha ghi dòng `Nhận tín hiệu SIGTERM` (hoặc `SIGHUP`) nếu bị hủy từ bên ngoài. Nếu log không có dòng này và dừng đột ngột thì tiến trình bị `SIGKILL` (thường do hết bộ nhớ hoặc bị hệ thống giết).
- Chia nhỏ các lượt chạy: phiên bị hủy không giữ output, nên mỗi lượt chỉ khoảng 1 đến 1,5 giờ chạy.

## 3. Chạy bù

Lượt thăm dò (vài phút mỗi lượt), chạy trước để tìm mẫu gây sự cố:

| Lượt | Chỉ số | Tiến trình | Mục đích |
| :--- | :--- | ---: | :--- |
| `P1` | 768 đến 769 (`row-1355`, `row-1356`) | 1 | Chạy từng mẫu nghi ngờ của R4, dòng `Bắt đầu` cuối trong log là mẫu gây lỗi |
| `P2` | 8678 đến 8681 (`row-17523`, `row-17527`, `row-17558`, `row-17559`) | 1 | Chạy từng mẫu nghi ngờ của R6 |
| `P3` | 768 đến 771 | 4 | Tái hiện nhóm chạy song song của Run 1 cũ |
| `P4` | 8678 đến 8681 | 4 | Tái hiện nhóm chạy song song của Run 5 và R6 |

Nếu `P1` hoặc `P2` chết thì mẫu cuối cùng có dòng `Bắt đầu` là thủ phạm. Nếu `P1` và `P2` chạy xong nhưng `P3` hoặc `P4` chết thì lỗi do chạy song song.

Lượt chạy thật:

| Lượt | Chỉ số | Số mẫu | Ước tính |
| :--- | :--- | ---: | :--- |
| `R1` | 0 đến 249 | 250 | 1 đến 1,5 giờ |
| `R2` | 250 đến 499 | 250 | 1 đến 1,5 giờ |
| `R3` | 500 đến 749 | 250 | 1 đến 1,5 giờ |
| `R4` | 750 đến 999 | 250 | 1 đến 1,5 giờ |
| `R5` | 8437 đến 8656 | 220 | 1 đến 1,3 giờ |
| `R6a` | 8657 đến 8679 | 23 | 10 đến 20 phút |
| `R6b` | 8680 đến 8682 | 3 (1 tiến trình) | vài phút |
| `R6c` | 8683 đến 8866 | 184 | 1 đến 1,3 giờ |
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

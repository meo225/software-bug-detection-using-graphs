# Tìm hiểu software bug detection bằng đồ thị

Môn học: **IE105**

Repository nghiên cứu phát hiện và phân loại software weakness trong mã nguồn C/C++ bằng biểu diễn đồ thị và Graph Neural Network (GNN). Software weakness ở đây là điểm yếu trong mã nguồn có thể liên quan đến lỗ hổng bảo mật. Đây không phải bài toán malware detection.

DiverseVul is currently a candidate primary dataset and is being audited before final selection.

Chưa có kết quả thực nghiệm. Chưa chọn dataset cuối cùng, chưa chốt biểu diễn đồ thị, và chưa huấn luyện model.

## Problem statement

Nhiều công trình phát hiện lỗ hổng bằng học máy dừng ở bài toán nhị phân: một function là vulnerable hoặc non-vulnerable. Nhóm muốn khảo sát bài toán khó hơn: từ source code, xây dựng đồ thị chương trình, rồi dùng GNN để dự đoán **loại CWE**.

Bài toán multiclass chỉ được theo đuổi nếu EDA trên dữ liệu thật cho thấy đủ lớp CWE usable. Ngưỡng tần suất, cách xử lý multi-CWE, chính sách duplicate và chiến lược chia tập là các quyết định nghiên cứu. EDA cung cấp bằng chứng; repository này không tự chốt các quyết định đó.

## Research objective

Mục tiêu cuối cùng dự kiến:

```text
source code → graph → GNN → dự đoán loại CWE
```

Pipeline hiện tại đang được khảo sát:

```text
C/C++ source code
→ function-level sample
→ CWE label
→ static program analysis
→ graph representation
→ Graph Neural Network
→ CWE classification
```

## Current research direction

| Hạng mục | Trạng thái |
| --- | --- |
| Ngôn ngữ | C/C++ |
| Đơn vị mẫu | function |
| Dataset chính | DiverseVul là ứng viên, đang chờ audit |
| Dataset khác | Big-Vul, PrimeVul và dataset mới phải thêm được mà không viết lại toàn bộ pipeline |
| Graph | AST, CFG, data dependency, control dependency, PDG, CPG. **CPG là candidate**, chưa phải quyết định cuối |
| Công cụ trích graph | Joern là phương án dự kiến |
| Model | GCN, GAT, GGNN. Có thể thêm kiến trúc khác sau |

Các nghiên cứu nền tảng đang khảo sát: Devign, ReVeal, DeepWukong, Big-Vul, DiverseVul, PrimeVul.

## Tentative pipeline

```text
C/C++ source code
→ preprocessing
→ graph construction
→ graph representation
→ GNN
→ CWE prediction
```

Vòng đời mà repository này được tổ chức để hỗ trợ:

```text
dataset acquisition
→ EDA
→ preprocessing
→ CWE filtering
→ deduplication
→ dataset splitting
→ graph extraction
→ graph feature construction
→ GNN training
→ validation
→ testing
→ evaluation
→ error analysis
→ experiment tracking
→ reporting
→ demo
```

CPG và Joern được ghi trong tài liệu như **candidate / planned approach**, không phải kết quả đã được xác nhận.

## Repository structure

```text
software-bug-detection-using-graphs/
├── configs/          dataset, graph, model, experiment YAML
├── data/             raw, interim, processed, splits, graphs (dữ liệu lớn không commit)
├── notebooks/        EDA và visualization
├── src/              data, graph, models, training, evaluation, utils
├── scripts/          command-line entry points
├── tests/
├── experiments/      manifest của từng lần chạy, không chứa checkpoint lớn
├── outputs/          checkpoint, prediction, metric, figure, log
├── reports/          kết quả viết được và commit được
└── demo/             placeholder cho demo cuối đồ án
```

- `configs/` giữ tham số nghiên cứu ra khỏi source code.
- `data/splits/` lưu danh sách sample ID cho train, validation và test. Không copy source code thành ba bộ riêng.
- Split phải tái lập được. `train.py` không được tự chia ngẫu nhiên rồi bỏ ID.
- `src/graph/joern.py` cô lập Joern để đổi extractor sau này mà không sửa toàn project.
- Mỗi GNN nằm trong một module riêng. Training loop không gắn cứng một kiến trúc.
- Artifact sinh ra nằm trong `outputs/`, tách khỏi source code.

## Setup

Yêu cầu Python 3.10 trở lên.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

PyTorch và PyTorch Geometric chưa nằm trong `requirements.txt`. Cài chúng khi bắt đầu pha huấn luyện, đúng bản CPU hoặc CUDA của máy.

Chạy lệnh từ thư mục gốc repository.

## Dataset preparation

1. Chọn file config, ví dụ `configs/data/diversevul.yaml`.
2. Tải bản dataset bằng tay vào đường dẫn `local_raw_dir` trong config. Script tải không tự kéo archive lớn.
3. Ghi `version` (tên file, ngày tải, checksum nếu có) vào config. Không sửa dữ liệu để khớp số liệu trong paper.
4. Không commit `data/raw/`, `data/interim/`, `data/processed/`, `data/graphs/`.

```powershell
python scripts/download_data.py --config configs/data/diversevul.yaml
```

Thêm dataset khác bằng một file YAML mới trong `configs/data/` và một loader trong `src/data/loader.py`. Không hard-code pipeline chỉ cho DiverseVul.

Nguồn công bố của DiverseVul: <https://github.com/wagner-group/diversevul>.

## EDA instructions

Notebook hiện có: `notebooks/01_dataset_overview.ipynb`.

Các notebook có thể thêm sau: `02_cwe_analysis.ipynb`, `03_project_analysis.ipynb`, `04_graph_inspection.ipynb`. Logic dùng lại được thì chuyển vào `src/data/`, không để toàn bộ pipeline trong notebook.

Việc cần làm trên DiverseVul, tính từ file đã tải:

- overview: số record, vulnerable / non-vulnerable, schema, missing value
- phân bố CWE và các ngưỡng 20, 50, 100, 200 sample
- multi-CWE
- phân bố theo project và khả năng random / project-wise / chronological split
- duplicate, kể cả hash sau khi chuẩn hóa whitespace và line ending
- chất lượng source code
- dữ liệu có đủ source code để thử trích graph hay không

Chỉ báo cáo. Không xóa duplicate, không chọn Top-K, không chọn ngưỡng, không lấy CWE đầu tiên làm nhãn, không chốt split.

Sau khi chạy trên dữ liệu thật, điền:

- `reports/dataset/dataset_eda.md`
- `reports/dataset/tables/cwe_distribution.csv`
- `reports/dataset/tables/project_distribution.csv`
- `reports/dataset/tables/cwe_project_distribution.csv`
- figure nhỏ trong `reports/dataset/figures/`

Nếu số đếm khác paper, ghi số của file đang dùng, ghi phiên bản dữ liệu, và ghi chỗ khác biệt. Không bịa thống kê.

## Planned graph extraction

Chưa chạy Joern trên toàn bộ dữ liệu.

Hướng dự kiến, sau khi EDA xác nhận source code dùng được:

```powershell
python scripts/extract_graphs.py --config configs/graph/cpg.yaml
```

`configs/graph/cpg.yaml` mô tả CPG như một candidate. AST, CFG, dependency và PDG vẫn còn trong phạm vi khảo sát. Một manifest khoảng 20–50 function có thể được EDA xuất ra để thử Joern; manifest đó chưa được tạo.

## Planned model training

Chưa huấn luyện model. Interface dự kiến:

```text
graph batch → GNN encoder → graph pooling → classifier → CWE logits
```

Module tương ứng: `src/models/gcn.py`, `gat.py`, `ggnn.py`, `classifier.py`. Trainer dùng chung nằm ở `src/training/` và đọc config, không gắn cứng một model.

Lệnh dự kiến:

```powershell
python scripts/preprocess.py --config configs/data/diversevul.yaml
python scripts/create_splits.py --config configs/data/diversevul.yaml --strategy project
python scripts/train.py --config configs/experiment/baseline.yaml
python scripts/evaluate.py --run <experiment-id>
python scripts/run_experiment.py --config configs/experiment/baseline.yaml
```

Các lệnh trên, trừ `download_data.py`, hiện là skeleton và dừng với `NotImplementedError`.

Mỗi experiment cần lưu được: random seed, phiên bản dataset, config tiền xử lý, lớp CWE được chọn, chiến lược split, train/validation/test ID, config graph, config model, hyperparameter và metric. Manifest đặt trong `experiments/`. Checkpoint lớn đặt trong `outputs/checkpoints/` và không commit.

## Evaluation strategy

Metric dự kiến cho phân loại CWE:

- Macro-F1
- Weighted-F1
- Precision, Recall và F1 theo từng CWE
- Confusion matrix
- Accuracy

Accuracy được ghi lại nhưng không phải metric duy nhất, vì dữ liệu vulnerability thường mất cân bằng lớp.

Nếu sau này có thí nghiệm nhị phân vulnerable / non-vulnerable, có thể bổ sung Precision, Recall, F1 và PR-AUC. Phần đó chưa được triển khai.

## Project status

- Đã dựng khung repository cho toàn bộ vòng đời nghiên cứu.
- DiverseVul chưa được audit và chưa được chọn làm dataset cuối cùng.
- Chưa có EDA, chưa có graph, chưa có model, chưa có số liệu thực nghiệm.
- Việc tiếp theo là nhánh `feat/diversevul-eda`: tải DiverseVul, chạy notebook overview, điền báo cáo từ số liệu tự tính.

## Contributor workflow

`main` là nhánh ổn định. Không commit dataset lớn, trọng số model, binary Joern, credential hoặc file `.env`.

Nhánh gợi ý khi công việc bắt đầu, chưa tạo sẵn:

```text
main
├── feat/diversevul-eda
├── feat/graph-extraction
├── feat/gcn
├── feat/gat
├── feat/ggnn
└── feat/evaluation
```

```powershell
git clone https://github.com/meo225/software-bug-detection-using-graphs.git
cd software-bug-detection-using-graphs
git checkout -b feat/diversevul-eda
git add .
git commit -m "feat: add DiverseVul EDA findings"
git push -u origin feat/diversevul-eda
```

Sau đó mở Pull Request vào `main`.

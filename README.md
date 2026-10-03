# Tìm hiểu software bug detection bằng đồ thị

Môn học: IE105

Nghiên cứu phát hiện software weakness trong mã nguồn C/C++ và phân loại CWE bằng biểu diễn đồ thị và Graph Neural Network.

```text
C/C++ source code → preprocessing → graph construction → graph representation → GNN → CWE prediction
```

Cấu hình dataset nằm ở `configs/data/`: DiverseVul, Big-Vul, PrimeVul. Cấu hình đồ thị và model nằm ở `configs/graph/` và `configs/model/`.

## Cấu trúc

```text
configs/       dataset, graph, model, experiment
data/          raw, interim, processed, splits, graphs
notebooks/     01_diversevul_eda.ipynb
src/           data, graph, models, training, evaluation, utils
scripts/       lệnh dòng lệnh
tests/
experiments/   manifest từng lần chạy
outputs/       checkpoint, prediction, metric, figure, log
reports/       báo cáo
demo/
```

`data/splits/` lưu danh sách sample ID. Dữ liệu lớn, đồ thị nhị phân, checkpoint và `.env` không được commit.

## Cài đặt

Python 3.10 trở lên. Chạy lệnh từ thư mục gốc repository.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

## Dữ liệu

DiverseVul: `configs/data/diversevul.yaml`. Nguồn: <https://github.com/wagner-group/diversevul>.

```powershell
python scripts/download_data.py --config configs/data/diversevul.yaml
```

Lệnh in thư mục đích và đường dẫn nguồn. Đặt file vào `local_raw_dir` và ghi `version` trong config.

Notebook: `notebooks/01_diversevul_eda.ipynb`. Báo cáo: `reports/dataset/dataset_eda.md`.

Sau khi đặt dữ liệu thật vào `data/raw/diversevul/`, chạy audit có kiểm tra input:

```powershell
python scripts/run_diversevul_eda.py --strict
jupyter nbconvert --to notebook --execute notebooks/01_diversevul_eda.ipynb --output 01_diversevul_eda.ipynb --output-dir notebooks
```

Nếu chưa có dữ liệu, chạy không có `--strict` sẽ sinh report và artifact placeholder ghi rõ `BLOCKED`; chúng không chứa số liệu paper giả làm kết quả EDA.

## Đóng góp

```powershell
git clone https://github.com/meo225/software-bug-detection-using-graphs.git
cd software-bug-detection-using-graphs
git checkout -b <ten-nhanh>
git push -u origin <ten-nhanh>
```

Mở pull request vào `main`.

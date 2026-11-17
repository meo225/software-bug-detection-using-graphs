"""Task 4.5: baseline mô hình text pretrained trên cùng split với các model graph.

Đây là một baseline, không phải bài toán chọn cấu hình như 4.1b và 4.2, cũng không
phải bài toán đo tác động như 4.3. Cấu hình được chốt trước một lần từ bài báo, chạy
đủ hai protocol với ba seed, và test được báo cáo cho cấu hình đó. Không dò siêu
tham số, vì mục đích là trả lời "mô hình text pretrained mạnh tới đâu trên split của
nhóm", chứ không phải tìm cấu hình text tốt nhất.

Nguồn của từng lựa chọn:

- Cắt hàm dài thành các đoạn 512 token rồi max-pooling: EMNLP 2024, bài 1. Bài báo
  cắt làm hai đoạn, nên ``max_chunks`` mặc định là 2.
- Learning rate 2e-5 và tối đa 10 epoch: PrimeVul, bài 3. Bài EMNLP 2024 không công
  bố learning rate, batch size hay optimizer.
- CodeBERT là lựa chọn chính vì bài 1 báo CodeBERT cho kết quả tốt nhất trong ba
  model họ thử. UniXcoder là lựa chọn thứ hai nếu còn thời gian.
- Class-weighted cross-entropy: giữ đúng quy ước của Task 4.1a để so sánh được.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from statistics import mean, pstdev

PROTOCOLS = ("project_wise", "seen_project")
SEEDS = (42, 43, 44)
SPLITS = ("validation", "test")

#: Tên model trên Hugging Face, theo khóa ngắn dùng trong dòng lệnh và tên thư mục.
MODELS = {
    "codebert": "microsoft/codebert-base",
    "unixcoder": "microsoft/unixcoder-base",
}
PRIMARY_MODEL = "codebert"

#: Cấu hình đã chốt trước khi chạy. Mọi thay đổi phải ghi lý do trong báo cáo.
BASELINE = {
    "max_length": 512,
    "max_chunks": 2,
    "pooling": "max",
    "dropout": 0.1,
    "lr": 2e-5,
    "weight_decay": 0.01,
    "batch_size": 8,
    "max_epochs": 10,
    "patience": 3,
    "warmup_ratio": 0.1,
    "grad_clip": 1.0,
}

HYPOTHESIS = (
    "Mô hình ngôn ngữ đã pretrained trên mã nguồn đọc được định danh, comment và cấu "
    "trúc chuỗi mà graph đã làm mất, nên dự kiến cao hơn mọi biến thể GNN của Task 4.1 "
    "đến 4.3, và là mốc để biết nút thắt nằm ở biểu diễn hay ở quy mô dữ liệu."
)

#: Kết quả các task trước, đọc thẳng từ tệp đã commit thay vì chép tay vào notebook.
REFERENCE_SOURCES = (
    ("reports/graph/4_1a_results/baselines_results.csv", "{model} (4.1a)", ("model",)),
    ("reports/graph/4_1a_results/gnn_results.csv", "{model}-{graph} mặc định (4.1a)",
     ("model", "graph")),
    ("reports/graph/4_1b_results/final/results.csv", "GCN-A tinh chỉnh (4.1b)", ()),
    ("reports/graph/4_2_results/final/results.csv", "GGNN-B tinh chỉnh (4.2)", ()),
    ("reports/graph/4_3_results/arms/C0/results.csv", "C0 đối chứng (4.3)", ()),
    ("reports/graph/4_3_results/arms/P1/results.csv", "P1 khởi tạo CodeBERT (4.3)", ()),
    ("reports/graph/4_3_results/arms/P2/results.csv", "P2 loss thích nghi (4.3)", ()),
)

GRAPH_SHORT = {"graph_a": "A", "graph_b": "B"}


def configuration(model: str = PRIMARY_MODEL, **overrides) -> dict:
    """Cấu hình đầy đủ của một lần chạy, gồm tên model trên Hugging Face."""
    if model not in MODELS:
        raise ValueError(f"Model không hợp lệ: {model!r}. Chọn một trong {sorted(MODELS)}")
    unknown = set(overrides) - set(BASELINE)
    if unknown:
        raise ValueError(f"Tham số không có trong cấu hình đã chốt: {sorted(unknown)}")
    return {"model": model, "model_name": MODELS[model], **BASELINE, **overrides}


def arguments(model: str = PRIMARY_MODEL, **overrides) -> list[str]:
    """Tham số dòng lệnh cho ``scripts/train_text.py``."""
    config = configuration(model, **overrides)
    result = ["--model", config["model"]]
    for name in BASELINE:
        result += ["--" + name.replace("_", "-"), str(config[name])]
    return result


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _label(template: str, row: dict[str, str], keys: tuple[str, ...]) -> str:
    values = {k: row.get(k, "") for k in keys}
    if "graph" in values:
        values["graph"] = GRAPH_SHORT.get(values["graph"], values["graph"])
    if "model" in values:
        values["model"] = values["model"].upper() if values["model"].startswith(("gcn", "ggnn")) \
            else values["model"]
    return template.format(**values)


def reference_results(root: Path, split: str = "test") -> list[dict[str, object]]:
    """Macro-F1 của các task trước, gộp theo seed, đọc từ tệp đã commit trong repo.

    Trả về danh sách bản ghi ``{"label", "protocol", "macro_f1", "std", "n_seeds"}``.
    Tệp thiếu thì bỏ qua, để notebook vẫn chạy được trên bản repo chưa đủ kết quả.
    """
    collected: dict[tuple[str, str], list[float]] = {}
    order: list[tuple[str, str]] = []
    for relative, template, keys in REFERENCE_SOURCES:
        path = Path(root) / relative
        if not path.is_file():
            continue
        for row in _rows(path):
            if row.get("split") != split:
                continue
            key = (_label(template, row, keys), row["protocol"])
            if key not in collected:
                collected[key] = []
                order.append(key)
            collected[key].append(float(row["macro_f1"]))
    return [{"label": label, "protocol": protocol, "macro_f1": mean(values),
             "std": pstdev(values), "n_seeds": len(values)}
            for label, protocol in order for values in [collected[(label, protocol)]]]


def validate_run(directory, model: str = PRIMARY_MODEL, **overrides) -> dict:
    """Kiểm tra một thư mục kết quả đúng là lần chạy đã đăng ký của Task 4.5."""
    directory = Path(directory)
    meta = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    recorded = meta["arguments"]
    expected = configuration(model, **overrides)
    if recorded.get("model") != expected["model"]:
        raise ValueError(f"Model khác cấu hình đã đăng ký: {recorded.get('model')!r}")
    if list(recorded.get("seeds", [])) != list(SEEDS):
        raise ValueError("Lần chạy phải đủ ba seed 42, 43, 44")
    if list(recorded.get("protocols", [])) != list(PROTOCOLS):
        raise ValueError("Lần chạy phải đủ hai protocol")
    if recorded.get("limit"):
        raise ValueError("Lần chạy rút gọn không dùng để báo cáo")
    differing = [name for name in BASELINE if recorded.get(name) != expected[name]]
    if differing:
        raise ValueError(f"Siêu tham số khác cấu hình đã đăng ký: {differing}")
    rows = _rows(directory / "results.csv")
    wanted = {(p, str(s), split) for p in PROTOCOLS for s in SEEDS for split in SPLITS}
    if {(r["protocol"], r["seed"], r["split"]) for r in rows} != wanted:
        raise ValueError("Thiếu kết quả validation hoặc test")
    return meta

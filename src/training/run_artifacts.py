"""Ghi kết quả thực nghiệm dùng chung cho mọi script huấn luyện của Phase 4.

Task 4.1a chốt bộ tệp kết quả ``results.csv``, ``per_class.csv``,
``confusion_matrices.json``, ``training_history.json`` và ``summary.md``. Mọi task
sau dùng đúng bộ này để gộp và so sánh được, nên phần ghi nằm ở một chỗ thay vì
được chép lại trong từng script.
"""

from __future__ import annotations

import csv
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Sequence

FIELD_LABELS = {"protocol": "Protocol", "graph": "Graph", "model": "Model", "split": "Split"}
METRIC_COLUMNS = (("macro_f1", "Macro-F1"), ("weighted_f1", "Weighted-F1"),
                  ("mcc", "MCC"), ("accuracy", "Accuracy"))


def plain(value: Any) -> Any:
    """Chuyển Path và danh sách Path thành chuỗi để ghi được ra JSON."""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    return value


def write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    """Ghi danh sách bản ghi, lấy tên cột từ bản ghi đầu tiên."""
    if not rows:
        return
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def summary_lines(title: str, rows: Sequence[dict[str, Any]],
                  key_fields: Sequence[str]) -> list[str]:
    """Bảng trung bình ± độ lệch chuẩn theo seed, nhóm theo ``key_fields``."""
    groups: dict[tuple, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(tuple(str(row[field]) for field in key_fields), []).append(row)
    headers = [FIELD_LABELS.get(field, field.title()) for field in key_fields]
    headers += [label for _, label in METRIC_COLUMNS] + ["Tham số", "Giây/seed"]
    alignment = [":---"] * len(key_fields) + ["---:"] * (len(METRIC_COLUMNS) + 2)
    lines = [title, "", "Trung bình ± độ lệch chuẩn theo seed.", "",
             "| " + " | ".join(headers) + " |",
             "| " + " | ".join(alignment) + " |"]
    for key, items in sorted(groups.items()):
        cells = [f"{mean(v):.4f} ± {pstdev(v):.4f}"
                 for v in ([item[metric] for item in items] for metric, _ in METRIC_COLUMNS)]
        lines.append(f"| {' | '.join(key)} | {' | '.join(cells)} | {items[0]['n_params']} | "
                     f"{mean(item['train_seconds'] for item in items):.0f} |")
    return lines

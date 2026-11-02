"""Task 4.1a: huấn luyện GCN và GGNN trên Graph A hoặc Graph B từ dữ liệu đã xử lý.

Ví dụ:
    python scripts/train_gnn.py --processed-dir /kaggle/input/<dataset>/processed \
        --out-dir /kaggle/working/gnn_results --models gcn ggnn --graphs graph_a graph_b
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from statistics import mean, pstdev

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import torch  # noqa: E402

from src.graph.processed import SPLITS, load_schema  # noqa: E402
from src.training.gnn_trainer import run_training  # noqa: E402

SCALARS = ("accuracy", "macro_precision", "macro_recall", "macro_f1", "weighted_f1", "mcc")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--processed-dir", type=Path, required=True)
    p.add_argument("--schema", type=Path, default=ROOT / "configs/graph/schema_spec.yaml")
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--protocols", nargs="+", default=["project_wise", "seen_project"])
    p.add_argument("--graphs", nargs="+", default=["graph_a", "graph_b"])
    p.add_argument("--models", nargs="+", default=["gcn", "ggnn"])
    p.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])
    p.add_argument("--dim", type=int, default=128)
    p.add_argument("--num-layers", type=int, default=3)
    p.add_argument("--dropout", type=float, default=0.2)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--weight-decay", type=float, default=1e-4)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--max-epochs", type=int, default=40)
    p.add_argument("--patience", type=int, default=8)
    p.add_argument("--max-nodes", type=int, default=None,
                   help="Cắt graph lớn hơn ngưỡng này (mặc định: giữ nguyên)")
    p.add_argument("--limit", type=int, default=None, help="Chỉ lấy N mẫu đầu mỗi split (chạy thử)")
    return p.parse_args()


def write_csv(path: Path, rows: list[dict]) -> None:
    if rows:
        with open(path, "w", encoding="utf-8", newline="") as h:
            w = csv.DictWriter(h, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)


def main() -> int:
    a = parse_args()
    a.out_dir.mkdir(parents=True, exist_ok=True)
    cwe_mapping = load_schema(a.schema)["cwe_mapping"]
    labels = [c for c, _ in sorted(cwe_mapping.items(), key=lambda kv: kv[1])]
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Thiết bị: {device}; torch {torch.__version__}")

    rows, per_class, matrices, histories = [], [], {}, []
    for protocol in a.protocols:
        vocab = json.loads((a.processed_dir / protocol / "vocab.json").read_text(encoding="utf-8"))
        n_types, n_tokens = len(vocab["node_type"]), len(vocab["token"])
        for graph in a.graphs:
            parts = {s: torch.load(a.processed_dir / protocol / f"{graph}_{s}.pt") for s in SPLITS}
            if a.limit:
                parts = {s: v[: a.limit] for s, v in parts.items()}
            print(f"{protocol}/{graph}: " + ", ".join(f"{s}={len(v)}" for s, v in parts.items())
                  + f"; K={vocab['k']}")
            for kind in a.models:
                for seed in a.seeds:
                    out = run_training(
                        parts["train"], parts["validation"], parts["test"], kind, n_types, n_tokens,
                        labels, seed, a.dim, a.num_layers, a.dropout, a.lr, a.weight_decay,
                        a.batch_size, a.max_epochs, a.patience, True, a.max_nodes, device)
                    tag = f"{protocol}|{graph}|{kind}|{seed}"
                    for split, rep in out["reports"].items():
                        rows.append({"protocol": protocol, "graph": graph, "model": kind, "seed": seed,
                                     "split": split, "n_eval": sum(rep["per_class_support"]),
                                     "best_epoch": out["best_epoch"], "epochs_run": out["epochs_run"],
                                     "n_params": out["n_params"],
                                     "train_seconds": round(out["train_seconds"], 1),
                                     "peak_gpu_mb": out["peak_gpu_mb"],
                                     "max_nodes": a.max_nodes,
                                     **{m: rep[m] for m in SCALARS}})
                        for i, cwe in enumerate(labels):
                            per_class.append({"protocol": protocol, "graph": graph, "model": kind,
                                              "seed": seed, "split": split, "cwe": cwe,
                                              "precision": rep["per_class_precision"][i],
                                              "recall": rep["per_class_recall"][i],
                                              "f1": rep["per_class_f1"][i],
                                              "support": rep["per_class_support"][i]})
                        if seed == a.seeds[0]:
                            matrices[f"{tag}|{split}"] = rep["confusion_matrix"]
                    histories.append({"tag": tag, "history": out["history"]})
                    write_csv(a.out_dir / "results.csv", rows)  # ghi dần để không mất khi phiên chết
                    write_csv(a.out_dir / "per_class.csv", per_class)

    (a.out_dir / "confusion_matrices.json").write_text(json.dumps(matrices), encoding="utf-8")
    (a.out_dir / "training_history.json").write_text(json.dumps(histories), encoding="utf-8")
    groups: dict[tuple, list[dict]] = {}
    for r in rows:
        groups.setdefault((r["protocol"], r["graph"], r["model"], r["split"]), []).append(r)
    lines = ["# Kết quả GNN (Task 4.1a)", "", "Trung bình ± độ lệch chuẩn theo seed.", "",
             "| Protocol | Graph | Model | Split | Macro-F1 | Weighted-F1 | MCC | Accuracy | Tham số | Giây/seed |",
             "| :--- | :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for key, items in sorted(groups.items()):
        def cell(m: str) -> str:
            v = [i[m] for i in items]
            return f"{mean(v):.4f} ± {pstdev(v):.4f}"
        lines.append(f"| {' | '.join(key)} | {cell('macro_f1')} | {cell('weighted_f1')} | {cell('mcc')} | "
                     f"{cell('accuracy')} | {items[0]['n_params']} | "
                     f"{mean(i['train_seconds'] for i in items):.0f} |")
    (a.out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

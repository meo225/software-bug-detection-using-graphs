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
from src.training.gnn_trainer import run_training, evaluate_saved  # noqa: E402

from src.training.gcn_tuning import (  # noqa: E402
    BASELINE, code_identity, environment, data_identity, digest, read_frozen, write_json, checkpoint_path, ARTIFACTS,
)

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
    p.add_argument("--edge-types", type=int, nargs="+", choices=[0, 1, 2], default=None,
                   help="Chỉ giữ các loại cạnh này (0 = AST, 1 = CFG, 2 = DATA_DEP). Mặc định: giữ tất cả")
    p.add_argument("--early-stopping", choices=["macro_f1", "val_loss"], default="macro_f1")
    p.add_argument("--validation-only", action="store_true", help="Never load or evaluate test tensors")
    p.add_argument("--save-checkpoints", action="store_true")
    p.add_argument("--config-id", default="B0")
    p.add_argument("--dataset-id", default="unspecified", help="Dataset name and immutable Kaggle version")
    p.add_argument("--frozen-selection", type=Path, help="Evaluate only the frozen winner, without training")
    p.add_argument("--results-root", type=Path, help="Root of relocated candidate artifacts")
    args = p.parse_args()
    if args.frozen_selection and (args.validation_only or args.limit):
        p.error("Frozen evaluation cannot use --validation-only or --limit")
    if args.edge_types and (args.frozen_selection or args.save_checkpoints):
        p.error("--edge-types chưa dùng được với --frozen-selection hoặc --save-checkpoints")
    if min(args.dim, args.num_layers, args.batch_size, args.max_epochs, args.patience) < 1:
        p.error("Dimension, layers, batch size, epochs and patience must be positive")
    if not 0 <= args.dropout < 1 or (args.max_nodes is not None and args.max_nodes < 1):
        p.error("Invalid dropout or node cap")
    return args


def write_csv(path: Path, rows: list[dict]) -> None:
    if rows:
        with open(path, "w", encoding="utf-8", newline="") as h:
            w = csv.DictWriter(h, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)


def main() -> int:
    a = parse_args()
    # Refuse accidental overwrite of previous experiments, including 4.0/4.1a outputs.
    if a.out_dir.exists() and any(a.out_dir.iterdir()):
        raise FileExistsError(f"Output directory must be empty: {a.out_dir}")
    frozen = read_frozen(a.frozen_selection, ROOT, a.processed_dir, a.schema, a.results_root) if a.frozen_selection else None
    if frozen:
        previous = frozen["winner"]["metadata"]["arguments"]
        for key in (*BASELINE, "protocols", "graphs", "models", "seeds", "config_id", "dataset_id"):
            setattr(a, key, previous[key])
    a.out_dir.mkdir(parents=True, exist_ok=True)
    cwe_mapping = load_schema(a.schema)["cwe_mapping"]
    labels = [c for c, _ in sorted(cwe_mapping.items(), key=lambda kv: kv[1])]
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Thiết bị: {device}; torch {torch.__version__}")

    metadata = {"arguments": {k: str(v) if isinstance(v, Path) else v for k, v in vars(a).items()},
                "code": code_identity(ROOT), "environment": environment(),
                "schema_sha256": digest(a.schema), "inputs": {}, "runs": []}
    if frozen:
        metadata["frozen_selection_sha256"] = digest(a.frozen_selection)
    write_json(a.out_dir / "metadata.json", metadata)
    rows, per_class, matrices, histories = [], [], {}, []
    for protocol in a.protocols:
        vocab = json.loads((a.processed_dir / protocol / "vocab.json").read_text(encoding="utf-8"))
        n_types, n_tokens = len(vocab["node_type"]), len(vocab["token"])
        for graph in a.graphs:
            splits = ("test",) if frozen else (("train", "validation") if a.validation_only else SPLITS)
            parts = {s: torch.load(a.processed_dir / protocol / f"{graph}_{s}.pt", weights_only=True) for s in splits}
            metadata["inputs"][f"{protocol}/{graph}"] = data_identity(a.processed_dir, protocol, graph)
            if a.validation_only or frozen:
                metadata["inputs"][protocol] = metadata["inputs"][f"{protocol}/{graph}"]
            if frozen:
                metadata.setdefault("test_sha256", {})[protocol] = digest(a.processed_dir / protocol / f"{graph}_test.pt")
            if a.limit:
                parts = {s: v[: a.limit] for s, v in parts.items()}
            print(f"{protocol}/{graph}: " + ", ".join(f"{s}={len(v)}" for s, v in parts.items())
                  + f"; K={vocab['k']}")
            for kind in a.models:
                for seed in a.seeds:
                    cfg = {key: getattr(a, key) for key in BASELINE}
                    if frozen:
                        winner = frozen["winner"]
                        entry = next(r for r in winner["metadata"]["runs"]
                                     if r["protocol"] == protocol and r["seed"] == seed)
                        payload = torch.load(checkpoint_path(frozen, entry, a.results_root or a.frozen_selection.parent),
                                             map_location="cpu", weights_only=True)
                        if (payload["configuration"] != cfg or payload["protocol"] != protocol
                                or payload["seed"] != seed or payload["labels"] != labels):
                            raise ValueError("Frozen model identity mismatch")
                        out = evaluate_saved(payload, parts["test"], device)
                    else:
                        out = run_training(
                            parts["train"], parts["validation"], parts.get("test", []), kind, n_types, n_tokens,
                            labels, seed, a.dim, a.num_layers, a.dropout, a.lr, a.weight_decay,
                            a.batch_size, a.max_epochs, a.patience, True, a.max_nodes, device,
                            early_stopping=a.early_stopping, evaluate_test=not a.validation_only,
                            edge_types=tuple(a.edge_types) if a.edge_types else None,
                            return_state=a.save_checkpoints)
                        if a.save_checkpoints:
                            checkpoint = f"{protocol}_{graph}_{kind}_{seed}.pt"
                            state = out.pop("state_dict")
                            payload = {"state_dict": state, "configuration": cfg, "labels": labels,
                                       "protocol": protocol, "seed": seed,
                                       "constructor": dict(kind=kind, n_types=n_types, n_tokens=n_tokens,
                                                           n_classes=len(labels), dim=a.dim,
                                                           num_layers=a.num_layers, dropout=a.dropout),
                                       "training": out}
                            torch.save(payload, a.out_dir / checkpoint)
                            metadata["runs"].append(dict(protocol=protocol, seed=seed, checkpoint=checkpoint,
                                                         sha256=digest(a.out_dir / checkpoint)))
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
                    write_json(a.out_dir / "metadata.json", metadata)

    (a.out_dir / "confusion_matrices.json").write_text(json.dumps(matrices), encoding="utf-8")
    (a.out_dir / "training_history.json").write_text(json.dumps(histories), encoding="utf-8")
    groups: dict[tuple, list[dict]] = {}
    for r in rows:
        groups.setdefault((r["protocol"], r["graph"], r["model"], r["split"]), []).append(r)
    title = (f"# Kết quả {'/'.join(a.models).upper()} {'/'.join(a.graphs)} (cấu hình {a.config_id})"
             if a.validation_only or frozen else "# Kết quả GNN (Task 4.1a)")
    lines = [title, "", "Trung bình ± độ lệch chuẩn theo seed.", "",
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
    metadata["artifacts_sha256"] = {name: digest(a.out_dir / name) for name in ARTIFACTS}
    write_json(a.out_dir / "metadata.json", metadata)
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Task 4.1a: huấn luyện GCN và GGNN trên Graph A hoặc Graph B từ dữ liệu đã xử lý.

Ví dụ:
    python scripts/train_gnn.py --processed-dir /kaggle/input/<dataset>/processed \
        --out-dir /kaggle/working/gnn_results --models gcn ggnn --graphs graph_a graph_b
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import torch  # noqa: E402

from src.graph.processed import SPLITS, load_schema  # noqa: E402
from src.training.gnn_trainer import run_training, evaluate_saved  # noqa: E402

from src.training.gcn_tuning import (  # noqa: E402
    BASELINE, code_identity, environment, data_identity, digest, read_frozen, write_json, checkpoint_path, ARTIFACTS,
    sensitivity_target,
)
from src.training.run_artifacts import plain as _plain, summary_lines, write_csv  # noqa: E402

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
    p.add_argument("--loss", choices=["weighted_ce", "adaptive"], default="weighted_ce",
                   help="adaptive: label smoothing cho lớp đầu, focal cho lớp đuôi, tăng dần theo epoch")
    p.add_argument("--focal-gamma", type=float, default=2.0, help="Chỉ dùng với --loss adaptive")
    p.add_argument("--label-smoothing", type=float, default=0.1, help="Chỉ dùng với --loss adaptive")
    p.add_argument("--head-fraction", type=float, default=0.5,
                   help="Tỷ lệ mẫu train cộng dồn xác định nhóm lớp đầu, chỉ dùng với --loss adaptive")
    p.add_argument("--token-init", type=Path, nargs="+", default=None,
                   help="Một tệp .pt cho mỗi protocol, sinh bởi scripts/export_token_embeddings.py. "
                        "Mỗi tệp tự khai báo protocol của nó, nên thứ tự không quan trọng")
    p.add_argument("--validation-only", action="store_true", help="Never load or evaluate test tensors")
    p.add_argument("--save-checkpoints", action="store_true")
    p.add_argument("--config-id", default="B0")
    p.add_argument("--dataset-id", default="unspecified", help="Dataset name and immutable Kaggle version")
    p.add_argument("--frozen-selection", type=Path, help="Evaluate only the frozen winner, without training")
    p.add_argument("--results-root", type=Path, help="Root of relocated candidate artifacts")
    p.add_argument("--sensitivity-config", default=None,
                   help="With --frozen-selection: evaluate this ranked non-winning configuration on test "
                        "for a sensitivity analysis. Never used to select a configuration")
    args = p.parse_args()
    if args.frozen_selection and (args.validation_only or args.limit):
        p.error("Frozen evaluation cannot use --validation-only or --limit")
    if args.sensitivity_config and not args.frozen_selection:
        p.error("--sensitivity-config requires --frozen-selection")
    if (args.loss != "weighted_ce" or args.token_init) and args.frozen_selection:
        p.error("--loss và --token-init chưa dùng được với --frozen-selection")
    if args.focal_gamma < 0 or not 0 <= args.label_smoothing < 1 or not 0 < args.head_fraction < 1:
        p.error("focal gamma, label smoothing hoặc head fraction không hợp lệ")
    if args.edge_types and (args.frozen_selection or args.save_checkpoints):
        p.error("--edge-types chưa dùng được với --frozen-selection hoặc --save-checkpoints")
    if min(args.dim, args.num_layers, args.batch_size, args.max_epochs, args.patience) < 1:
        p.error("Dimension, layers, batch size, epochs and patience must be positive")
    if not 0 <= args.dropout < 1 or (args.max_nodes is not None and args.max_nodes < 1):
        p.error("Invalid dropout or node cap")
    return args


def load_token_init(paths: list[Path], protocol: str, n_tokens: int, dim: int) -> torch.Tensor:
    """Chọn tệp khởi tạo embedding token của ``protocol`` và kiểm tra khớp vocabulary.

    Mỗi protocol có vocabulary riêng nên cần một tệp riêng. Tệp tự khai báo protocol của nó,
    vì vậy một tệp dành cho protocol khác sẽ bị từ chối thay vì được dùng nhầm.
    """
    if isinstance(paths, (str, Path)):
        paths = [Path(paths)]
    payloads = [(path, torch.load(path, map_location="cpu", weights_only=True)) for path in paths]
    matching = [(path, p) for path, p in payloads if p["protocol"] == protocol]
    if len(matching) != 1:
        available = sorted(p["protocol"] for _, p in payloads)
        raise ValueError(f"Cần đúng một tệp token init cho protocol {protocol!r}, đang có {available}")
    path, payload = matching[0]
    matrix = payload["matrix"]
    if tuple(matrix.shape) != (n_tokens, dim):
        raise ValueError(f"Token init có dạng {tuple(matrix.shape)}, cần {(n_tokens, dim)}")
    print(f"Token init {protocol}: {payload['model_name']} -> {tuple(matrix.shape)}")
    return matrix


def main() -> int:
    a = parse_args()
    # Refuse accidental overwrite of previous experiments, including 4.0/4.1a outputs.
    if a.out_dir.exists() and any(a.out_dir.iterdir()):
        raise FileExistsError(f"Output directory must be empty: {a.out_dir}")
    frozen = read_frozen(a.frozen_selection, ROOT, a.processed_dir, a.schema, a.results_root) if a.frozen_selection else None
    sensitivity = a.sensitivity_config
    target = frozen["winner"] if frozen else None
    if sensitivity:
        target = sensitivity_target(frozen, sensitivity, ROOT, a.processed_dir, a.schema,
                                    a.results_root or a.frozen_selection.parent)
    if frozen:
        previous = target["metadata"]["arguments"]
        for key in (*BASELINE, "protocols", "graphs", "models", "seeds", "config_id", "dataset_id"):
            setattr(a, key, previous[key])
    a.out_dir.mkdir(parents=True, exist_ok=True)
    cwe_mapping = load_schema(a.schema)["cwe_mapping"]
    labels = [c for c, _ in sorted(cwe_mapping.items(), key=lambda kv: kv[1])]
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Thiết bị: {device}; torch {torch.__version__}")

    metadata = {"arguments": {k: _plain(v) for k, v in vars(a).items()},
                "code": code_identity(ROOT), "environment": environment(),
                "schema_sha256": digest(a.schema), "inputs": {}, "runs": []}
    if frozen:
        metadata["frozen_selection_sha256"] = digest(a.frozen_selection)
    if sensitivity:
        metadata["purpose"] = "test sensitivity analysis; not used for selection"
    write_json(a.out_dir / "metadata.json", metadata)
    rows, per_class, matrices, histories = [], [], {}, []
    for protocol in a.protocols:
        vocab = json.loads((a.processed_dir / protocol / "vocab.json").read_text(encoding="utf-8"))
        n_types, n_tokens = len(vocab["node_type"]), len(vocab["token"])
        token_init = load_token_init(a.token_init, protocol, n_tokens, a.dim) if a.token_init else None
        if token_init is not None:
            metadata.setdefault("token_init", {})[protocol] = {
                "paths": [str(p) for p in a.token_init],
                "sha256": {str(p): digest(p) for p in a.token_init}}
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
                        entry = next(r for r in target["metadata"]["runs"]
                                     if r["protocol"] == protocol and r["seed"] == seed)
                        payload = torch.load(checkpoint_path({"winner": target}, entry,
                                                             a.results_root or a.frozen_selection.parent),
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
                            return_state=a.save_checkpoints, loss=a.loss, token_init=token_init,
                            focal_gamma=a.focal_gamma, label_smoothing=a.label_smoothing,
                            head_fraction=a.head_fraction)
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
    title = f"# Kết quả {'/'.join(a.models).upper()} {'/'.join(a.graphs)} (cấu hình {a.config_id})"
    if sensitivity:
        title += ", độ nhạy trên test, không dùng để chọn cấu hình"
    lines = summary_lines(title, rows, ("protocol", "graph", "model", "split"))
    (a.out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    metadata["artifacts_sha256"] = {name: digest(a.out_dir / name) for name in ARTIFACTS}
    write_json(a.out_dir / "metadata.json", metadata)
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

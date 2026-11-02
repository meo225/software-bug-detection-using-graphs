"""Task 4.1a: chạy baseline không dùng graph và ghi kết quả.

Baseline: majority, stratified random, token-method và token-nodes (TF-IDF cộng
hồi quy logistic). Chạy trên hai protocol, mỗi protocol đánh giá validation và test.
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

from src.evaluation.metrics import classification_report  # noqa: E402
from src.models import text_baselines as tb  # noqa: E402

DEFAULT_MANIFEST = ROOT / "data" / "splits" / "diversevul_experiment_manifest.csv"
DEFAULT_SCHEMA = ROOT / "configs" / "graph" / "schema_spec.yaml"
SCALAR_METRICS = ("accuracy", "macro_precision", "macro_recall", "macro_f1", "weighted_f1", "mcc")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Baseline không dùng graph cho Task 4.1a")
    parser.add_argument("--graph-a-dir", type=Path, required=True, help="Thư mục graph_a của Task 3.3")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])
    parser.add_argument("--protocols", nargs="+", default=list(tb.PROTOCOL_COLUMNS))
    parser.add_argument("--max-features", type=int, default=200_000)
    return parser.parse_args()


def evaluate_all(args: argparse.Namespace) -> tuple[list[dict], list[dict], dict]:
    cwe_mapping = tb.load_cwe_mapping(args.schema)
    labels = [cwe for cwe, _ in sorted(cwe_mapping.items(), key=lambda kv: kv[1])]
    samples = tb.load_samples(args.graph_a_dir, args.manifest, cwe_mapping)
    print(f"Số mẫu hợp lệ đọc được: {len(samples)}")

    rows: list[dict] = []
    per_class: list[dict] = []
    matrices: dict[str, list[list[int]]] = {}

    for protocol in args.protocols:
        parts = tb.split_samples(samples, protocol)
        train_y = [s["y"] for s in parts["train"]]
        print(f"{protocol}: " + ", ".join(f"{k}={len(v)}" for k, v in parts.items()))
        eval_splits = [name for name in ("validation", "test") if parts[name]]
        if not eval_splits or not train_y:
            continue
        # Hồi quy logistic với lbfgs mang tính xác định, nên mỗi biến thể token chỉ fit một
        # lần cho mỗi protocol và dùng lại cho mọi seed. Chỉ random thay đổi theo seed.
        eval_all = [s for name in eval_splits for s in parts[name]]
        token_predictions: dict[str, dict[str, list[int]]] = {}
        for name, key in (("token_method", "text_method"), ("token_nodes", "text_nodes")):
            joined = tb.fit_predict_tfidf(
                [s[key] for s in parts["train"]], train_y,
                [s[key] for s in eval_all], args.seeds[0], args.max_features,
            )
            offset = 0
            token_predictions[name] = {}
            for split in eval_splits:
                n = len(parts[split])
                token_predictions[name][split] = list(joined[offset:offset + n])
                offset += n

        for split in eval_splits:
            eval_set = parts[split]
            y_true = [s["y"] for s in eval_set]
            for seed in args.seeds:
                predictions = {
                    "majority": tb.predict_majority(train_y, len(eval_set)),
                    "random": tb.predict_random(train_y, len(eval_set), seed),
                    "token_method": token_predictions["token_method"][split],
                    "token_nodes": token_predictions["token_nodes"][split],
                }
                for model, y_pred in predictions.items():
                    report = classification_report(y_true, list(y_pred), labels)
                    rows.append({"protocol": protocol, "split": split, "model": model,
                                 "seed": seed, "n_eval": len(eval_set),
                                 **{m: report[m] for m in SCALAR_METRICS}})
                    for i, cwe in enumerate(labels):
                        per_class.append({"protocol": protocol, "split": split, "model": model,
                                          "seed": seed, "cwe": cwe,
                                          "precision": report["per_class_precision"][i],
                                          "recall": report["per_class_recall"][i],
                                          "f1": report["per_class_f1"][i],
                                          "support": report["per_class_support"][i]})
                    if seed == args.seeds[0]:
                        matrices[f"{protocol}|{split}|{model}"] = report["confusion_matrix"]
    return rows, per_class, matrices


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_summary(path: Path, rows: list[dict]) -> None:
    groups: dict[tuple[str, str, str], list[dict]] = {}
    for row in rows:
        groups.setdefault((row["protocol"], row["split"], row["model"]), []).append(row)
    lines = ["# Kết quả baseline không dùng graph (Task 4.1a)", "",
             "Giá trị là trung bình ± độ lệch chuẩn theo seed.", "",
             "| Protocol | Split | Model | Macro-F1 | Weighted-F1 | MCC | Accuracy |",
             "| :--- | :--- | :--- | ---: | ---: | ---: | ---: |"]
    for (protocol, split, model), items in sorted(groups.items()):
        def cell(metric: str) -> str:
            values = [i[metric] for i in items]
            return f"{mean(values):.4f} ± {pstdev(values):.4f}"
        lines.append(f"| {protocol} | {split} | {model} | {cell('macro_f1')} | "
                     f"{cell('weighted_f1')} | {cell('mcc')} | {cell('accuracy')} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    if not args.graph_a_dir.is_dir():
        print(f"Lỗi không tìm thấy thư mục graph_a: {args.graph_a_dir}", file=sys.stderr)
        return 1
    args.out_dir.mkdir(parents=True, exist_ok=True)
    rows, per_class, matrices = evaluate_all(args)
    write_csv(args.out_dir / "results.csv", rows)
    write_csv(args.out_dir / "per_class.csv", per_class)
    (args.out_dir / "confusion_matrices.json").write_text(json.dumps(matrices), encoding="utf-8")
    write_summary(args.out_dir / "summary.md", rows)
    print(f"Đã ghi kết quả vào {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

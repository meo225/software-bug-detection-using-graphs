"""Task 4.5: fine-tune mô hình text pretrained trên cùng split với các model graph.

Đầu vào là tệp ``.jsonl.gz`` do ``scripts/build_text_dataset.py`` sinh ra, không
phải Kaggle Dataset graph của Task 4.0, vì dữ liệu đó không chứa mã nguồn gốc.

Tệp kết quả giống hệt Task 4.1a để gộp và so sánh được.

Ví dụ:
    python scripts/train_text.py --dataset /kaggle/input/<dataset>/diversevul_text.jsonl.gz \
        --out-dir /kaggle/working/text_results --model codebert
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

from src.data.text_dataset import (  # noqa: E402
    check_split_sizes, labels_from_mapping, load_cwe_mapping, load_text_dataset,
    split_sizes, split_text_samples,
)
from src.models.text_encoder import build_encoder, build_tokenizer, length_statistics, tokenize_samples  # noqa: E402
from src.training.gcn_tuning import ARTIFACTS, code_identity, digest, environment, write_json  # noqa: E402
from src.training.run_artifacts import plain, summary_lines, write_csv  # noqa: E402
from src.training.text_experiments import BASELINE, MODELS, PRIMARY_MODEL, PROTOCOLS, SEEDS  # noqa: E402
from src.training.text_trainer import run_text_training  # noqa: E402

SCALARS = ("accuracy", "macro_precision", "macro_recall", "macro_f1", "weighted_f1", "mcc")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dataset", type=Path, required=True, help="Tệp .jsonl.gz văn bản hàm.")
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--schema", type=Path, default=ROOT / "configs" / "graph" / "schema_spec.yaml")
    p.add_argument("--model", choices=sorted(MODELS), default=PRIMARY_MODEL)
    p.add_argument("--protocols", nargs="+", default=list(PROTOCOLS), choices=list(PROTOCOLS))
    p.add_argument("--seeds", nargs="+", type=int, default=list(SEEDS))
    p.add_argument("--dataset-id", default="", help="Định danh dataset để ghi vào metadata.")
    for name, value in BASELINE.items():
        p.add_argument("--" + name.replace("_", "-"), type=type(value), default=value)
    p.add_argument("--limit", type=int, default=0, help="Chỉ dùng N mẫu đầu mỗi split, để thử nhanh.")
    p.add_argument("--no-amp", action="store_true", help="Tắt mixed precision.")
    p.add_argument("--local-files-only", action="store_true",
                   help="Chỉ dùng trọng số đã tải sẵn, không gọi mạng.")
    p.add_argument("--validation-only", action="store_true",
                   help="Không chấm test. Dùng khi cần dò cấu hình mà không nhìn test.")
    return p.parse_args()


def main() -> int:
    a = parse_args()
    if a.out_dir.exists() and any(a.out_dir.iterdir()):
        raise FileExistsError(f"Thư mục kết quả phải rỗng: {a.out_dir}")
    a.out_dir.mkdir(parents=True, exist_ok=True)

    cwe_mapping = load_cwe_mapping(a.schema)
    labels = labels_from_mapping(cwe_mapping)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Thiết bị: {device}; torch {torch.__version__}")

    samples = load_text_dataset(a.dataset, n_classes=len(labels))
    problems = check_split_sizes(samples)
    if problems and not a.limit:
        print("CẢNH BÁO tập văn bản lệch khỏi dữ liệu đã xử lý của Task 4.0:")
        for line in problems:
            print("  " + line)

    model_name = MODELS[a.model]
    tokenizer = build_tokenizer(model_name, a.local_files_only)
    encoded = tokenize_samples(samples, tokenizer, a.max_length, a.max_chunks)
    stats = length_statistics(encoded, a.max_length, a.max_chunks)
    print(f"Độ dài hàm theo token: trung vị {stats['median_tokens']}, p90 {stats['p90_tokens']}, "
          f"tối đa {stats['max_tokens']}")
    print(f"Hàm cần nhiều hơn một đoạn: {stats['share_over_one_chunk']:.1%}; "
          f"bị cắt bỏ một phần: {stats['share_truncated']:.1%}; "
          f"giữ được {stats['token_coverage']:.1%} số token")

    metadata = {"arguments": {k: plain(v) for k, v in vars(a).items()},
                "code": code_identity(ROOT), "environment": environment(),
                "schema_sha256": digest(a.schema),
                "inputs": {"dataset": str(a.dataset), "dataset_sha256": digest(a.dataset),
                           "dataset_id": a.dataset_id, "model_name": model_name,
                           "n_samples": len(samples), "split_sizes": split_sizes(samples),
                           "split_size_problems": problems, "length_statistics": stats},
                "runs": []}
    write_json(a.out_dir / "metadata.json", metadata)

    rows, per_class, matrices, histories = [], [], {}, []
    for protocol in a.protocols:
        parts = split_text_samples(encoded, protocol)
        if a.limit:
            parts = {name: part[: a.limit] for name, part in parts.items()}
        print(f"{protocol}: " + ", ".join(f"{k}={len(v)}" for k, v in parts.items()))
        for seed in a.seeds:
            out = run_text_training(
                parts["train"], parts["validation"], parts["test"],
                lambda: build_encoder(model_name, a.local_files_only),
                labels, seed, tokenizer.pad_token_id,
                dropout=a.dropout, pooling=a.pooling, lr=a.lr, weight_decay=a.weight_decay,
                batch_size=a.batch_size, max_epochs=a.max_epochs, patience=a.patience,
                warmup_ratio=a.warmup_ratio, grad_clip=a.grad_clip, amp=not a.no_amp,
                device=device, evaluate_test=not a.validation_only, tag=a.model)
            tag = f"{protocol}|{a.model}|{seed}"
            for split, rep in out["reports"].items():
                rows.append({"protocol": protocol, "model": a.model, "seed": seed, "split": split,
                             "n_eval": sum(rep["per_class_support"]),
                             "best_epoch": out["best_epoch"], "epochs_run": out["epochs_run"],
                             "n_params": out["n_params"],
                             "train_seconds": round(out["train_seconds"], 1),
                             "peak_gpu_mb": out["peak_gpu_mb"],
                             "max_length": a.max_length, "max_chunks": a.max_chunks,
                             "pooling": a.pooling,
                             **{m: rep[m] for m in SCALARS}})
                for i, cwe in enumerate(labels):
                    per_class.append({"protocol": protocol, "model": a.model, "seed": seed,
                                      "split": split, "cwe": cwe,
                                      "precision": rep["per_class_precision"][i],
                                      "recall": rep["per_class_recall"][i],
                                      "f1": rep["per_class_f1"][i],
                                      "support": rep["per_class_support"][i]})
                if seed == a.seeds[0]:
                    matrices[f"{tag}|{split}"] = rep["confusion_matrix"]
            histories.append({"tag": tag, "history": out["history"]})
            metadata["runs"].append({"protocol": protocol, "seed": seed,
                                     "best_epoch": out["best_epoch"],
                                     "epochs_run": out["epochs_run"]})
            write_csv(a.out_dir / "results.csv", rows)  # ghi dần để không mất khi phiên chết
            write_csv(a.out_dir / "per_class.csv", per_class)
            write_json(a.out_dir / "metadata.json", metadata)

    (a.out_dir / "confusion_matrices.json").write_text(json.dumps(matrices), encoding="utf-8")
    (a.out_dir / "training_history.json").write_text(json.dumps(histories), encoding="utf-8")
    lines = summary_lines(f"# Kết quả {a.model} trên văn bản hàm (Task 4.5)", rows,
                          ("protocol", "model", "split"))
    (a.out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    metadata["artifacts_sha256"] = {name: digest(a.out_dir / name) for name in ARTIFACTS}
    write_json(a.out_dir / "metadata.json", metadata)
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

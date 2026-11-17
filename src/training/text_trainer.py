"""Vòng huấn luyện mô hình text cho Task 4.5.

Giữ đúng giao diện kết quả của ``src/training/gnn_trainer.run_training`` để
``scripts/train_text.py`` dùng lại được phần ghi kết quả của Task 4.1a, nhờ đó
bảng của Task 4.5 đặt cạnh bảng của Task 4.1 đến 4.3 mà không cần chuyển đổi.

Khác biệt so với vòng huấn luyện GNN, và lý do:

- Learning rate 2e-5 cùng tối đa 10 epoch, theo PrimeVul (bài 3 trong tab Tài liệu
  tham khảo). Bài báo EMNLP 2024 không công bố learning rate hay batch size.
- Không áp weight decay lên bias và LayerNorm, theo cách fine-tune transformer
  thông thường.
- Gradient clipping 1,0 thay vì 5,0 của GNN, cũng theo thông lệ fine-tune.
- Có warmup tuyến tính rồi giảm tuyến tính.
- Trọng số tốt nhất được giữ trên CPU vì encoder 125M tham số chiếm VRAM đáng kể.
"""

from __future__ import annotations

import random
import time
from typing import Any, Callable, Sequence

import torch
from torch import nn

from src.evaluation.metrics import classification_report
from src.models.text_encoder import ChunkedTextClassifier, collate_text
from src.training.gnn_trainer import seed_everything
from src.training.losses import balanced_class_weights, build_loss

__all__ = ["run_text_training", "predict", "count_parameters", "linear_schedule"]


def count_parameters(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def linear_schedule(step: int, total_steps: int, warmup_ratio: float) -> float:
    """Hệ số learning rate: tăng tuyến tính rồi giảm tuyến tính về 0."""
    total_steps = max(total_steps, 1)
    warmup = max(int(round(total_steps * warmup_ratio)), 0)
    if step < warmup:
        return (step + 1) / max(warmup, 1)
    remaining = total_steps - warmup
    if remaining <= 0:
        return 1.0
    return max(0.0, (total_steps - step) / remaining)


def parameter_groups(model: nn.Module, weight_decay: float) -> list[dict[str, Any]]:
    """Bỏ weight decay cho bias và các lớp normalization, theo thông lệ fine-tune transformer.

    Lớp normalization được nhận ra theo kiểu module chứ không theo tên tham số, vì tên
    phụ thuộc cách đặt tên của từng kiến trúc.
    """
    exempt_ids = {id(parameter)
                  for module in model.modules()
                  if "norm" in type(module).__name__.lower()
                  for parameter in module.parameters(recurse=False)}
    decayed, plain = [], []
    for name, parameter in model.named_parameters():
        if not parameter.requires_grad:
            continue
        exempt = id(parameter) in exempt_ids or name.split(".")[-1] == "bias"
        (plain if exempt else decayed).append(parameter)
    return [{"params": decayed, "weight_decay": weight_decay},
            {"params": plain, "weight_decay": 0.0}]


def iterate(items: Sequence[dict[str, Any]], batch_size: int, shuffle: bool,
            rng: random.Random, pad_id: int, device: torch.device):
    order = list(range(len(items)))
    if shuffle:
        rng.shuffle(order)
    for start in range(0, len(order), batch_size):
        batch = collate_text([items[i] for i in order[start:start + batch_size]], pad_id)
        yield {k: v.to(device) for k, v in batch.items()}


@torch.no_grad()
def predict(model: nn.Module, items: Sequence[dict[str, Any]], batch_size: int,
            pad_id: int, device: torch.device, amp: bool = False) -> tuple[list[int], list[int]]:
    model.eval()
    y_true, y_pred = [], []
    for batch in iterate(items, batch_size, False, random.Random(0), pad_id, device):
        with torch.autocast(device.type, dtype=torch.float16, enabled=amp and device.type == "cuda"):
            logits = model(batch)
        y_pred.extend(logits.float().argmax(-1).tolist())
        y_true.extend(batch["y"].tolist())
    return y_true, y_pred


def run_text_training(
    train: Sequence[dict[str, Any]],
    val: Sequence[dict[str, Any]],
    test: Sequence[dict[str, Any]],
    encoder_factory: Callable[[], nn.Module],
    labels: list[str],
    seed: int,
    pad_id: int,
    *,
    dropout: float = 0.1,
    pooling: str = "max",
    lr: float = 2e-5,
    weight_decay: float = 0.01,
    batch_size: int = 8,
    max_epochs: int = 10,
    patience: int = 3,
    warmup_ratio: float = 0.1,
    grad_clip: float = 1.0,
    amp: bool = True,
    device: torch.device | None = None,
    evaluate_test: bool = True,
    log: Callable[[str], None] = print,
    tag: str = "text",
) -> dict[str, Any]:
    """Fine-tune encoder pretrained với class-weighted CE, dừng sớm theo Macro-F1."""
    device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
    seed_everything(seed)
    rng = random.Random(seed)
    n_classes = len(labels)
    use_amp = amp and device.type == "cuda"

    model = ChunkedTextClassifier(encoder_factory(), n_classes, dropout, pooling).to(device)
    train_y = [int(item["y"]) for item in train]
    loss_fn, _ = build_loss("weighted_ce", train_y, n_classes, max_epochs)
    loss_fn = loss_fn.to(device)
    optim = torch.optim.AdamW(parameter_groups(model, weight_decay), lr=lr)
    steps_per_epoch = max(1, (len(train) + batch_size - 1) // batch_size)
    total_steps = steps_per_epoch * max_epochs
    scheduler = torch.optim.lr_scheduler.LambdaLR(
        optim, lambda step: linear_schedule(step, total_steps, warmup_ratio))
    scaler = torch.amp.GradScaler(device.type, enabled=use_amp)

    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats()
    start = time.time()
    best_f1, best_state, best_epoch, history, bad = -1.0, None, 0, [], 0
    for epoch in range(1, max_epochs + 1):
        model.train()
        total, seen = 0.0, 0
        for batch in iterate(train, batch_size, True, rng, pad_id, device):
            optim.zero_grad(set_to_none=True)
            with torch.autocast(device.type, dtype=torch.float16, enabled=use_amp):
                batch_loss = loss_fn(model(batch), batch["y"])
            scaler.scale(batch_loss).backward()
            scaler.unscale_(optim)
            nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
            scaler.step(optim)
            scaler.update()
            scheduler.step()
            total += float(batch_loss.detach()) * batch["y"].shape[0]
            seen += batch["y"].shape[0]
        yt, yp = predict(model, val, batch_size, pad_id, device, use_amp)
        f1 = classification_report(yt, yp, labels)["macro_f1"]
        history.append({"epoch": epoch, "train_loss": total / max(seen, 1), "val_macro_f1": f1,
                        "lr": scheduler.get_last_lr()[0]})
        log(f"  [{tag} seed={seed}] epoch {epoch:02d} loss={total / max(seen, 1):.4f} val_macro_f1={f1:.4f}")
        if f1 > best_f1:
            best_f1, best_epoch, bad = f1, epoch, 0
            best_state = {k: v.detach().to("cpu", copy=True) for k, v in model.state_dict().items()}
        else:
            bad += 1
            if bad >= patience:
                break
    train_seconds = time.time() - start

    if best_state is not None:
        model.load_state_dict(best_state)
    reports = {}
    parts = [("validation", val)] + ([("test", test)] if evaluate_test else [])
    for name, part in parts:
        yt, yp = predict(model, part, batch_size, pad_id, device, use_amp)
        reports[name] = classification_report(yt, yp, labels)
    peak_mb = torch.cuda.max_memory_allocated() / 2**20 if device.type == "cuda" else None
    return {"reports": reports, "best_epoch": best_epoch, "epochs_run": len(history),
            "loss": "weighted_ce", "history": history, "n_params": count_parameters(model),
            "train_seconds": train_seconds, "peak_gpu_mb": peak_mb}

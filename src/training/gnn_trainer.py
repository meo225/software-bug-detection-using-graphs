"""Vòng huấn luyện GNN cho Task 4.1a (class-weighted CE, dừng sớm theo Macro-F1 validation)."""

from __future__ import annotations

import copy
import random
import time
from typing import Any

import numpy as np
import torch
from torch import nn

from src.evaluation.metrics import classification_report
from src.models.gnn import GNNClassifier, collate, count_parameters, filter_edge_types, truncate_graph
from src.training.losses import balanced_class_weights, build_loss

__all__ = ["balanced_class_weights", "build_loss", "run_training", "evaluate_saved",
           "seed_everything", "predict", "validation_loss"]


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def iterate(items: list[dict[str, Any]], batch_size: int, shuffle: bool,
            rng: random.Random, add_reverse: bool, device: torch.device):
    order = list(range(len(items)))
    if shuffle:
        rng.shuffle(order)
    for start in range(0, len(order), batch_size):
        chunk = [items[i] for i in order[start:start + batch_size]]
        batch = collate(chunk, add_reverse)
        yield {k: v.to(device) for k, v in batch.items()}


@torch.no_grad()
def predict(model: nn.Module, items: list[dict[str, Any]], batch_size: int,
            add_reverse: bool, device: torch.device) -> tuple[list[int], list[int]]:
    model.eval()
    y_true, y_pred = [], []
    for batch in iterate(items, batch_size, False, random.Random(0), add_reverse, device):
        y_pred.extend(model(batch).argmax(-1).tolist())
        y_true.extend(batch["y"].tolist())
    return y_true, y_pred


@torch.no_grad()
def validation_loss(model: nn.Module, items: list[dict[str, Any]], batch_size: int,
                    add_reverse: bool, device: torch.device, weights: torch.Tensor) -> float:
    """Weighted CE over the whole validation set, independent of batch boundaries.

    Class weights come exclusively from training labels, including zero weights
    for classes absent from train, matching the training objective.
    """
    model.eval()
    numerator, denominator = 0.0, 0.0
    for batch in iterate(items, batch_size, False, random.Random(0), add_reverse, device):
        logits = model(batch)
        numerator += float(nn.functional.cross_entropy(logits, batch["y"], weight=weights, reduction="sum"))
        denominator += float(weights[batch["y"]].sum())
    if denominator <= 0:
        raise ValueError("Validation loss has no positive training-class weights")
    return numerator / denominator


def run_training(
    train: list[dict[str, Any]], val: list[dict[str, Any]], test: list[dict[str, Any]],
    kind: str, n_types: int, n_tokens: int, labels: list[str], seed: int,
    dim: int = 128, num_layers: int = 3, dropout: float = 0.2, lr: float = 1e-3,
    weight_decay: float = 1e-4, batch_size: int = 32, max_epochs: int = 40,
    patience: int = 8, add_reverse: bool = True, max_nodes: int | None = None,
    device: torch.device | None = None, log=print,
    *, early_stopping: str = "macro_f1", evaluate_test: bool = True,
    return_state: bool = False, edge_types: tuple[int, ...] | None = None,
    loss: str = "weighted_ce", token_init: torch.Tensor | None = None,
    focal_gamma: float = 2.0, label_smoothing: float = 0.1, head_fraction: float = 0.5,
) -> dict[str, Any]:
    """Huấn luyện một cấu hình với một seed. Chọn epoch tốt nhất theo Macro-F1 trên validation."""
    if early_stopping not in {"macro_f1", "val_loss"}:
        raise ValueError("early_stopping must be macro_f1 or val_loss")
    if loss != "weighted_ce" and early_stopping == "val_loss":
        # Validation loss luôn tính bằng cross-entropy có trọng số, nên sẽ không khớp mục tiêu train.
        raise ValueError("Dừng sớm theo validation loss chỉ dùng được với loss weighted_ce")
    if not train or not val or (evaluate_test and not test):
        raise ValueError("Required splits must be nonempty")
    if max_epochs < 1 or patience < 1 or batch_size < 1 or num_layers < 1:
        raise ValueError("Epochs, patience, batch size and layers must be positive")
    device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if max_nodes:
        train = [truncate_graph(g, max_nodes) for g in train]
        val = [truncate_graph(g, max_nodes) for g in val]
        if evaluate_test:
            test = [truncate_graph(g, max_nodes) for g in test]
    if edge_types:
        # Ablation loại cạnh: áp dụng giống nhau cho mọi split; None giữ nguyên mọi cạnh.
        train = [filter_edge_types(g, edge_types) for g in train]
        val = [filter_edge_types(g, edge_types) for g in val]
        if evaluate_test:
            test = [filter_edge_types(g, edge_types) for g in test]
    seed_everything(seed)
    rng = random.Random(seed)
    n_classes = len(labels)

    model = GNNClassifier(kind, n_types, n_tokens, n_classes, dim, num_layers, dropout,
                          token_init=token_init).to(device)
    train_y = [int(g["y"]) for g in train]
    loss_fn, weights = build_loss(loss, train_y, n_classes, max_epochs,
                                  focal_gamma, label_smoothing, head_fraction)
    loss_fn, weights = loss_fn.to(device), weights.to(device)
    optim = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)

    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats()
    start = time.time()
    best_f1, best_state, best_epoch, history, bad = -1.0, None, 0, [], 0
    best_signal = float("inf") if early_stopping == "val_loss" else -1.0
    for epoch in range(1, max_epochs + 1):
        set_epoch = getattr(loss_fn, "set_epoch", None)
        if set_epoch is not None:
            set_epoch(epoch)
        model.train()
        total, seen = 0.0, 0
        for batch in iterate(train, batch_size, True, rng, add_reverse, device):
            optim.zero_grad()
            batch_loss = loss_fn(model(batch), batch["y"])
            batch_loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optim.step()
            total += float(batch_loss.detach()) * batch["y"].shape[0]
            seen += batch["y"].shape[0]
        yt, yp = predict(model, val, batch_size, add_reverse, device)
        f1 = classification_report(yt, yp, labels)["macro_f1"]
        signal = f1
        entry = {"epoch": epoch, "train_loss": total / max(seen, 1), "val_macro_f1": f1}
        if early_stopping == "val_loss":
            signal = validation_loss(model, val, batch_size, add_reverse, device, weights)
            entry["val_loss"] = signal
        history.append(entry)
        if early_stopping == "val_loss":
            log(f"  validation loss={signal:.6f}")
        log(f"  [{kind} seed={seed}] epoch {epoch:02d} loss={total / max(seen, 1):.4f} val_macro_f1={f1:.4f}")
        if f1 > best_f1:
            best_f1, best_epoch = f1, epoch
            best_state = copy.deepcopy(model.state_dict())
        improved = signal < best_signal if early_stopping == "val_loss" else signal > best_signal
        if improved:
            best_signal, bad = signal, 0
        else:
            bad += 1
            if bad >= patience:
                break
    train_seconds = time.time() - start

    model.load_state_dict(best_state)
    reports = {}
    evaluation_parts = [("validation", val)] + ([("test", test)] if evaluate_test else [])
    for name, part in evaluation_parts:
        yt, yp = predict(model, part, batch_size, add_reverse, device)
        reports[name] = classification_report(yt, yp, labels)
    peak_mb = torch.cuda.max_memory_allocated() / 2**20 if device.type == "cuda" else None
    result = {"reports": reports, "best_epoch": best_epoch, "epochs_run": len(history),
            "loss": loss,
            "history": history, "n_params": count_parameters(model),
            "train_seconds": train_seconds, "peak_gpu_mb": peak_mb}

    if return_state:
        result["state_dict"] = {k: v.detach().cpu().clone() for k, v in best_state.items()}
    return result


@torch.no_grad()
def evaluate_saved(payload: dict, test: list[dict[str, Any]], device: torch.device) -> dict:
    """Evaluate saved validation-selected weights without fitting or selecting epochs."""
    cfg = payload["configuration"]
    if cfg["max_nodes"]:
        test = [truncate_graph(g, cfg["max_nodes"]) for g in test]
    model = GNNClassifier(**payload["constructor"]).to(device)
    model.load_state_dict(payload["state_dict"])
    yt, yp = predict(model, test, cfg["batch_size"], True, device)
    return {**payload["training"], "reports": {"test": classification_report(yt, yp, payload["labels"])}}

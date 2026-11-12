"""Hàm mất mát cho Task 4.3.

``weighted_ce`` là hàm mất mát mặc định của Task 4.1a đến 4.2: cross-entropy có trọng số lớp.
``AdaptiveReweightedLoss`` lấy ý tưởng từ LIVABLE (arXiv 2306.06935): label smoothing cho nhóm
lớp đầu, focal cho nhóm lớp đuôi, và mức độ nhấn vào nhóm đuôi tăng dần theo epoch. Đây là bản
diễn giải theo mô tả trong bài báo, không phải bản cài đặt lại chính thức của nhóm tác giả.
"""

from __future__ import annotations

from collections import Counter

import torch
from torch import Tensor, nn


def balanced_class_weights(train_y: list[int], n_classes: int) -> Tensor:
    """w_c = n / (C_present * n_c) cho lớp có mặt trong train, 0 cho lớp vắng mặt."""
    counts = Counter(train_y)
    present = len(counts)
    total = len(train_y)
    weights = torch.zeros(n_classes)
    for label, count in counts.items():
        weights[label] = total / (present * count)
    return weights


def head_class_mask(train_y: list[int], n_classes: int, head_fraction: float = 0.5) -> Tensor:
    """Đánh dấu nhóm lớp đầu: các lớp nhiều mẫu nhất cộng dồn đủ ``head_fraction`` tập train.

    Lớp vắng mặt trong train luôn thuộc nhóm đuôi. Ranh giới được tính một lần từ train, không
    phụ thuộc batch, nên không rò rỉ thông tin của validation hay test.
    """
    if not 0 < head_fraction < 1:
        raise ValueError("head_fraction phải nằm trong khoảng (0, 1)")
    counts = Counter(train_y)
    total = len(train_y)
    mask = torch.zeros(n_classes, dtype=torch.bool)
    cumulative = 0
    for label, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        if cumulative >= head_fraction * total:
            break
        mask[label] = True
        cumulative += count
    return mask


class AdaptiveReweightedLoss(nn.Module):
    """Label smoothing cho lớp đầu, focal cho lớp đuôi, cường độ tăng dần theo epoch.

    Với mẫu thuộc nhóm đầu, hàm dùng cross-entropy có label smoothing ``smoothing``.
    Với mẫu thuộc nhóm đuôi, hàm dùng focal cross-entropy với số mũ ``gamma * beta``.
    ``beta`` đi từ 0 ở epoch đầu tới 1 ở epoch ``max_epochs``, nên epoch đầu tương đương
    cross-entropy có trọng số lớp, còn các epoch sau nhấn dần vào mẫu đuôi khó.
    Trọng số lớp giữ nguyên công thức của Task 4.1a để chỉ thay đổi đúng một yếu tố.
    """

    def __init__(self, class_weights: Tensor, head_mask: Tensor, gamma: float = 2.0,
                 smoothing: float = 0.1, max_epochs: int = 40) -> None:
        super().__init__()
        if class_weights.shape != head_mask.shape:
            raise ValueError("class_weights và head_mask phải cùng số lớp")
        if gamma < 0 or not 0 <= smoothing < 1 or max_epochs < 1:
            raise ValueError("gamma, smoothing hoặc max_epochs không hợp lệ")
        self.register_buffer("class_weights", class_weights)
        self.register_buffer("head_mask", head_mask)
        self.gamma = gamma
        self.smoothing = smoothing
        self.max_epochs = max_epochs
        self.beta = 0.0

    def set_epoch(self, epoch: int) -> None:
        """Cập nhật cường độ ``beta`` theo epoch hiện tại, đếm từ 1."""
        if epoch < 1:
            raise ValueError("epoch đếm từ 1")
        self.beta = min(1.0, (epoch - 1) / max(self.max_epochs - 1, 1))

    def forward(self, logits: Tensor, target: Tensor) -> Tensor:
        log_probs = torch.log_softmax(logits, dim=-1)
        picked = log_probs.gather(1, target.unsqueeze(1)).squeeze(1)
        is_head = self.head_mask[target]

        smoothed = (1 - self.smoothing) * picked + self.smoothing * log_probs.mean(dim=-1)
        focal = (1 - picked.exp()).clamp(min=0.0).pow(self.gamma * self.beta) * picked
        per_sample = -torch.where(is_head, smoothed, focal)

        weights = self.class_weights[target]
        denominator = weights.sum()
        if denominator <= 0:
            raise ValueError("Batch không có mẫu nào thuộc lớp có trong train")
        return (per_sample * weights).sum() / denominator


def build_loss(name: str, train_y: list[int], n_classes: int, max_epochs: int,
               gamma: float = 2.0, smoothing: float = 0.1,
               head_fraction: float = 0.5) -> tuple[nn.Module, Tensor]:
    """Trả về hàm mất mát và vector trọng số lớp dùng chung cho validation loss."""
    weights = balanced_class_weights(train_y, n_classes)
    if name == "weighted_ce":
        return nn.CrossEntropyLoss(weight=weights), weights
    if name == "adaptive":
        head = head_class_mask(train_y, n_classes, head_fraction)
        return AdaptiveReweightedLoss(weights, head, gamma, smoothing, max_epochs), weights
    raise ValueError(f"Hàm mất mát không hợp lệ: {name!r}")

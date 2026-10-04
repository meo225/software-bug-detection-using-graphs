"""Seed xác định cho các thí nghiệm sau này.

Python, NumPy và PyTorch được đặt seed khi các thư viện này đã cài đặt.
Split của dataset vẫn phải được lưu. Chỉ seed không đủ để ghi nhận các sample ID
đã được sử dụng.
"""

from __future__ import annotations

import os
import random


def set_seed(seed: int) -> None:
    """Đặt seed cho thư viện chuẩn và các thư viện số tùy chọn."""
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)

    try:
        import numpy as np
    except ImportError:
        np = None
    if np is not None:
        np.random.seed(seed)

    try:
        import torch
    except ImportError:
        torch = None
    if torch is not None:
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)

"""Deterministic seeds for later experiments.

Python, NumPy, and PyTorch are seeded when those libraries are installed.
The dataset split itself must still be saved. A seed alone is not a record
of which sample IDs were used.
"""

from __future__ import annotations

import os
import random


def set_seed(seed: int) -> None:
    """Seed the standard library and any optional numeric libraries."""
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

"""Kiểm thử helper đặt seed."""

import random

from src.utils.seed import set_seed


def test_set_seed_repeats_python_rng() -> None:
    set_seed(7)
    first = [random.random() for _ in range(3)]
    set_seed(7)
    second = [random.random() for _ in range(3)]
    assert first == second

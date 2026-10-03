"""Tính toàn vẹn của cách chia dữ liệu.

Việc tạo ba chiến lược vẫn là TODO. Kiểm tra project trùng đã được triển khai
để cách chia theo project sau này không thể che giấu một project dùng chung.
"""

import pytest

from src.data.split import SPLIT_STRATEGIES, assert_project_disjoint, create_split


def test_project_wise_split_rejects_a_shared_project() -> None:
    with pytest.raises(ValueError, match="train_test"):
        assert_project_disjoint(
            train_groups={"openssl", "linux"},
            validation_groups={"qemu"},
            test_groups={"linux"},
        )


def test_project_wise_split_accepts_disjoint_projects() -> None:
    assert_project_disjoint(
        train_groups={"openssl"},
        validation_groups={"qemu"},
        test_groups={"linux"},
    ) is None


def test_create_split_is_not_implemented_for_any_strategy() -> None:
    assert SPLIT_STRATEGIES == ("random", "project", "chronological")
    for strategy in SPLIT_STRATEGIES:
        with pytest.raises(NotImplementedError):
            create_split(["sample-1"], strategy=strategy, seed=0, group_ids=["project-a"])

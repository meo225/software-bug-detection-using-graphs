"""Chia dữ liệu theo ID có thể tái lập.

Mỗi cách chia gồm ba danh sách sample ID được ghi trong ``data/splits/``.
Không sao chép source code thành các dataset train, validation và test riêng.
``train.py`` phải load các file này thay vì tạo một cách chia ngẫu nhiên mới.
"""

from __future__ import annotations

from pathlib import Path

SPLIT_STRATEGIES: tuple[str, ...] = ("random", "project", "chronological")


def create_split(
    sample_ids: list[str],
    strategy: str,
    seed: int,
    group_ids: list[str] | None = None,
    timestamps: list[str] | None = None,
) -> dict[str, list[str]]:
    """Trả về các danh sách ID ``train``, ``validation`` và ``test``.

    Chiến lược ``project`` cần ``group_ids`` và phải giữ mỗi project ở đúng một
    phía của phép chia train/test. ``chronological`` cần timestamp hợp lệ.
    TODO: triển khai ba chiến lược. Không chọn chiến lược mặc định tại đây.
    """
    if strategy not in SPLIT_STRATEGIES:
        raise ValueError(f"Chiến lược chia dữ liệu không xác định: {strategy}")
    raise NotImplementedError(
        f"Chưa triển khai create_split({strategy!r}, seed={seed}). "
        f"Đã nhận {len(sample_ids)} ID, "
        f"group={'có' if group_ids is not None else 'không'}, "
        f"timestamp={'có' if timestamps is not None else 'không'}."
    )


def assert_project_disjoint(
    train_groups: set[str],
    validation_groups: set[str],
    test_groups: set[str],
) -> None:
    """Báo lỗi khi cùng một project xuất hiện trong nhiều tập dữ liệu.

    Cách chia theo project phải ngăn một project đồng thời có mặt trong train và test.
    Quy tắc tương tự cũng áp dụng cho tập validation.
    """
    overlaps = {
        "train_validation": sorted(train_groups & validation_groups),
        "train_test": sorted(train_groups & test_groups),
        "validation_test": sorted(validation_groups & test_groups),
    }
    found = {name: groups for name, groups in overlaps.items() if groups}
    if found:
        raise ValueError(f"Project ID bị trùng giữa các tập dữ liệu: {found}")


def save_split_ids(split: dict[str, list[str]], output_dir: Path) -> None:
    """Ghi một danh sách ID cho mỗi tập. TODO: chọn định dạng văn bản ổn định."""
    raise NotImplementedError(f"Chưa triển khai save_split_ids cho {output_dir}.")


def load_split_ids(output_dir: Path) -> dict[str, list[str]]:
    """Đọc các danh sách ID do :func:`save_split_ids` tạo ra."""
    raise NotImplementedError(f"Chưa triển khai load_split_ids cho {output_dir}.")

"""Callback training. Checkpoint được ghi vào ``outputs/checkpoints/`` và bị Git bỏ qua."""

from __future__ import annotations

from pathlib import Path


class CheckpointCallback:
    """Lưu trạng thái trainer trong ``output_dir``. Phần triển khai đang để ngỏ."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir

    def on_epoch_end(self, epoch: int, state: object) -> None:
        """TODO: ghi checkpoint nhưng không commit file đó."""
        raise NotImplementedError(
            f"Chưa triển khai CheckpointCallback (epoch={epoch}, thư mục={self.output_dir})."
        )

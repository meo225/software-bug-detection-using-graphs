"""Training callbacks. Checkpoints go to ``outputs/checkpoints/`` and are gitignored."""

from __future__ import annotations

from pathlib import Path


class CheckpointCallback:
    """Save trainer state under ``output_dir``. The implementation is pending."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir

    def on_epoch_end(self, epoch: int, state: object) -> None:
        """TODO: write a checkpoint without committing it."""
        raise NotImplementedError(
            f"CheckpointCallback is not implemented (epoch={epoch}, dir={self.output_dir})."
        )

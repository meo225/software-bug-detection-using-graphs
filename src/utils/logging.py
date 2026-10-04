"""Helper logging cho script. Ưu tiên dùng thay cho các lệnh print rời rạc."""

from __future__ import annotations

import logging
from pathlib import Path


def get_logger(name: str, log_file: Path | None = None) -> logging.Logger:
    """Trả về logger ghi vào stderr và tùy chọn ghi thêm vào ``log_file``.

    Các lần gọi cùng tên sẽ dùng lại handler hiện có.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    logger.propagate = False
    return logger

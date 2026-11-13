"""Mô hình text cho Task 4.5: encoder pretrained cộng cắt đoạn cộng max-pooling.

CodeBERT và UniXcoder nhận tối đa 512 token, trong khi nhiều hàm C dài hơn. Theo
EMNLP 2024 (bài 1 trong tab Tài liệu tham khảo), hàm dài được cắt thành nhiều đoạn
512 token, mỗi đoạn đi qua encoder một lần, rồi các vector biểu diễn của cùng một
hàm được max-pooling lại thành một vector duy nhất.

Bài báo cắt làm hai đoạn. Ở đây số đoạn là tham số ``max_chunks`` để đo được phần
bị cắt bỏ, với mặc định 2 cho đúng bài báo. ``max_chunks=1`` tương đương cắt cụt
thẳng, dùng làm mốc đối chiếu rẻ tiền.

Thư viện ``transformers`` chỉ được import bên trong hàm dựng model, nên phần cắt
đoạn và pooling test được mà không cần tải trọng số.
"""

from __future__ import annotations

from typing import Any, Sequence

import torch
from torch import Tensor, nn

POOLINGS = ("max", "mean", "first")


def chunk_token_ids(
    ids: Sequence[int], max_length: int, max_chunks: int, cls_id: int, sep_id: int
) -> tuple[list[list[int]], int]:
    """Cắt chuỗi id thành các đoạn đã gắn token đặc biệt.

    ``ids`` là id của phần thân, chưa có token đặc biệt. Mỗi đoạn chứa tối đa
    ``max_length - 2`` id thân, cộng ``cls_id`` ở đầu và ``sep_id`` ở cuối.

    Trả về danh sách đoạn cùng số id thân thực sự được giữ lại. Chênh lệch giữa
    số này và ``len(ids)`` là phần bị cắt bỏ, cần báo cáo.
    """
    if max_length < 3:
        raise ValueError(f"max_length phải ít nhất 3, nhận {max_length}")
    if max_chunks < 1:
        raise ValueError(f"max_chunks phải ít nhất 1, nhận {max_chunks}")
    window = max_length - 2
    body = list(ids)
    pieces = [body[start:start + window] for start in range(0, len(body), window)] or [[]]
    kept = pieces[:max_chunks]
    used = sum(len(piece) for piece in kept)
    return [[cls_id, *piece, sep_id] for piece in kept], used


def tokenize_samples(
    samples: Sequence[dict[str, Any]], tokenizer: Any, max_length: int, max_chunks: int,
    text_field: str = "func",
) -> list[dict[str, Any]]:
    """Mã hóa trước một lần cho cả quá trình huấn luyện.

    Giữ nguyên mẫu gốc và thêm ``chunks``, ``n_body_tokens`` và ``n_used_tokens``
    để thống kê độ dài cùng tỷ lệ bị cắt.
    """
    cls_id = tokenizer.cls_token_id
    sep_id = tokenizer.sep_token_id
    if cls_id is None or sep_id is None:
        raise ValueError("Tokenizer phải có cls_token_id và sep_token_id")
    encoded = []
    for sample in samples:
        body = tokenizer(sample[text_field], add_special_tokens=False,
                         truncation=False)["input_ids"]
        chunks, used = chunk_token_ids(body, max_length, max_chunks, cls_id, sep_id)
        encoded.append({**sample, "chunks": chunks,
                        "n_body_tokens": len(body), "n_used_tokens": used})
    return encoded


def collate_text(batch: Sequence[dict[str, Any]], pad_id: int) -> dict[str, Tensor]:
    """Gộp một batch, chỉ đệm tới kích thước lớn nhất trong chính batch đó.

    Đệm theo batch thay vì theo hằng số toàn cục giúp batch toàn hàm ngắn chạy
    nhanh hơn hẳn, vì phần lớn hàm chỉ cần một đoạn.
    """
    n_chunks = max(len(item["chunks"]) for item in batch)
    width = max(len(chunk) for item in batch for chunk in item["chunks"])
    size = (len(batch), n_chunks, width)
    input_ids = torch.full(size, pad_id, dtype=torch.long)
    attention_mask = torch.zeros(size, dtype=torch.long)
    chunk_mask = torch.zeros(size[:2], dtype=torch.bool)
    for i, item in enumerate(batch):
        for j, chunk in enumerate(item["chunks"]):
            input_ids[i, j, : len(chunk)] = torch.tensor(chunk, dtype=torch.long)
            attention_mask[i, j, : len(chunk)] = 1
            chunk_mask[i, j] = True
    return {"input_ids": input_ids, "attention_mask": attention_mask,
            "chunk_mask": chunk_mask,
            "y": torch.tensor([int(item["y"]) for item in batch], dtype=torch.long)}


def pool_chunks(hidden: Tensor, chunk_mask: Tensor, pooling: str) -> Tensor:
    """Gộp biểu diễn các đoạn của cùng một hàm thành một vector.

    ``hidden`` có dạng [B, C, H], ``chunk_mask`` dạng [B, C]. Đoạn đệm không được
    tham gia vào kết quả.
    """
    if pooling not in POOLINGS:
        raise ValueError(f"Pooling không hợp lệ: {pooling}")
    if pooling == "first":
        return hidden[:, 0]
    mask = chunk_mask.unsqueeze(-1)
    if pooling == "mean":
        total = (hidden * mask).sum(dim=1)
        return total / mask.sum(dim=1).clamp(min=1)
    filled = hidden.masked_fill(~mask, torch.finfo(hidden.dtype).min)
    return filled.max(dim=1).values


class ChunkedTextClassifier(nn.Module):
    """Encoder pretrained cộng đầu phân loại tuyến tính trên vector đã pooling."""

    def __init__(self, encoder: nn.Module, n_classes: int, dropout: float = 0.1,
                 pooling: str = "max") -> None:
        super().__init__()
        if pooling not in POOLINGS:
            raise ValueError(f"Pooling không hợp lệ: {pooling}")
        self.encoder = encoder
        self.pooling = pooling
        self.dropout = nn.Dropout(dropout)
        self.head = nn.Linear(encoder.config.hidden_size, n_classes)

    def forward(self, batch: dict[str, Tensor]) -> Tensor:
        input_ids = batch["input_ids"]
        chunk_mask = batch["chunk_mask"]
        b, c, length = input_ids.shape
        flat_mask = chunk_mask.reshape(-1)
        # Chỉ đẩy đoạn thật qua encoder. Hàm ngắn chỉ có một đoạn, nên với batch
        # trộn dài ngắn thì bước này bỏ qua được phần lớn đoạn đệm.
        ids = input_ids.reshape(b * c, length)[flat_mask]
        attention = batch["attention_mask"].reshape(b * c, length)[flat_mask]
        encoded = self.encoder(input_ids=ids, attention_mask=attention).last_hidden_state[:, 0]
        hidden = encoded.new_zeros((b * c, encoded.shape[-1]))
        hidden[flat_mask] = encoded
        pooled = pool_chunks(hidden.view(b, c, -1), chunk_mask, self.pooling)
        return self.head(self.dropout(pooled))


def build_encoder(model_name: str, local_files_only: bool = False) -> nn.Module:
    """Tải encoder pretrained. Tách riêng để phần còn lại không cần transformers."""
    from transformers import AutoModel

    return AutoModel.from_pretrained(model_name, local_files_only=local_files_only)


def build_tokenizer(model_name: str, local_files_only: bool = False) -> Any:
    """Tải tokenizer tương ứng với encoder."""
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(model_name, local_files_only=local_files_only)


def length_statistics(encoded: Sequence[dict[str, Any]], max_length: int,
                      max_chunks: int) -> dict[str, float]:
    """Thống kê độ dài hàm theo token để báo cáo phần bị cắt bỏ."""
    if not encoded:
        return {}
    lengths = sorted(item["n_body_tokens"] for item in encoded)
    capacity = (max_length - 2) * max_chunks
    body = sum(lengths)
    used = sum(item["n_used_tokens"] for item in encoded)

    def percentile(fraction: float) -> int:
        index = min(len(lengths) - 1, max(0, round(fraction * (len(lengths) - 1))))
        return lengths[index]

    return {
        "n_samples": len(lengths),
        "mean_tokens": body / len(lengths),
        "median_tokens": percentile(0.5),
        "p90_tokens": percentile(0.9),
        "p99_tokens": percentile(0.99),
        "max_tokens": lengths[-1],
        "capacity_tokens": capacity,
        "share_over_one_chunk": sum(1 for n in lengths if n > max_length - 2) / len(lengths),
        "share_truncated": sum(1 for n in lengths if n > capacity) / len(lengths),
        "token_coverage": used / body if body else 1.0,
    }

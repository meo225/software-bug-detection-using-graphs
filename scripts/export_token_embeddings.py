"""Task 4.3: xuất bảng khởi tạo embedding token từ một mô hình ngôn ngữ mã nguồn.

Mỗi token trong vocabulary của Task 4.0 được đưa qua tokenizer của mô hình, lấy trung bình các
vector embedding đầu vào của những sub-token tương ứng, rồi chiếu xuống ``dim`` chiều bằng SVD
rút gọn. Kết quả được chuẩn hóa để có độ lệch chuẩn 1, khớp thang khởi tạo mặc định của
``nn.Embedding``, nên chỉ thay đổi hướng khởi tạo chứ không thay đổi độ lớn.

Bước này cần thư viện ``transformers`` và mạng, nên được tách khỏi mã huấn luyện. Tệp kết quả
chỉ là tensor, mã huấn luyện không phụ thuộc ``transformers``.

Ví dụ:
    python scripts/export_token_embeddings.py --processed-dir <processed> \
        --out-dir /kaggle/working/token_init --dim 128
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import torch  # noqa: E402

SPECIAL = ("<PAD>", "<UNK>", "<MASK>")


def subword_matrix(tokens: list[str], model_name: str) -> torch.Tensor:
    """Trung bình embedding đầu vào của các sub-token, cho từng token trong vocabulary."""
    from transformers import AutoModel, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name)
    table = model.get_input_embeddings().weight.detach()
    rows = torch.zeros(len(tokens), table.shape[1])
    missing = 0
    for index, token in enumerate(tokens):
        if token in SPECIAL:
            continue
        ids = tokenizer.encode(token, add_special_tokens=False)
        if not ids:
            missing += 1
            continue
        rows[index] = table[torch.tensor(ids)].mean(dim=0)
    print(f"{len(tokens)} token, {missing} token không có sub-token nào")
    return rows


def project(rows: torch.Tensor, dim: int) -> torch.Tensor:
    """Chiếu xuống ``dim`` chiều bằng SVD rút gọn rồi chuẩn hóa về độ lệch chuẩn 1."""
    if dim > rows.shape[1]:
        raise ValueError(f"dim phải nhỏ hơn hoặc bằng {rows.shape[1]}")
    centred = rows - rows.mean(dim=0, keepdim=True)
    _, _, v = torch.svd_lowrank(centred, q=min(dim + 8, min(centred.shape)), niter=8)
    reduced = centred @ v[:, :dim]
    std = reduced.std()
    if std <= 0:
        raise ValueError("Phép chiếu cho ra ma trận hằng")
    return reduced / std


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--protocols", nargs="+", default=["project_wise", "seen_project"])
    parser.add_argument("--model-name", default="microsoft/codebert-base")
    parser.add_argument("--dim", type=int, default=128)
    args = parser.parse_args()
    if args.dim < 1:
        parser.error("dim phải dương")

    torch.manual_seed(0)  # svd_lowrank dùng phép chiếu ngẫu nhiên
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for protocol in args.protocols:
        vocab = json.loads((args.processed_dir / protocol / "vocab.json").read_text(encoding="utf-8"))
        tokens = [token for token, _ in sorted(vocab["token"].items(), key=lambda kv: kv[1])]
        matrix = project(subword_matrix(tokens, args.model_name), args.dim)
        matrix[0] = 0.0  # <PAD>
        destination = args.out_dir / f"{protocol}_dim{args.dim}.pt"
        torch.save({"model_name": args.model_name, "protocol": protocol, "dim": args.dim,
                    "n_tokens": len(tokens), "matrix": matrix}, destination)
        print(f"{protocol}: {tuple(matrix.shape)} -> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

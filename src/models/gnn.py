"""GCN và GGNN thuần PyTorch (không phụ thuộc PyTorch Geometric) cho Task 4.1a.

- ``GCN``: lan truyền chuẩn hóa đối xứng trên đồ thị vô hướng, không phân biệt loại cạnh.
- ``GGNN``: mỗi loại cạnh theo mỗi chiều có một ma trận riêng, tổng hợp bằng phép cộng rồi cập nhật bằng GRU.

Cạnh ngược được thêm lúc train (``add_reverse``) vì dữ liệu chỉ lưu cạnh có hướng gốc.
Với Graph A, ``edge_type`` luôn bằng 0 nên GGNN chỉ còn phân biệt chiều cạnh.
"""

from __future__ import annotations

from typing import Any

import torch
from torch import Tensor, nn

NUM_EDGE_TYPES = 3  # 0 = AST, 1 = CFG, 2 = DATA_DEP


def collate(items: list[dict[str, Any]], add_reverse: bool = True) -> dict[str, Tensor]:
    """Gộp nhiều graph thành một batch lớn (các graph không liên thông với nhau)."""
    x_type, x_tok, x_rel, batch, ys = [], [], [], [], []
    src, dst, etype, direction = [], [], [], []
    offset = 0
    for g, item in enumerate(items):
        n = item["x_type"].shape[0]
        x_type.append(item["x_type"])
        x_tok.append(item["x_tok"])
        x_rel.append(item["x_rel"])
        batch.append(torch.full((n,), g, dtype=torch.long))
        ys.append(item["y"])
        ei = item["edge_index"] + offset
        e = ei.shape[1]
        src.append(ei[0]); dst.append(ei[1]); etype.append(item["edge_type"])
        direction.append(torch.zeros(e, dtype=torch.long))
        if add_reverse:
            src.append(ei[1]); dst.append(ei[0]); etype.append(item["edge_type"])
            direction.append(torch.ones(e, dtype=torch.long))
        offset += n
    return {
        "x_type": torch.cat(x_type), "x_tok": torch.cat(x_tok), "x_rel": torch.cat(x_rel),
        "batch": torch.cat(batch), "y": torch.cat(ys),
        "src": torch.cat(src), "dst": torch.cat(dst),
        "edge_type": torch.cat(etype), "direction": torch.cat(direction),
        "num_graphs": torch.tensor(len(items)),
    }


def truncate_graph(item: dict[str, Any], max_nodes: int) -> dict[str, Any]:
    """Giữ ``max_nodes`` node đầu theo thứ tự lưu và các cạnh nối hai node được giữ."""
    n = item["x_type"].shape[0]
    if n <= max_nodes:
        return item
    keep = (item["edge_index"] < max_nodes).all(dim=0)
    return {**item, "x_type": item["x_type"][:max_nodes], "x_tok": item["x_tok"][:max_nodes],
            "x_rel": item["x_rel"][:max_nodes], "edge_index": item["edge_index"][:, keep],
            "edge_type": item["edge_type"][keep]}


def filter_edge_types(item: dict[str, Any], keep: tuple[int, ...]) -> dict[str, Any]:
    """Chỉ giữ cạnh có loại thuộc ``keep`` (0 = AST, 1 = CFG, 2 = DATA_DEP); node không đổi."""
    mask = torch.isin(item["edge_type"], torch.tensor(sorted(set(keep)), dtype=item["edge_type"].dtype))
    return {**item, "edge_index": item["edge_index"][:, mask], "edge_type": item["edge_type"][mask]}


class NodeEmbedding(nn.Module):
    """Loại node + trung bình embedding token (bỏ đệm) + vị trí tương đối trong hàm."""

    def __init__(self, n_types: int, n_tokens: int, dim: int, token_init: Tensor | None = None) -> None:
        super().__init__()
        self.type_emb = nn.Embedding(n_types, dim, padding_idx=0)
        self.tok_emb = nn.Embedding(n_tokens, dim, padding_idx=0)
        self.rel = nn.Linear(1, dim)
        if token_init is not None:
            set_token_init(self.tok_emb, token_init)

    def forward(self, b: dict[str, Tensor]) -> Tensor:
        mask = (b["x_tok"] != 0).unsqueeze(-1).float()
        tok = (self.tok_emb(b["x_tok"]) * mask).sum(1) / mask.sum(1).clamp(min=1.0)
        return self.type_emb(b["x_type"]) + tok + self.rel(b["x_rel"].unsqueeze(-1))


def set_token_init(embedding: nn.Embedding, matrix: Tensor) -> None:
    """Thay khởi tạo ngẫu nhiên của bảng embedding token bằng ``matrix``.

    Kiến trúc không đổi: chỉ giá trị khởi tạo khác, bảng vẫn được huấn luyện tiếp.
    Hàng đệm (chỉ số 0) luôn bị đặt về 0 để giữ đúng ngữ nghĩa ``padding_idx``.
    """
    if matrix.shape != embedding.weight.shape:
        raise ValueError(f"Token init phải có dạng {tuple(embedding.weight.shape)}, nhận {tuple(matrix.shape)}")
    if not torch.isfinite(matrix).all():
        raise ValueError("Token init chứa giá trị không hữu hạn")
    with torch.no_grad():
        embedding.weight.copy_(matrix.to(embedding.weight.dtype))
        embedding.weight[embedding.padding_idx].zero_()


def _degree_norm(src: Tensor, dst: Tensor, n: int) -> Tensor:
    deg = torch.zeros(n, device=src.device).index_add_(0, dst, torch.ones_like(dst, dtype=torch.float))
    inv = deg.clamp(min=1.0).pow(-0.5)
    return inv[src] * inv[dst]


class GCNLayer(nn.Module):
    def __init__(self, dim: int) -> None:
        super().__init__()
        self.lin = nn.Linear(dim, dim)

    def forward(self, h: Tensor, b: dict[str, Tensor]) -> Tensor:
        n = h.shape[0]
        loops = torch.arange(n, device=h.device)
        src = torch.cat([b["src"], b["dst"], loops])  # vô hướng hóa + tự nối
        dst = torch.cat([b["dst"], b["src"], loops])
        norm = _degree_norm(src, dst, n).unsqueeze(-1)
        out = torch.zeros_like(h).index_add_(0, dst, h[src] * norm)
        return torch.relu(self.lin(out))


class GGNNLayer(nn.Module):
    """Một bước lan truyền: m_v = sum_e W[loại, chiều] h_u, rồi h_v = GRU(m_v, h_v)."""

    def __init__(self, dim: int) -> None:
        super().__init__()
        self.msg = nn.ModuleList(nn.Linear(dim, dim) for _ in range(NUM_EDGE_TYPES * 2))
        self.gru = nn.GRUCell(dim, dim)

    def forward(self, h: Tensor, b: dict[str, Tensor]) -> Tensor:
        agg = torch.zeros_like(h)
        slot = b["edge_type"] * 2 + b["direction"]
        for s, lin in enumerate(self.msg):
            sel = slot == s
            if sel.any():
                agg.index_add_(0, b["dst"][sel], lin(h[b["src"][sel]]))
        return self.gru(agg, h)


class GNNClassifier(nn.Module):
    """Embedding node, ``num_layers`` lớp GCN hoặc ``steps`` bước GGNN, readout mean+max, MLP."""

    def __init__(self, kind: str, n_types: int, n_tokens: int, n_classes: int,
                 dim: int = 128, num_layers: int = 3, dropout: float = 0.2,
                 token_init: Tensor | None = None) -> None:
        super().__init__()
        if kind not in {"gcn", "ggnn"}:
            raise ValueError(f"kind không hợp lệ: {kind!r}")
        self.kind = kind
        self.embed = NodeEmbedding(n_types, n_tokens, dim, token_init)
        if kind == "gcn":
            self.layers = nn.ModuleList(GCNLayer(dim) for _ in range(num_layers))
        else:  # GGNN dùng chung tham số giữa các bước theo bài báo gốc
            self.layers = nn.ModuleList([GGNNLayer(dim)])
        self.steps = num_layers
        self.dropout = nn.Dropout(dropout)
        self.head = nn.Sequential(nn.Linear(2 * dim, dim), nn.ReLU(), nn.Dropout(dropout),
                                  nn.Linear(dim, n_classes))

    def forward(self, b: dict[str, Tensor]) -> Tensor:
        h = self.embed(b)
        if self.kind == "gcn":
            for layer in self.layers:
                h = self.dropout(layer(h, b))
        else:
            for _ in range(self.steps):
                h = self.layers[0](h, b)
        g = int(b["num_graphs"])
        idx = b["batch"].unsqueeze(-1).expand_as(h)
        total = torch.zeros(g, h.shape[1], device=h.device).index_add_(0, b["batch"], h)
        count = torch.zeros(g, device=h.device).index_add_(
            0, b["batch"], torch.ones_like(b["batch"], dtype=torch.float)).clamp(min=1.0)
        mean = total / count.unsqueeze(-1)
        mx = torch.full((g, h.shape[1]), float("-inf"), device=h.device).scatter_reduce(
            0, idx, h, reduce="amax", include_self=True)
        return self.head(torch.cat([mean, mx], dim=-1))


def count_parameters(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)

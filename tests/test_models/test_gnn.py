"""Test GCN/GGNN: hình dạng đầu ra, độc lập giữa các graph trong batch và huấn luyện giảm loss."""

import random

import pytest

torch = pytest.importorskip("torch")

from src.models.gnn import GNNClassifier, collate, filter_edge_types, truncate_graph  # noqa: E402
from src.training.gnn_trainer import balanced_class_weights, run_training  # noqa: E402


def _item(n: int, y: int, edge_types: tuple[int, ...] = (0,), seed: int = 0) -> dict:
    g = torch.Generator().manual_seed(seed)
    ei = torch.stack([torch.arange(n - 1), torch.arange(1, n)])
    et = torch.tensor([edge_types[i % len(edge_types)] for i in range(n - 1)], dtype=torch.long)
    return {"sample_id": f"s{seed}", "x_type": torch.randint(1, 5, (n,), generator=g),
            "x_tok": torch.randint(0, 8, (n, 3), generator=g),
            "x_rel": torch.rand(n, generator=g), "edge_index": ei, "edge_type": et,
            "y": torch.tensor([y]), "is_oversized": False}


@pytest.mark.parametrize("kind", ["gcn", "ggnn"])
def test_forward_shape_and_graph_independence(kind: str) -> None:
    a, b = _item(6, 0, (0, 1, 2), 1), _item(9, 1, (0, 1, 2), 2)
    model = GNNClassifier(kind, 6, 9, 4, dim=16).eval()
    both = model(collate([a, b]))
    assert both.shape == (2, 4)
    alone = model(collate([a]))
    assert torch.allclose(both[0], alone[0], atol=1e-5)  # graph khác trong batch không ảnh hưởng


def test_collate_adds_reverse_edges_with_direction_flag() -> None:
    batch = collate([_item(4, 0)], add_reverse=True)
    assert batch["src"].shape[0] == 6 and batch["direction"].tolist() == [0, 0, 0, 1, 1, 1]
    assert collate([_item(4, 0)], add_reverse=False)["src"].shape[0] == 3


def test_truncate_graph_drops_edges_outside() -> None:
    t = truncate_graph(_item(10, 0), 4)
    assert t["x_type"].shape[0] == 4 and t["edge_index"].max() < 4 and t["edge_index"].shape[1] == 3


def test_balanced_weights() -> None:
    w = balanced_class_weights([0, 0, 0, 1], 3)
    assert w[2] == 0 and torch.isclose(w[1], torch.tensor(2.0)) and torch.isclose(w[0], torch.tensor(2 / 3))


@pytest.mark.parametrize("kind", ["gcn", "ggnn"])
def test_training_learns_separable_toy_task(kind: str) -> None:
    # lớp 1 luôn có token 7 ở node đầu, lớp 0 thì không
    def make(i: int) -> dict:
        y = i % 2
        it = _item(5, y, seed=i)
        it["x_tok"] = torch.randint(1, 5, (5, 3))
        if y:
            it["x_tok"][0, 0] = 7
        return it

    data = [make(i) for i in range(600)]
    out = run_training(data[:400], data[400:500], data[500:], kind, 6, 9, ["a", "b"], seed=0, dim=32,
                       lr=1e-2, max_epochs=30, patience=30, batch_size=16, log=lambda *_: None,
                       device=torch.device("cpu"))
    assert out["reports"]["test"]["accuracy"] >= 0.9
    assert out["history"][-1]["train_loss"] < out["history"][0]["train_loss"]


def test_filter_edge_types_keeps_nodes_and_selected_types() -> None:
    item = _item(7, 0, (0, 1, 2), 3)
    out = filter_edge_types(item, (0, 2))
    assert set(out["edge_type"].tolist()) == {0, 2}
    assert out["edge_index"].shape[1] == out["edge_type"].shape[0] == 4
    assert torch.equal(out["x_type"], item["x_type"]) and torch.equal(out["x_tok"], item["x_tok"])
    assert filter_edge_types(item, (0, 1, 2))["edge_index"].shape == item["edge_index"].shape


def test_run_training_edge_types_default_unchanged_and_filter_applied() -> None:
    data = [_item(6, i % 2, (0, 1, 2), i) for i in range(48)]
    kwargs = dict(kind="ggnn", n_types=6, n_tokens=9, labels=["a", "b"], seed=0, dim=8,
                  max_epochs=2, patience=2, batch_size=16, log=lambda *_: None,
                  device=torch.device("cpu"))
    base = run_training(data[:32], data[32:40], data[40:], **kwargs)
    same = run_training(data[:32], data[32:40], data[40:], edge_types=None, **kwargs)
    full = run_training(data[:32], data[32:40], data[40:], edge_types=(0, 1, 2), **kwargs)
    assert base["history"] == same["history"] == full["history"]
    only_ast = run_training(data[:32], data[32:40], data[40:], edge_types=(0,), **kwargs)
    assert only_ast["history"] != base["history"] and only_ast["n_params"] == base["n_params"]

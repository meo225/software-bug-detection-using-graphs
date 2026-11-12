"""Kiểm thử cho Task 4.3: loss thích nghi, khởi tạo embedding token và ba nhánh thực nghiệm."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest
import torch
from torch import nn

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import train_gnn as cli  # noqa: E402
from scripts.export_token_embeddings import project  # noqa: E402
from src.models.gnn import GNNClassifier, set_token_init  # noqa: E402
from src.training import paper_experiments as arms  # noqa: E402
from src.training.gnn_trainer import run_training  # noqa: E402
from src.training.losses import (  # noqa: E402
    AdaptiveReweightedLoss, balanced_class_weights, build_loss, head_class_mask,
)

LONG_TAIL = [0] * 100 + [1] * 60 + [2] * 20 + [3] * 8 + [4] * 2


def test_head_mask_splits_by_cumulative_training_mass():
    mask = head_class_mask(LONG_TAIL, 6, head_fraction=0.5)
    assert mask.tolist() == [True, False, False, False, False, False]  # lớp 0 đã đủ 100/190
    wider = head_class_mask(LONG_TAIL, 6, head_fraction=0.9)
    assert wider.tolist() == [True, True, True, False, False, False]
    assert not head_class_mask(LONG_TAIL, 6)[5]  # lớp vắng mặt luôn thuộc nhóm đuôi
    for bad in (0.0, 1.0, -0.5):
        with pytest.raises(ValueError):
            head_class_mask(LONG_TAIL, 6, bad)


def test_adaptive_loss_matches_weighted_ce_shape_and_ramps_with_epoch():
    loss_fn, weights = build_loss("adaptive", LONG_TAIL, 5, max_epochs=40)
    assert torch.equal(weights, balanced_class_weights(LONG_TAIL, 5))
    logits = torch.randn(16, 5, generator=torch.Generator().manual_seed(0))
    target = torch.tensor([0, 1, 2, 3] * 4)
    loss_fn.set_epoch(1)
    assert loss_fn.beta == 0.0
    first = float(loss_fn(logits, target))
    loss_fn.set_epoch(40)
    assert loss_fn.beta == 1.0
    assert float(loss_fn(logits, target)) != first  # focal chỉ có hiệu lực khi beta > 0
    loss_fn.set_epoch(999)
    assert loss_fn.beta == 1.0  # không vượt quá 1
    with pytest.raises(ValueError):
        loss_fn.set_epoch(0)


def test_adaptive_loss_downweights_easy_tail_samples_relative_to_weighted_ce():
    """Mẫu đuôi đã dự đoán đúng chắc chắn phải đóng góp ít hơn so với cross-entropy thường."""
    weights = torch.ones(3)
    head = torch.tensor([True, False, False])
    adaptive = AdaptiveReweightedLoss(weights, head, gamma=2.0, smoothing=0.0, max_epochs=2)
    adaptive.set_epoch(2)
    easy = torch.tensor([[0.0, 8.0, 0.0]])  # lớp đuôi 1, dự đoán rất chắc
    target = torch.tensor([1])
    plain = nn.CrossEntropyLoss(weight=weights)
    assert float(adaptive(easy, target)) < float(plain(easy, target))
    hard = torch.tensor([[8.0, 0.0, 0.0]])
    assert float(adaptive(hard, target)) == pytest.approx(float(plain(hard, target)), rel=0.05)


def test_adaptive_loss_rejects_invalid_arguments():
    weights, head = torch.ones(3), torch.tensor([True, False, False])
    for kwargs in ({"gamma": -1.0}, {"smoothing": 1.0}, {"max_epochs": 0}):
        with pytest.raises(ValueError):
            AdaptiveReweightedLoss(weights, head, **kwargs)
    with pytest.raises(ValueError):
        AdaptiveReweightedLoss(torch.ones(4), head)
    with pytest.raises(ValueError):
        build_loss("unknown", LONG_TAIL, 5, 40)


def test_token_init_replaces_embedding_and_keeps_padding_row_zero():
    matrix = torch.randn(11, 8, generator=torch.Generator().manual_seed(1))
    model = GNNClassifier("ggnn", 4, 11, 3, dim=8, num_layers=2, token_init=matrix)
    weight = model.embed.tok_emb.weight
    assert torch.equal(weight[0], torch.zeros(8))  # padding_idx
    assert torch.allclose(weight[1:], matrix[1:])
    assert weight.requires_grad  # vẫn được huấn luyện tiếp
    plain = GNNClassifier("ggnn", 4, 11, 3, dim=8, num_layers=2)
    assert not torch.allclose(plain.embed.tok_emb.weight[1:], matrix[1:])
    with pytest.raises(ValueError):
        set_token_init(nn.Embedding(11, 8, padding_idx=0), torch.randn(11, 4))
    with pytest.raises(ValueError):
        set_token_init(nn.Embedding(11, 8, padding_idx=0), torch.full((11, 8), float("nan")))


def test_projection_reduces_dimension_deterministically_with_unit_scale():
    rows = torch.randn(80, 32, generator=torch.Generator().manual_seed(2))
    torch.manual_seed(0)
    first = project(rows, 8)
    torch.manual_seed(0)
    assert torch.allclose(first, project(rows, 8))
    assert first.shape == (80, 8)
    assert float(first.std()) == pytest.approx(1.0, rel=1e-4)
    with pytest.raises(ValueError):
        project(rows, 64)


def test_arm_definitions_change_exactly_one_factor_against_the_control():
    control = arms.arm_configuration("C0")
    assert control["num_layers"] == 2 and control["loss"] == "weighted_ce"
    assert not control["token_init"]
    for arm in ("P1", "P2"):
        changed = {k: v for k, v in arms.arm_configuration(arm).items() if v != control[k]}
        assert len(changed) == 1, f"{arm} đổi {changed}"
        assert arm in arms.ARM_HYPOTHESES and arm in arms.ARM_LABELS
    with pytest.raises(ValueError):
        arms.arm_configuration("X9")


def graph(label: int, nodes: int = 6) -> dict:
    return {"sample_id": f"s{label}-{nodes}", "x_type": torch.randint(1, 3, (nodes,)),
            "x_tok": torch.randint(0, 4, (nodes, 2)), "x_rel": torch.linspace(0, 1, nodes),
            "edge_index": torch.tensor([[0, 1, 2, 3, 0], [1, 2, 3, 4, 5]]),
            "edge_type": torch.tensor([0, 1, 2, 0, 1]), "y": torch.tensor([label]),
            "is_oversized": False}


@pytest.fixture
def processed(tmp_path):
    root = tmp_path / "processed"
    for protocol in arms.PROTOCOLS:
        (root / protocol).mkdir(parents=True)
        (root / protocol / "vocab.json").write_text(json.dumps(
            {"node_type": {"<PAD>": 0, "a": 1, "b": 2}, "token": {"<PAD>": 0, "a": 1, "b": 2, "c": 3}, "k": 2}))
        for split in ("train", "validation", "test"):
            torch.save([graph(i % 2) for i in range(8)], root / protocol / f"graph_b_{split}.pt")
    return root


def run_arm(monkeypatch, processed, out: Path, arm: str, token_init: Path | None = None):
    monkeypatch.setattr(sys, "argv", [
        "train_gnn.py", "--processed-dir", str(processed), "--out-dir", str(out),
        "--models", arms.SCOPE[0], "--graphs", arms.SCOPE[1],
        "--protocols", *arms.PROTOCOLS, "--seeds", *map(str, arms.SEEDS),
        "--config-id", arm, *arms.arm_arguments(arm, str(token_init) if token_init else None)])
    assert cli.main() == 0
    return arms.validate_arm(out, arm)


def test_all_three_arms_run_end_to_end_and_validate(monkeypatch, processed, tmp_path):
    init_path = tmp_path / "pw.pt"
    torch.save({"model_name": "test", "protocol": "project_wise", "dim": 128, "n_tokens": 4,
                "matrix": torch.randn(4, 128)}, init_path)
    metas = {}
    for arm in ("C0", "P2"):
        metas[arm] = run_arm(monkeypatch, processed, tmp_path / arm, arm)
    assert metas["C0"]["arguments"]["loss"] == "weighted_ce"
    assert metas["P2"]["arguments"]["loss"] == "adaptive"
    with (tmp_path / "C0" / "results.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    assert {r["split"] for r in rows} == {"validation", "test"}
    assert {(r["model"], r["graph"]) for r in rows} == {arms.SCOPE}
    # Nhánh P1 dùng khởi tạo token: metadata phải ghi lại dấu vân tay của tệp.
    monkeypatch.setattr(sys, "argv", [
        "train_gnn.py", "--processed-dir", str(processed), "--out-dir", str(tmp_path / "P1"),
        "--models", "ggnn", "--graphs", "graph_b", "--protocols", "project_wise",
        "--seeds", "42", "--config-id", "P1", *arms.arm_arguments("P1", str(init_path))])
    assert cli.main() == 0
    meta = json.loads((tmp_path / "P1" / "metadata.json").read_text())
    assert meta["token_init"]["sha256"] and meta["token_init"]["path"] == str(init_path)


def test_validate_arm_rejects_mislabelled_or_incomplete_results(monkeypatch, processed, tmp_path):
    out = tmp_path / "C0"
    run_arm(monkeypatch, processed, out, "C0")
    with pytest.raises(ValueError, match="Hàm mất mát"):
        arms.validate_arm(out, "P2")  # kết quả C0 không được nhận là P2
    meta = json.loads((out / "metadata.json").read_text())
    meta["arguments"]["seeds"] = [42]
    (out / "metadata.json").write_text(json.dumps(meta))
    with pytest.raises(ValueError, match="ba seed"):
        arms.validate_arm(out, "C0")


def test_token_init_must_match_protocol_and_shape(tmp_path):
    path = tmp_path / "init.pt"
    torch.save({"model_name": "t", "protocol": "project_wise", "dim": 4, "n_tokens": 5,
                "matrix": torch.randn(5, 4)}, path)
    assert cli.load_token_init(path, "project_wise", 5, 4).shape == (5, 4)
    with pytest.raises(ValueError, match="protocol"):
        cli.load_token_init(path, "seen_project", 5, 4)
    with pytest.raises(ValueError, match="dạng"):
        cli.load_token_init(path, "project_wise", 6, 4)


def test_cli_rejects_incompatible_option_combinations(monkeypatch, tmp_path):
    base = ["train_gnn.py", "--processed-dir", str(tmp_path), "--out-dir", str(tmp_path / "o")]
    for extra in (["--loss", "adaptive", "--frozen-selection", str(tmp_path / "f.json")],
                  ["--focal-gamma", "-1"], ["--label-smoothing", "1.0"], ["--head-fraction", "0"]):
        monkeypatch.setattr(sys, "argv", base + extra)
        with pytest.raises(SystemExit):
            cli.parse_args()


def test_adaptive_loss_cannot_pair_with_validation_loss_stopping():
    with pytest.raises(ValueError, match="weighted_ce"):
        run_training([graph(0)], [graph(0)], [], "ggnn", 3, 4, ["a", "b"], 42,
                     loss="adaptive", early_stopping="val_loss")


def test_default_path_is_unchanged_by_the_new_options():
    """Hai lần chạy cùng seed, một lần dùng mặc định tường minh, phải cho kết quả giống nhau."""
    data = [graph(i % 2, 6 + i % 3) for i in range(12)]
    common = dict(kind="ggnn", n_types=3, n_tokens=4, labels=["a", "b"], seed=42,
                  dim=8, num_layers=2, max_epochs=2, patience=2, evaluate_test=False,
                  device=torch.device("cpu"), log=lambda *a, **k: None)
    first = run_training(data, data, [], **common)
    second = run_training(data, data, [], loss="weighted_ce", token_init=None, **common)
    assert first["history"] == second["history"]
    assert first["loss"] == "weighted_ce"

"""Kiểm thử cho Task 4.3: loss thích nghi, khởi tạo embedding token và ba nhánh thực nghiệm."""
from __future__ import annotations

import csv
import json
import re
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


def run_arm(monkeypatch, processed, out: Path, arm: str, token_init: list[Path] | None = None):
    monkeypatch.setattr(sys, "argv", [
        "train_gnn.py", "--processed-dir", str(processed), "--out-dir", str(out),
        "--models", arms.SCOPE[0], "--graphs", arms.SCOPE[1],
        "--protocols", *arms.PROTOCOLS, "--seeds", *map(str, arms.SEEDS),
        "--config-id", arm, *arms.arm_arguments(arm, token_init)])
    assert cli.main() == 0
    return arms.validate_arm(out, arm)


def token_init_files(tmp_path, dim=128, n_tokens=4):
    paths = []
    for protocol in arms.PROTOCOLS:
        path = tmp_path / f"{protocol}.pt"
        torch.save({"model_name": "test", "protocol": protocol, "dim": dim, "n_tokens": n_tokens,
                    "matrix": torch.randn(n_tokens, dim)}, path)
        paths.append(path)
    return paths


def test_all_three_arms_run_end_to_end_and_validate(monkeypatch, processed, tmp_path):
    init_paths = token_init_files(tmp_path)
    metas = {arm: run_arm(monkeypatch, processed, tmp_path / arm, arm,
                          init_paths if arm == "P1" else None)
             for arm in ("C0", "P1", "P2")}
    assert metas["C0"]["arguments"]["loss"] == "weighted_ce"
    assert metas["P2"]["arguments"]["loss"] == "adaptive"
    assert not metas["C0"]["arguments"]["token_init"]
    # Nhánh P1 phải ghi lại dấu vân tay tệp khởi tạo cho từng protocol.
    assert set(metas["P1"]["token_init"]) == set(arms.PROTOCOLS)
    assert all(entry["sha256"] for entry in metas["P1"]["token_init"].values())
    with (tmp_path / "C0" / "results.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    assert {r["split"] for r in rows} == {"validation", "test"}
    assert {(r["model"], r["graph"]) for r in rows} == {arms.SCOPE}


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


def test_token_init_is_selected_per_protocol_and_shape_checked(tmp_path):
    paths = token_init_files(tmp_path, dim=4, n_tokens=5)
    for protocol in arms.PROTOCOLS:
        chosen = cli.load_token_init(paths, protocol, 5, 4)
        expected = torch.load(tmp_path / f"{protocol}.pt", weights_only=True)["matrix"]
        assert torch.equal(chosen, expected)  # không lấy nhầm tệp của protocol khác
    with pytest.raises(ValueError, match="đúng một tệp"):
        cli.load_token_init([paths[0]], "seen_project", 5, 4)
    with pytest.raises(ValueError, match="dạng"):
        cli.load_token_init(paths, "project_wise", 6, 4)


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


NOTEBOOK = ROOT / "notebooks/4_3_paper_experiments.ipynb"


def notebook_cells():
    payload = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    return ["".join(c["source"]) for c in payload["cells"] if c["cell_type"] == "code"]


def test_notebook_is_valid_unexecuted_and_pinned():
    import ast
    import nbformat
    notebook = nbformat.read(NOTEBOOK, as_version=4)
    nbformat.validate(notebook)
    for cell in notebook.cells:
        if cell.cell_type == "code":
            assert cell.execution_count is None and not cell.outputs
            ast.parse(cell.source)
    text = "\n".join(notebook_cells())
    assert 'APPROVED_BRANCH = "feature/4_3_paper_experiments"' in text
    assert "scripts/train_gnn.py" in text and "scripts/export_token_embeddings.py" in text
    assert "arms.arm_arguments" in text, "Notebook phải lấy cấu hình từ mã nguồn, không tự viết lại"
    assert "class GNNClassifier" not in text and "def run_training" not in text
    assert re.search(r'APPROVED_COMMIT = "[0-9a-f]{40}"', text)


def test_notebook_disabled_stages_touch_nothing(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Khi tắt, notebook không được chạm vào Git, GPU, dữ liệu hay subprocess")
    for name in ("run", "Popen", "check_output"):
        monkeypatch.setattr(__import__("subprocess"), name, forbidden)
    namespace = {}
    for source in notebook_cells():
        exec(compile(source.replace("RUN_EXPERIMENTS = True", "RUN_EXPERIMENTS = False"),
                     "<notebook>", "exec"), namespace)
    assert not namespace["ACTIVE"] and not namespace["RUN_EXPERIMENTS"]


def test_notebook_experiment_and_plot_cells_produce_every_figure(monkeypatch, processed, tmp_path):
    """Chạy các ô thực nghiệm và vẽ biểu đồ trên dữ liệu giả, đảm bảo không ô nào lỗi."""
    import matplotlib
    matplotlib.use("Agg")
    out = tmp_path / "results"
    init_paths = token_init_files(tmp_path, dim=128, n_tokens=4)
    token_init = dict(zip(arms.PROTOCOLS, init_paths))
    vocab = {p: json.loads((processed / p / "vocab.json").read_text()) for p in arms.PROTOCOLS}

    def run_script(script, arguments, log_path):
        assert script == "scripts/train_gnn.py"
        monkeypatch.setattr(sys, "argv", ["train_gnn.py", *arguments])
        assert cli.main() == 0
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("stub", encoding="utf-8")

    from src.graph.processed import ids_hash, load_schema
    from src.training.gcn_tuning import code_identity
    namespace = dict(ACTIVE=False, RUN_EXPERIMENTS=True, SAVED_RESULTS_ROOT=None,
                     OUT_DIR=out, READ_ROOT=out, INIT_DIR=tmp_path / "init",
                     FIG_DIR=tmp_path / "figures", SUBMISSION_DIR=tmp_path / "submission",
                     TOKEN_INIT=token_init, PROCESSED=processed, REPO_DIR=ROOT, VOCAB=vocab,
                     APPROVED_ARMS=["C0", "P1", "P2"], DATASET_ID="unspecified",
                     CODEBERT_NAME="test", arms=arms, torch=torch, json=json, csv=csv,
                     shutil=__import__("shutil"), Path=Path, ids_hash=ids_hash,
                     load_schema=load_schema, code_identity=code_identity, run_script=run_script)
    (tmp_path / "init").mkdir()
    for source in notebook_cells()[2:]:
        exec(compile(source, "<notebook>", "exec"), namespace)

    figures = {p.name for p in (tmp_path / "figures").iterdir()}
    assert {"arm_summary.csv", "effect_vs_control.csv", "effect_test_macro_f1.png",
            "per_cwe_groups.csv", "per_cwe_by_arm.png", "learning_curves.png",
            "history_comparison.csv", "history_comparison.png",
            "confusion_matrices.png"} <= figures
    effects = list(csv.DictReader((tmp_path / "figures/effect_vs_control.csv").open()))
    assert {row["protocol"] for row in effects} == set(arms.PROTOCOLS)
    assert all(row["kết luận"] for row in effects)
    submission = tmp_path / "submission"
    assert not list(submission.rglob("*.pt")), "Gói nộp không được chứa tensor nặng"
    assert (submission / "arms/C0/results.csv").is_file()
    assert (submission / "arms/experiment_plan.json").is_file()
    assert {p.stem for p in (submission / "token_init").glob("*.json")} == set(arms.PROTOCOLS)
    assert (tmp_path / "submission.zip").is_file()

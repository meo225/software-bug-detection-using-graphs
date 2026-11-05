"""Focused synthetic-data checks for the shared 4.1b tuning workflow."""
import copy
import csv
import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")

from src.models.gnn import GNNClassifier, collate
from src.training import gnn_trainer as trainer
from src.training import gcn_tuning as tuning
from scripts import train_gnn as cli

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def cpu_threads():
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(previous)


def graph(label=0):
    return {"sample_id": f"row-{label}", "x_type": torch.tensor([1, 2, 1]),
            "x_tok": torch.tensor([[1, 2], [2, 0], [1, 0]]),
            "x_rel": torch.tensor([0.0, 0.5, 1.0]),
            "edge_index": torch.tensor([[0, 1], [1, 2]]),
            "edge_type": torch.zeros(2, dtype=torch.long),
            "y": torch.tensor([label]), "is_oversized": False}


def train_kwargs():
    return dict(kind="gcn", n_types=3, n_tokens=3, labels=["a", "b"], seed=42,
                dim=4, num_layers=2, max_epochs=3, patience=2, batch_size=2,
                device=torch.device("cpu"), log=lambda *_: None)


def test_default_matches_original_baseline_trainer():
    source = subprocess.check_output(
        ["git", "-C", str(ROOT), "show", "7e8d3b0:src/training/gnn_trainer.py"], text=True, encoding="utf-8")
    reference = types.ModuleType("baseline_trainer")
    exec(compile(source, "baseline_trainer.py", "exec"), reference.__dict__)
    data = [graph(0), graph(1)]
    before = copy.deepcopy(data)
    old = reference.run_training(data, data, data, **train_kwargs())
    new = trainer.run_training(data, data, data, **train_kwargs())
    for key in ("reports", "history", "best_epoch", "epochs_run", "n_params"):
        assert new[key] == old[key]
    assert "val_loss" not in new["history"][0]
    assert "state_dict" not in new
    for item, original in zip(data, before):
        for key in ("x_type", "x_tok", "edge_index", "y"):
            assert torch.equal(item[key], original[key])


def test_validation_loss_stops_independently_of_best_f1(monkeypatch):
    snapshots = []
    def predict(model, *args):
        snapshots.append(copy.deepcopy(model.state_dict()))
        return [0], [0]
    monkeypatch.setattr(trainer, "predict", predict)
    scores = iter([0.1, 0.9, 0.3, 0.9, 0.2, 0.9])
    monkeypatch.setattr(trainer, "classification_report", lambda *args: {"macro_f1": next(scores)})
    losses = iter([0.9, 0.8, 0.7, 0.75, 0.76])
    monkeypatch.setattr(trainer, "validation_loss", lambda *args: next(losses))
    args = {**train_kwargs(), "max_epochs": 10}
    data = [graph(0), graph(1)]
    out = trainer.run_training(data, data, [], **args, early_stopping="val_loss",
                               evaluate_test=False, return_state=True)
    assert out["epochs_run"] == 5  # Raw F1 stopping would stop at epoch 4.
    assert out["best_epoch"] == 2  # Raw F1 tie at epoch 4 keeps the earlier model.
    assert [r["val_loss"] for r in out["history"]] == [0.9, 0.8, 0.7, 0.75, 0.76]  # Minimum loss is epoch 3, not the saved epoch.
    for key, tensor in out["state_dict"].items():
        assert torch.equal(tensor, snapshots[1][key])
        assert torch.equal(tensor, snapshots[-1][key])


def test_weighted_validation_loss_uses_global_denominator():
    data = [graph(0), graph(1), graph(1)]
    torch.manual_seed(42)
    model = GNNClassifier("gcn", 3, 3, 2, dim=4).eval()
    weights = torch.tensor([2.0, 0.5])
    expected = torch.nn.functional.cross_entropy(model(collate(data)), torch.tensor([0, 1, 1]), weight=weights)
    for batch_size in (1, 2, 3):
        actual = trainer.validation_loss(model, data, batch_size, True, torch.device("cpu"), weights)
        assert actual == pytest.approx(float(expected.detach()), rel=1e-6)
    with pytest.raises(ValueError, match="positive"):
        trainer.validation_loss(model, data, 2, True, torch.device("cpu"), torch.zeros(2))


@pytest.mark.parametrize("max_nodes", [None, 2])
def test_validation_only_never_touches_test(max_nodes):
    class Forbidden:
        def __bool__(self):
            raise AssertionError("test accessed")
        def __iter__(self):
            raise AssertionError("test accessed")
    data = [graph(0), graph(1)]
    out = trainer.run_training(data, data, Forbidden(), **train_kwargs(), evaluate_test=False, max_nodes=max_nodes)
    assert set(out["reports"]) == {"validation"}


@pytest.mark.parametrize("layers", [1, 2, 4])
def test_gcn_layer_count_and_edge_type_agnostic(layers):
    model = GNNClassifier("gcn", 3, 3, 2, dim=4, num_layers=layers, dropout=0).eval()
    data = graph(0)
    first = model(collate([data]))
    data["edge_type"][:] = 2
    second = model(collate([data]))
    assert len(model.layers) == layers
    assert first.shape == (1, 2)
    assert torch.equal(first, second)
    first.sum().backward()
    assert all(layer.lin.weight.grad is not None for layer in model.layers)


def test_configurations_change_only_one_factor():
    assert tuning.configuration("B0") == tuning.BASELINE
    for key, changes in tuning.CANDIDATES.items():
        cfg = tuning.configuration(key)
        assert {k: v for k, v in cfg.items() if v != tuning.BASELINE[k]} == changes
        assert len(changes) == (0 if key == "B0" else 1)
    assert tuning.configuration("E1")["early_stopping"] == "val_loss"
    assert tuning.configuration("L1")["num_layers"] == 2


@pytest.fixture
def processed(tmp_path):
    root = tmp_path / "processed"
    for protocol in tuning.PROTOCOLS:
        folder = root / protocol
        folder.mkdir(parents=True)
        (folder / "vocab.json").write_text(json.dumps({"node_type": {"p": 0, "a": 1, "b": 2},
                                                       "token": {"p": 0, "a": 1, "b": 2}, "k": 2}))
        # Deliberately no test file until after freezing.
        for split in ("train", "validation"):
            torch.save([graph(0), graph(1)], folder / f"graph_a_{split}.pt")
    return root


def call_cli(monkeypatch, processed, output, *extra):
    monkeypatch.setattr(sys, "argv", ["train_gnn.py", "--processed-dir", str(processed),
        "--out-dir", str(output), *extra])
    return cli.main()


def synthetic_candidates(monkeypatch, processed, tmp_path, equal_scores=False):
    """Mock optimization only; exercise real CLI loading, writing and checkpoint gates."""
    def train(*args, **kwargs):
        labels, dim = args[6], args[8]
        model = GNNClassifier(args[3], args[4], args[5], len(labels), dim, args[9], args[10])
        from src.evaluation.metrics import classification_report
        rep = classification_report([0, 1], [0, 1], labels)
        # H1 wins validation; checkpoint weights still use the official model.
        rep["macro_f1"] = 0.8 if dim == 64 and not equal_scores else 0.5
        return {"state_dict": model.state_dict(), "reports": {"validation": rep},
                "history": [{"epoch": 1, "train_loss": 1.0, "val_macro_f1": rep["macro_f1"]}],
                "best_epoch": 1, "epochs_run": 1, "n_params": sum(p.numel() for p in model.parameters()),
                "train_seconds": 0.1, "peak_gpu_mb": None}
    monkeypatch.setattr(cli, "run_training", train)
    directories=[]
    for key in ("B0", "H1"):
        out = tmp_path / key
        params = []
        for name, value in tuning.configuration(key).items():
            if value is not None:
                params += ["--" + name.replace("_", "-"), str(value)]
        call_cli(monkeypatch, processed, out, "--models", "gcn", "--graphs", "graph_a",
                 "--validation-only", "--save-checkpoints", "--config-id", key, *params)
        directories.append(out)
    return directories


def test_cli_freezes_then_evaluates_only_saved_winner(monkeypatch, processed, tmp_path):
    directories = synthetic_candidates(monkeypatch, processed, tmp_path)
    for folder in directories:
        assert {"results.csv", "per_class.csv", "confusion_matrices.json", "training_history.json",
                "summary.md", "metadata.json"} <= {p.name for p in folder.iterdir()}
        meta = json.loads((folder / "metadata.json").read_text())
        assert len(meta["runs"]) == 6
        assert meta["code"]["commit"]
        assert meta["environment"]["torch"]
        with (folder / "results.csv").open() as handle:
            assert {r["split"] for r in csv.DictReader(handle)} == {"validation"}
    frozen_path = tmp_path / "frozen.json"
    frozen = tuning.freeze_winner(directories, frozen_path)
    assert frozen["winner"]["config_id"] == "H1"
    assert frozen["winner"]["score"] == 0.8
    with pytest.raises(FileExistsError):
        tuning.freeze_winner(directories, frozen_path)
    for protocol in tuning.PROTOCOLS:
        torch.save([graph(0), graph(1)], processed / protocol / "graph_a_test.pt")
    def forbidden(*args, **kwargs):
        raise AssertionError("final evaluation must not train")
    monkeypatch.setattr(cli, "run_training", forbidden)
    output = tmp_path / "final"
    call_cli(monkeypatch, processed, output, "--frozen-selection", str(frozen_path))
    with (output / "results.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 6 and {r["split"] for r in rows} == {"test"}
    metadata = json.loads((output / "metadata.json").read_text())
    assert metadata["arguments"]["dim"] == 64
    assert metadata["arguments"]["config_id"] == "H1"
    assert metadata["frozen_selection_sha256"] == tuning.digest(frozen_path)
    with pytest.raises(FileExistsError):
        call_cli(monkeypatch, processed, output, "--frozen-selection", str(frozen_path))


def test_freeze_rejects_test_rows_and_mixed_factors(monkeypatch, processed, tmp_path):
    directories = synthetic_candidates(monkeypatch, processed, tmp_path)
    metadata_path = directories[1] / "metadata.json"
    original = json.loads(metadata_path.read_text())
    modified = copy.deepcopy(original)
    modified["arguments"]["dropout"] = 0.9
    metadata_path.write_text(json.dumps(modified))
    with pytest.raises(ValueError, match="declared"):
        tuning.freeze_winner(directories, tmp_path / "bad.json")
    metadata_path.write_text(json.dumps(original))
    results = directories[1] / "results.csv"
    results.write_text(results.read_text().replace("validation", "test"))
    modified = json.loads(metadata_path.read_text())
    modified["artifacts_sha256"]["results.csv"] = tuning.digest(results)
    metadata_path.write_text(json.dumps(modified))
    with pytest.raises(ValueError, match="contamination"):
        tuning.freeze_winner(directories, tmp_path / "bad.json")


def test_frozen_evaluation_rejects_changed_data_and_weights(monkeypatch, processed, tmp_path):
    directories = synthetic_candidates(monkeypatch, processed, tmp_path)
    frozen_path = tmp_path / "frozen.json"
    frozen = tuning.freeze_winner(directories, frozen_path)
    vocab = processed / "project_wise/vocab.json"
    original = vocab.read_bytes()
    vocab.write_bytes(original + b" ")
    with pytest.raises(ValueError, match="Dataset"):
        tuning.read_frozen(frozen_path, ROOT, processed, ROOT / "configs/graph/schema_spec.yaml")
    vocab.write_bytes(original)
    cp = tmp_path / frozen["winner"]["directory"] / frozen["winner"]["metadata"]["runs"][0]["checkpoint"]
    with cp.open("ab") as handle:
        handle.write(b"changed")
    with pytest.raises(ValueError, match="hash"):
        tuning.read_frozen(frozen_path, ROOT, processed, ROOT / "configs/graph/schema_spec.yaml")


def test_cli_real_tiny_validation_only(monkeypatch, processed, tmp_path):
    out = tmp_path / "tiny"
    call_cli(monkeypatch, processed, out, "--models", "gcn", "--graphs", "graph_a",
             "--protocols", "project_wise", "--seeds", "42", "--validation-only",
             "--save-checkpoints", "--early-stopping", "val_loss", "--dim", "4",
             "--num-layers", "1", "--max-nodes", "2", "--max-epochs", "2")
    history = json.loads((out / "training_history.json").read_text())
    assert "val_loss" in history[0]["history"][0]
    assert len(json.loads((out / "metadata.json").read_text())["runs"]) == 1


def test_notebook_is_valid_and_unexecuted():
    import ast
    import nbformat
    notebook = nbformat.read(ROOT / "notebooks/4_1b_gcn_tuning.ipynb", as_version=4)
    nbformat.validate(notebook)
    sources=[]
    for cell in notebook.cells:
        if cell.cell_type == "code":
            assert cell.execution_count is None and not cell.outputs
            ast.parse(cell.source)
            sources.append(cell.source)
    text = "\n".join(sources)
    assert "RUN_TUNING = False" in text and "RUN_FINAL_TEST = False" in text
    assert "--validation-only" in text and "--frozen-selection" in text
    assert "scripts/train_gnn.py" in text
    assert "APPROVED_COMMIT" in text and "--detach" in text
    assert "class GCN" not in text and "def run_training" not in text


def test_freeze_ties_prefer_baseline_and_require_complete_seeds(monkeypatch, processed, tmp_path):
    directories = synthetic_candidates(monkeypatch, processed, tmp_path, equal_scores=True)
    frozen = tuning.freeze_winner(list(reversed(directories)), tmp_path / "tie.json")
    assert frozen["winner"]["config_id"] == "B0"
    path = directories[0] / "results.csv"
    lines = path.read_text().splitlines()
    path.write_text("\n".join(lines[:-1]) + "\n")
    meta_path = directories[0] / "metadata.json"
    meta = json.loads(meta_path.read_text())
    meta["artifacts_sha256"]["results.csv"] = tuning.digest(path)
    meta_path.write_text(json.dumps(meta))
    with pytest.raises(ValueError, match="Incomplete"):
        tuning.freeze_winner(directories, tmp_path / "incomplete.json")



def test_relocated_frozen_winner_missing_checkpoints_and_final_reuse(monkeypatch, processed, tmp_path):
    import shutil
    original = tmp_path / "original"
    original.mkdir()
    directories = synthetic_candidates(monkeypatch, processed, original)
    frozen_path = original / "frozen_selection.json"
    frozen = tuning.freeze_winner(directories, frozen_path)
    assert not Path(frozen["winner"]["directory"]).is_absolute()
    relocated = tmp_path / "mounted_output"
    shutil.move(str(original), relocated)
    manifest = relocated / "frozen_selection.json"
    loaded = tuning.read_frozen(manifest, ROOT, processed, ROOT / "configs/graph/schema_spec.yaml")
    assert loaded == frozen
    # Manifest can also be copied separately with an explicit portable root.
    separate = tmp_path / "selection.json"
    shutil.copyfile(manifest, separate)
    tuning.read_frozen(separate, ROOT, processed, ROOT / "configs/graph/schema_spec.yaml", relocated)
    run = frozen["winner"]["metadata"]["runs"][0]
    cp = tuning.checkpoint_path(frozen, run, relocated)
    old = cp.read_bytes()
    cp.unlink()
    with pytest.raises(FileNotFoundError, match="Missing artifact"):
        tuning.read_frozen(manifest, ROOT, processed, ROOT / "configs/graph/schema_spec.yaml")
    cp.write_bytes(old)
    hashes = {p.name: tuning.digest(p) for p in (relocated / frozen["winner"]["directory"]).glob("*.pt")}
    for protocol in tuning.PROTOCOLS:
        torch.save([graph(0), graph(1)], processed / protocol / "graph_a_test.pt")
    monkeypatch.setattr(cli, "run_training", lambda *a, **k: pytest.fail("Must not retrain"))
    output = tmp_path / "final"
    call_cli(monkeypatch, processed, output, "--frozen-selection", str(separate), "--results-root", str(relocated))
    tuning.validate_final(output, separate, ROOT, processed, ROOT / "configs/graph/schema_spec.yaml", relocated)
    second = tmp_path / "second_final"
    call_cli(monkeypatch, processed, second, "--frozen-selection", str(separate), "--results-root", str(relocated))
    assert (output / "results.csv").read_bytes() == (second / "results.csv").read_bytes()
    assert hashes == {p.name: tuning.digest(p) for p in (relocated / frozen["winner"]["directory"]).glob("*.pt")}
    assert json.loads(manifest.read_text()) == frozen


def test_reuse_rejects_partial_or_inconsistent_artifacts(monkeypatch, processed, tmp_path):
    directories = synthetic_candidates(monkeypatch, processed, tmp_path)
    folder = directories[0]
    tuning.reuse_candidate(folder, "B0", ROOT, processed, ROOT / "configs/graph/schema_spec.yaml", "unspecified")
    before = {p.name: tuning.digest(p) for p in folder.iterdir()}
    with pytest.raises(ValueError, match="Configuration"):
        tuning.reuse_candidate(folder, "H1", ROOT, processed, ROOT / "configs/graph/schema_spec.yaml", "unspecified")
    assert before == {p.name: tuning.digest(p) for p in folder.iterdir()}
    (folder / "summary.md").write_text("truncated")
    with pytest.raises(ValueError, match="hash"):
        tuning.validate_candidate(folder)
    metadata_path = folder / "metadata.json"
    meta = json.loads(metadata_path.read_text())
    meta.pop("artifacts_sha256")
    metadata_path.write_text(json.dumps(meta))
    with pytest.raises(ValueError, match="Incomplete"):
        tuning.freeze_winner(directories, tmp_path / "selection.json")


def test_frozen_identity_and_path_checks(monkeypatch, processed, tmp_path):
    directories = synthetic_candidates(monkeypatch, processed, tmp_path)
    manifest = tmp_path / "selection.json"
    frozen = tuning.freeze_winner(directories, manifest)
    original = manifest.read_bytes()
    frozen["winner"]["config_id"] = "B0"
    manifest.write_text(json.dumps(frozen))
    with pytest.raises(ValueError, match="metadata"):
        tuning.read_frozen(manifest, ROOT, processed, ROOT / "configs/graph/schema_spec.yaml")
    manifest.write_bytes(original)
    with pytest.raises(FileExistsError):
        tuning.freeze_winner(list(reversed(directories)), manifest)
    assert manifest.read_bytes() == original
    with pytest.raises(ValueError, match="escapes"):
        tuning.checked_path(tmp_path, "../outside.pt")


def notebook_code(needle):
    nb = json.loads((ROOT / "notebooks/4_1b_gcn_tuning.ipynb").read_text(encoding="utf-8"))
    return next("".join(c["source"]) for c in nb["cells"]
                if c["cell_type"] == "code" and needle in "".join(c["source"]))


def test_notebook_all_stages_disabled_is_clean(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Disabled stages must not access Git, GPU, data or subprocesses")
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "check_output", forbidden)
    nb = json.loads((ROOT / "notebooks/4_1b_gcn_tuning.ipynb").read_text(encoding="utf-8"))
    namespace = {}
    for cell in nb["cells"]:
        if cell["cell_type"] == "code":
            exec(compile("".join(cell["source"]), "<notebook>", "exec"), namespace)
    assert not namespace["ACTIVE"]


def test_notebook_tuning_recovery_and_separate_final_only(monkeypatch, processed, tmp_path):
    directories = synthetic_candidates(monkeypatch, processed, tmp_path)
    schema = ROOT / "configs/graph/schema_spec.yaml"
    namespace = {name: getattr(tuning, name) for name in (
        "configuration", "code_identity", "environment", "HYPOTHESES", "PROTOCOLS", "SEEDS",
        "reuse_candidate", "read_frozen", "validate_context", "freeze_winner", "validate_final")}
    namespace.update(dict(RUN_TUNING=True, RUN_FINAL_TEST=False, OUT_DIR=tmp_path, READ_ROOT=tmp_path,
        APPROVED_CONFIG_IDS=["B0", "H1"], PROCESSED=processed, REPO_DIR=ROOT, DATASET_ID="unspecified",
        json=json, run_script=lambda *a, **k: pytest.fail("Completed configurations must be reused")))
    exec(notebook_code('OUT_DIR.mkdir'), namespace)
    exec(notebook_code('FROZEN_ROOT ='), namespace)
    manifest = tmp_path / "frozen_selection.json"
    original = manifest.read_bytes()
    exec(notebook_code('OUT_DIR.mkdir'), namespace)
    exec(notebook_code('FROZEN_ROOT ='), namespace)
    assert manifest.read_bytes() == original
    exec(notebook_code('if FINAL_OUT_DIR.exists()'), namespace)
    # Simulate a fresh session with a different mounted results root.
    import shutil
    relocated = tmp_path.parent / (tmp_path.name + "_relocated")
    shutil.move(str(tmp_path), relocated)
    moved_processed = relocated / "processed"
    for protocol in tuning.PROTOCOLS:
        torch.save([graph(0), graph(1)], moved_processed / protocol / "graph_a_test.pt")
    namespace.update(RUN_TUNING=False, RUN_FINAL_TEST=True, READ_ROOT=relocated, PROCESSED=moved_processed,
                     FINAL_OUT_DIR=relocated / "final_output")
    exec(notebook_code('OUT_DIR.mkdir'), namespace)
    exec(notebook_code('FROZEN_ROOT ='), namespace)
    def evaluate(arguments, *unused):
        assert "--frozen-selection" in arguments and "--results-root" in arguments
        monkeypatch.setattr(sys, "argv", ["train_gnn.py", *arguments])
        cli.main()
    namespace["run_script"] = evaluate
    exec(notebook_code('if FINAL_OUT_DIR.exists()'), namespace)
    namespace["run_script"] = lambda *a, **k: pytest.fail("Valid final results must be reused")
    exec(notebook_code('if FINAL_OUT_DIR.exists()'), namespace)
    assert (relocated / "frozen_selection.json").read_bytes() == original


def test_notebook_recovers_completed_configs_from_saved_mount(monkeypatch, processed, tmp_path):
    import shutil
    saved = tmp_path / "saved_output"
    saved.mkdir()
    directories = synthetic_candidates(monkeypatch, processed, saved)
    manifest = saved / "frozen_selection.json"
    tuning.freeze_winner(directories, manifest)
    original = manifest.read_bytes()
    recovered = tmp_path / "new_session_output"
    namespace = {name: getattr(tuning, name) for name in (
        "configuration", "code_identity", "environment", "HYPOTHESES", "PROTOCOLS", "SEEDS",
        "reuse_candidate", "read_frozen", "validate_context", "freeze_winner")}
    namespace.update(dict(RUN_TUNING=True, RUN_FINAL_TEST=False, OUT_DIR=recovered, READ_ROOT=saved,
        APPROVED_CONFIG_IDS=["B0", "H1"], PROCESSED=processed, REPO_DIR=ROOT, DATASET_ID="unspecified",
        json=json, shutil=shutil, run_script=lambda *a, **k: pytest.fail("Must reuse saved configurations")))
    exec(notebook_code('OUT_DIR.mkdir'), namespace)
    exec(notebook_code('FROZEN_ROOT ='), namespace)
    assert (recovered / "frozen_selection.json").read_bytes() == original
    for key in ("B0", "H1"):
        assert tuning.validate_candidate(recovered / key) == tuning.validate_candidate(saved / key)
    # Repeating recovery is verification only, not a new freeze or overwrite.
    before = {str(p.relative_to(recovered)): tuning.digest(p) for p in recovered.rglob("*") if p.is_file()}
    exec(notebook_code('OUT_DIR.mkdir'), namespace)
    exec(notebook_code('FROZEN_ROOT ='), namespace)
    assert before == {str(p.relative_to(recovered)): tuning.digest(p) for p in recovered.rglob("*") if p.is_file()}



def test_notebook_requires_only_shared_training_pipeline():
    import ast
    notebook = json.loads((ROOT / "notebooks/4_1b_gcn_tuning.ipynb").read_text(encoding="utf-8"))
    source = "\n".join("".join(c["source"]) for c in notebook["cells"] if c["cell_type"] == "code")
    assert "preflight" not in source.lower()
    assert "torch.ones(1, device=\"cuda\")" in source
    assert "load_schema" in source and "train_ids_sha256" in source and "n_valid_samples" in source
    assert '"scripts/train_gnn.py"' in source
    for relative in ("scripts/train_gnn.py", "src/training/gnn_trainer.py", "src/training/gcn_tuning.py"):
        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert "preflight" not in (node.module or "")
            if isinstance(node, ast.Import):
                assert all("preflight" not in item.name for item in node.names)

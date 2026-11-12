"""Controlled GNN configurations and validation-only winner selection.

Used by 4.1b (GCN on Graph A) and 4.2 (GGNN on Graph B). The scope ``(model, graph)``
selects which experiment is validated; the default keeps the 4.1b behaviour.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
import subprocess
from pathlib import Path
from statistics import mean

import torch

BASELINE = dict(dim=128, num_layers=3, dropout=0.2, lr=1e-3, weight_decay=1e-4,
                batch_size=32, max_epochs=40, patience=8, max_nodes=None,
                early_stopping="macro_f1")
CANDIDATES = {
    "B0": {}, "E1": {"early_stopping": "val_loss"}, "D1": {"dropout": 0.4},
    "W1": {"weight_decay": 1e-3}, "H1": {"dim": 64},
    "L1": {"num_layers": 2}, "N1": {"max_nodes": 1000},
}
HYPOTHESES = {
    "B0": "Reproduce the official default in the tuning environment.",
    "E1": "Validation-loss stopping may be less sensitive to noisy Macro-F1 fluctuations.",
    "D1": "More dropout may reduce early overfitting.",
    "W1": "Stronger weight decay may improve generalization.",
    "H1": "Smaller hidden dimension may reduce memorization.",
    "L1": "Two GCN layers may reduce excessive propagation and model capacity.",
    "N1": "A 1000-node cap tests sensitivity to large graphs and aggregation cost.",
}
ARTIFACTS = ("results.csv", "per_class.csv", "confusion_matrices.json", "training_history.json", "summary.md")
GGNN_HYPOTHESES = {
    "B0": "Reproduce the official default in the tuning environment.",
    "E1": "Validation-loss stopping may be less sensitive to noisy Macro-F1 fluctuations.",
    "D1": "More dropout may reduce the early overfitting seen in the default GGNN.",
    "W1": "Stronger weight decay may improve generalization.",
    "H1": "Smaller hidden dimension may reduce memorization and VRAM on Graph B.",
    "L1": "Two propagation steps may reduce over-smoothing and cost on the larger Graph B.",
    "N1": "A 1000-node cap bounds Graph B cost; it truncates the oversized graphs.",
}
GCN_A = ("gcn", "graph_a")  # scope of task 4.1b
GGNN_B = ("ggnn", "graph_b")  # scope of task 4.2
PROTOCOLS = ("project_wise", "seen_project")
SEEDS = (42, 43, 44)


def configuration(config_id: str) -> dict:
    return {**BASELINE, **CANDIDATES[config_id]}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def code_identity(root: Path) -> dict:
    def git(*args):
        return subprocess.check_output(["git", "-C", str(root), *args], text=True, encoding="utf-8").strip()
    return {"commit": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain")),
            "source_sha256": {p: digest(root / p) for p in (
                "src/models/gnn.py", "src/training/gnn_trainer.py",
                "src/training/gcn_tuning.py", "src/evaluation/metrics.py", "scripts/train_gnn.py")}}


def environment() -> dict:
    import numpy
    import sklearn
    return {"python": platform.python_version(), "torch": str(torch.__version__),
            "numpy": numpy.__version__, "sklearn": sklearn.__version__,
            "cuda": torch.version.cuda,
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}


def data_identity(processed_dir: Path, protocol: str, graph: str) -> dict:
    # Never open test tensors during tuning. Pin dataset metadata and tuning inputs.
    paths = [f"{protocol}/vocab.json", f"{protocol}/{graph}_train.pt",
             f"{protocol}/{graph}_validation.pt"]
    paths += [p for p in ("metadata.json", f"{protocol}/manifest.csv")
              if (processed_dir / p).is_file()]
    return {p: digest(processed_dir / p) for p in paths}


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def checked_path(root: Path, relative: str) -> Path:
    """Resolve portable paths without allowing absolute paths or escaping the root."""
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(root):
        raise ValueError(f"Artifact path escapes results root: {relative}")
    if not path.is_file():
        raise FileNotFoundError(f"Missing artifact: {path}")
    return path


def validate_artifacts(directory: Path) -> dict:
    """A final metadata write binds all outputs; partial configurations are rejected."""
    directory = Path(directory)
    try:
        meta = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Missing or incomplete metadata in {directory}") from exc
    hashes = meta.get("artifacts_sha256", {})
    if set(hashes) != set(ARTIFACTS):
        raise ValueError(f"Incomplete artifacts in {directory}; preserve this directory for inspection")
    for name in ARTIFACTS:
        if digest(checked_path(directory, name)) != hashes[name]:
            raise ValueError(f"Artifact hash mismatch: {directory / name}")
    return meta


def validate_candidate(directory: Path, scope: tuple[str, str] = GCN_A) -> dict:
    model, graph = scope
    directory = Path(directory)
    meta = validate_artifacts(directory)
    args = meta["arguments"]
    config_id = args["config_id"]
    if config_id not in CANDIDATES or any(args[k] != v for k, v in configuration(config_id).items()):
        raise ValueError("Candidate must change exactly its declared baseline factor")
    if (not args["validation_only"] or args["limit"] is not None or args["frozen_selection"]
            or args["graphs"] != [graph] or args["models"] != [model]
            or args["seeds"] != list(SEEDS) or args["protocols"] != list(PROTOCOLS)):
        raise ValueError("Freeze requires complete validation-only experiments for the declared model and graph")
    with (directory / "results.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    expected = {(p, str(s)) for p in PROTOCOLS for s in SEEDS}
    if (len(rows) != 6 or {(r["protocol"], r["seed"]) for r in rows} != expected
            or any(r["split"] != "validation" or r["graph"] != graph or r["model"] != model for r in rows)):
        raise ValueError("Incomplete validation results or test contamination")
    if not all(math.isfinite(float(row["macro_f1"])) for row in rows):
        raise ValueError("Non-finite validation score")
    runs = meta["runs"]
    if len(runs) != 6 or {(r["protocol"], str(r["seed"])) for r in runs} != expected:
        raise ValueError("Missing candidate checkpoints")
    histories = json.loads((directory / "training_history.json").read_text(encoding="utf-8"))
    expected_tags = {f"{p}|{graph}|{model}|{s}" for p in PROTOCOLS for s in SEEDS}
    if len(histories) != 6 or {h["tag"] for h in histories} != expected_tags:
        raise ValueError("Incomplete training histories")
    with (directory / "per_class.csv").open(encoding="utf-8", newline="") as handle:
        per_class = list(csv.DictReader(handle))
    for run in runs:
        checkpoint = checked_path(directory, run["checkpoint"])
        if digest(checkpoint) != run["sha256"]:
            raise ValueError("Checkpoint hash mismatch")
        payload = torch.load(checkpoint, map_location="cpu", weights_only=True)
        row = next(r for r in rows if r["protocol"] == run["protocol"] and int(r["seed"]) == run["seed"])
        constructor = payload["constructor"]
        cfg = configuration(config_id)
        if (payload["configuration"] != cfg or payload["protocol"] != run["protocol"]
                or payload["seed"] != run["seed"] or set(payload["training"]["reports"]) != {"validation"}
                or constructor["kind"] != model or constructor["n_classes"] != len(payload["labels"])
                or any(constructor[k] != cfg[k] for k in ("dim", "num_layers", "dropout"))
                or payload["training"]["reports"]["validation"]["macro_f1"] != float(row["macro_f1"])
                or payload["training"]["best_epoch"] != int(row["best_epoch"])):
            raise ValueError("Validation results do not match saved checkpoint")
        tag = f"{run['protocol']}|{graph}|{model}|{run['seed']}"
        history = next(h["history"] for h in histories if h["tag"] == tag)
        if history != payload["training"]["history"] or len(history) != int(row["epochs_run"]):
            raise ValueError("Training history differs from checkpoint")
        classes = [c for c in per_class if c["protocol"] == run["protocol"] and int(c["seed"]) == run["seed"]]
        if (len(per_class) != 6 * len(payload["labels"]) or len(classes) != len(payload["labels"]) or {c["cwe"] for c in classes} != set(payload["labels"])
                or any(c["split"] != "validation" or c["graph"] != graph or c["model"] != model for c in classes)):
            raise ValueError("Incomplete per-class results")
    return meta


def validate_context(meta: dict, root: Path, processed_dir: Path, schema: Path,
                     dataset_id: str | None = None, scope: tuple[str, str] = GCN_A) -> None:
    if meta["code"] != code_identity(root) or meta["schema_sha256"] != digest(schema):
        raise ValueError("Code or schema differs from saved experiment")
    if dataset_id is not None and meta["arguments"]["dataset_id"] != dataset_id:
        raise ValueError("Dataset version differs from saved experiment")
    for protocol in PROTOCOLS:
        if meta["inputs"][protocol] != data_identity(processed_dir, protocol, scope[1]):
            raise ValueError("Dataset differs from saved experiment")


def reuse_candidate(directory: Path, config_id: str, root: Path, processed_dir: Path,
                    schema: Path, dataset_id: str, scope: tuple[str, str] = GCN_A) -> dict:
    meta = validate_candidate(directory, scope)
    validate_context(meta, root, processed_dir, schema, dataset_id, scope)
    if meta["arguments"]["config_id"] != config_id or meta["environment"] != environment():
        raise ValueError("Configuration or training environment differs from saved experiment")
    return meta


def checkpoint_path(frozen: dict, run: dict, results_root: Path) -> Path:
    return checked_path(results_root, str(Path(frozen["winner"]["directory"]) / run["checkpoint"]))


def freeze_winner(candidate_dirs: list[Path], destination: Path, scope: tuple[str, str] = GCN_A) -> dict:
    """Freeze validation-only results with paths relative to the manifest directory."""
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError(destination)
    candidates, identities = [], []
    for directory in candidate_dirs:
        directory = Path(directory).resolve()
        meta = validate_candidate(directory, scope)
        args = meta["arguments"]
        identities.append((meta["code"], meta["inputs"], meta["environment"], meta["schema_sha256"], args["dataset_id"]))
        with (directory / "results.csv").open(encoding="utf-8", newline="") as handle:
            values = [float(r["macro_f1"]) for r in csv.DictReader(handle) if r["protocol"] == "project_wise"]
        relative = directory.relative_to(destination.parent.resolve()).as_posix()
        candidates.append(dict(config_id=args["config_id"], score=mean(values), directory=relative, metadata=meta))
    if not candidates or len({c["config_id"] for c in candidates}) != len(candidates):
        raise ValueError("Need distinct complete candidates")
    if any(identity != identities[0] for identity in identities[1:]):
        raise ValueError("Candidates differ in code, data, schema, environment or dataset version")
    ranked = sorted(candidates, key=lambda c: (-c["score"], list(CANDIDATES).index(c["config_id"])))
    frozen = {"format_version": 2, "selection_metric": "project_wise.validation.macro_f1.mean",
              "winner": ranked[0], "ranking": [{k: c[k] for k in ("config_id", "score")} for c in ranked]}
    # Exclusive creation prevents a different selection replacing an existing manifest.
    with destination.open("x", encoding="utf-8") as handle:
        json.dump(frozen, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
    return frozen


def read_frozen(path: Path, root: Path, processed_dir: Path, schema: Path,
                results_root: Path | None = None, scope: tuple[str, str] | None = None) -> dict:
    """Verify a frozen winner. ``scope`` defaults to the winner's own single model and graph."""
    path = Path(path)
    frozen = json.loads(path.read_text(encoding="utf-8"))
    if frozen["format_version"] != 2 or frozen["selection_metric"] != "project_wise.validation.macro_f1.mean":
        raise ValueError("Unsupported frozen selection; expected portable format 2")
    winner = frozen["winner"]
    results_root = Path(results_root) if results_root else path.parent
    meta = winner["metadata"]
    if scope is None:
        models, graphs = meta["arguments"]["models"], meta["arguments"]["graphs"]
        if len(models) != 1 or len(graphs) != 1:
            raise ValueError("Frozen winner must declare exactly one model and one graph")
        scope = (models[0], graphs[0])
    validate_context(meta, root, processed_dir, schema, scope=scope)
    # Verify the stored winner, never reselect using new candidates or test metrics.
    directory = checked_path(results_root, str(Path(winner["directory"]) / "metadata.json")).parent
    saved = validate_candidate(directory, scope)
    if saved != meta or winner["config_id"] != meta["arguments"]["config_id"]:
        raise ValueError("Frozen winner metadata differs from saved configuration")
    with (directory / "results.csv").open(encoding="utf-8", newline="") as handle:
        score = mean(float(r["macro_f1"]) for r in csv.DictReader(handle) if r["protocol"] == "project_wise")
    ranking = frozen["ranking"]
    if (winner["score"] != score or not ranking or ranking[0] != {"config_id": winner["config_id"], "score": score}
            or len({r["config_id"] for r in ranking}) != len(ranking)
            or ranking != sorted(ranking, key=lambda r: (-r["score"], list(CANDIDATES).index(r["config_id"])))):
        raise ValueError("Frozen winner is inconsistent with validation ranking")
    return frozen


def sensitivity_target(frozen: dict, config_id: str, root: Path, processed_dir: Path,
                       schema: Path, results_root: Path) -> dict:
    """Return a non-winning candidate for a post-selection test sensitivity analysis.

    Only configurations ranked in an already frozen selection are accepted, so test
    scores can never influence which configuration is reported as the tuned result.
    """
    winner = frozen["winner"]
    if config_id not in {r["config_id"] for r in frozen["ranking"]}:
        raise ValueError(f"Configuration {config_id} is not part of the frozen ranking")
    arguments = winner["metadata"]["arguments"]
    scope = (arguments["models"][0], arguments["graphs"][0])
    relative = (Path(winner["directory"]).parent / config_id).as_posix()
    directory = checked_path(results_root, f"{relative}/metadata.json").parent
    meta = validate_candidate(directory, scope)
    validate_context(meta, root, processed_dir, schema, arguments["dataset_id"], scope)
    if meta["arguments"]["config_id"] != config_id:
        raise ValueError("Candidate directory holds a different configuration")
    return {"config_id": config_id, "directory": relative, "metadata": meta}


def validate_final(directory: Path, frozen_path: Path, root: Path, processed_dir: Path,
                   schema: Path, results_root: Path | None = None, scope: tuple[str, str] = GCN_A) -> dict:
    model, graph = scope
    frozen = read_frozen(frozen_path, root, processed_dir, schema, results_root, scope)
    meta = validate_artifacts(directory)
    validate_context(meta, root, processed_dir, schema, scope=scope)
    args = meta["arguments"]
    cfg = configuration(frozen["winner"]["config_id"])
    if (meta.get("frozen_selection_sha256") != digest(frozen_path)
            or args["config_id"] != frozen["winner"]["config_id"]
            or any(args[k] != v for k, v in cfg.items())):
        raise ValueError("Final results refer to a different frozen selection")
    with (Path(directory) / "results.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if (len(rows) != 6 or {(r["protocol"], int(r["seed"])) for r in rows} !=
            {(p, s) for p in PROTOCOLS for s in SEEDS}
            or any(r["split"] != "test" or r["model"] != model or r["graph"] != graph for r in rows)):
        raise ValueError("Incomplete final test results")
    for protocol in PROTOCOLS:
        if meta["test_sha256"][protocol] != digest(processed_dir / protocol / f"{graph}_test.pt"):
            raise ValueError("Test inputs differ from saved final evaluation")
    return meta

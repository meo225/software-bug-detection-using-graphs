"""Config không phụ thuộc riêng một dataset và không giả định EDA đã hoàn tất."""

from pathlib import Path

import pytest

pytest.importorskip("yaml")

from src.utils.config import load_config
from src.utils.paths import repo_root


def test_diversevul_config_is_still_a_candidate() -> None:
    config = load_config(repo_root() / "configs" / "data" / "diversevul.yaml")
    dataset = config["dataset"]
    assert dataset["name"] == "diversevul"
    assert dataset["status"] == "candidate"
    assert dataset["version"] is None


def test_other_dataset_configs_exist() -> None:
    data_dir = repo_root() / "configs" / "data"
    names = sorted(path.stem for path in data_dir.glob("*.yaml"))
    assert names == ["bigvul", "diversevul", "megavul", "primevul"]
    megavul = load_config(data_dir / "megavul.yaml")["dataset"]
    assert megavul["status"] == "candidate"
    assert megavul["code_field"] == "func_before"


def test_experiment_does_not_select_cwe_or_split() -> None:
    config = load_config(repo_root() / "configs" / "experiment" / "baseline.yaml")
    experiment = config["experiment"]
    assert experiment["selected_cwe_classes"] is None
    assert experiment["multi_cwe_policy"] is None
    assert experiment["split"]["strategy"] is None
    assert "macro_f1" in experiment["metrics"]
    assert "accuracy" in experiment["metrics"]


def test_cpg_config_is_a_candidate() -> None:
    config = load_config(repo_root() / "configs" / "graph" / "cpg.yaml")
    assert config["graph"]["status"] == "candidate"
    assert "cpg" in config["graph"]["candidates"]
    assert "ast" in config["graph"]["candidates"]

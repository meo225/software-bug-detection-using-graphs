"""Kiểm thử cho Task 4.5: tập văn bản, cắt đoạn, pooling và vòng fine-tune."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch
from torch import nn

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import train_text as cli  # noqa: E402
from src.data import text_dataset as td  # noqa: E402
from src.models.text_encoder import (  # noqa: E402
    ChunkedTextClassifier, chunk_token_ids, collate_text, length_statistics, pool_chunks,
    tokenize_samples,
)
from src.training import text_experiments as tx  # noqa: E402
from src.training.run_artifacts import plain, summary_lines, write_csv  # noqa: E402
from src.training.text_trainer import linear_schedule, parameter_groups, run_text_training  # noqa: E402

CLS, SEP, PAD = 0, 2, 1


class StubTokenizer:
    """Tách theo khoảng trắng, mỗi từ một id, đủ để kiểm thử mà không cần mạng."""

    cls_token_id, sep_token_id, pad_token_id = CLS, SEP, PAD

    def __call__(self, text, add_special_tokens=False, truncation=False):
        words = text.split()
        return {"input_ids": [10 + (hash(w) % 40) for w in words]}


class StubEncoder(nn.Module):
    """Encoder nhỏ: mỗi đoạn cho một vector phụ thuộc token thật trong đoạn."""

    def __init__(self, hidden: int = 8, vocab: int = 64) -> None:
        super().__init__()
        self.config = SimpleNamespace(hidden_size=hidden)
        self.embedding = nn.Embedding(vocab, hidden)

    def forward(self, input_ids, attention_mask):
        weights = attention_mask.unsqueeze(-1).to(self.embedding.weight.dtype)
        pooled = (self.embedding(input_ids) * weights).sum(1) / weights.sum(1).clamp(min=1)
        return SimpleNamespace(last_hidden_state=pooled.unsqueeze(1).expand(-1, input_ids.shape[1], -1))


def sample(index: int, words: int, label: int) -> dict:
    return {"sample_id": f"row-{index}", "func": " ".join(f"tok{index}_{i}" for i in range(words)),
            "cwe": f"CWE-{label}", "y": label,
            "project_wise": "train", "seen_project": "train"}


# --- cắt đoạn -------------------------------------------------------------

def test_chunk_splits_on_the_window_and_adds_special_tokens():
    chunks, used = chunk_token_ids(list(range(10, 19)), max_length=5, max_chunks=3, cls_id=CLS, sep_id=SEP)
    assert chunks == [[CLS, 10, 11, 12, SEP], [CLS, 13, 14, 15, SEP], [CLS, 16, 17, 18, SEP]]
    assert used == 9


def test_chunk_reports_tokens_dropped_beyond_max_chunks():
    chunks, used = chunk_token_ids(list(range(10, 20)), max_length=5, max_chunks=2, cls_id=CLS, sep_id=SEP)
    assert len(chunks) == 2 and used == 6  # 10 token thân, chỉ giữ 6


def test_chunk_one_chunk_is_plain_truncation():
    chunks, used = chunk_token_ids(list(range(100)), max_length=12, max_chunks=1, cls_id=CLS, sep_id=SEP)
    assert len(chunks) == 1 and len(chunks[0]) == 12 and used == 10


def test_chunk_handles_empty_body():
    assert chunk_token_ids([], 8, 2, CLS, SEP) == ([[CLS, SEP]], 0)


@pytest.mark.parametrize("length,chunks", [(2, 2), (8, 0), (8, -1)])
def test_chunk_rejects_impossible_arguments(length, chunks):
    with pytest.raises(ValueError):
        chunk_token_ids([1, 2], length, chunks, CLS, SEP)


def test_tokenize_samples_records_length_and_coverage():
    encoded = tokenize_samples([sample(1, 9, 0)], StubTokenizer(), max_length=5, max_chunks=2)
    assert encoded[0]["n_body_tokens"] == 9
    assert encoded[0]["n_used_tokens"] == 6
    assert encoded[0]["sample_id"] == "row-1"  # mẫu gốc được giữ nguyên


def test_tokenize_rejects_tokenizer_without_special_tokens():
    broken = StubTokenizer()
    broken.cls_token_id = None
    with pytest.raises(ValueError):
        tokenize_samples([sample(1, 3, 0)], broken, 8, 2)


# --- gộp batch và pooling -------------------------------------------------

def test_collate_pads_to_the_largest_item_in_the_batch_only():
    batch = collate_text([{"chunks": [[CLS, 9, SEP]], "y": 1},
                          {"chunks": [[CLS, 9, 9, SEP], [CLS, 9, SEP]], "y": 2}], PAD)
    assert batch["input_ids"].shape == (2, 2, 4)
    assert batch["chunk_mask"].tolist() == [[True, False], [True, True]]
    assert batch["attention_mask"][0, 0].tolist() == [1, 1, 1, 0]
    assert batch["attention_mask"][0, 1].tolist() == [0, 0, 0, 0]
    assert batch["input_ids"][0, 1].tolist() == [PAD] * 4
    assert batch["y"].tolist() == [1, 2]


def test_max_pooling_ignores_padded_chunks():
    hidden = torch.tensor([[[1.0, 5.0], [9.0, 9.0]]])
    mask = torch.tensor([[True, False]])
    assert pool_chunks(hidden, mask, "max").tolist() == [[1.0, 5.0]]


def test_mean_pooling_divides_by_valid_chunks_only():
    hidden = torch.tensor([[[2.0], [4.0], [0.0]]])
    mask = torch.tensor([[True, True, False]])
    assert pool_chunks(hidden, mask, "mean").tolist() == [[3.0]]


def test_first_pooling_takes_chunk_zero():
    hidden = torch.tensor([[[7.0], [1.0]]])
    assert pool_chunks(hidden, torch.tensor([[True, True]]), "first").tolist() == [[7.0]]


def test_pooling_rejects_unknown_name():
    with pytest.raises(ValueError):
        pool_chunks(torch.zeros(1, 1, 1), torch.ones(1, 1, dtype=torch.bool), "sum")


def test_padding_a_short_sample_does_not_change_its_prediction():
    """Mẫu một đoạn phải cho cùng logits dù batch có mẫu hai đoạn hay không."""
    torch.manual_seed(0)
    model = ChunkedTextClassifier(StubEncoder(), n_classes=3, dropout=0.0).eval()
    short = {"chunks": [[CLS, 11, 12, SEP]], "y": 0}
    long = {"chunks": [[CLS, 13, 14, SEP], [CLS, 15, SEP]], "y": 1}
    with torch.no_grad():
        alone = model(collate_text([short], PAD))
        mixed = model(collate_text([short, long], PAD))
    assert torch.allclose(alone[0], mixed[0], atol=1e-6)


def test_classifier_rejects_unknown_pooling():
    with pytest.raises(ValueError):
        ChunkedTextClassifier(StubEncoder(), 3, pooling="sum")


def test_length_statistics_reports_truncation_share():
    encoded = tokenize_samples([sample(i, n, 0) for i, n in enumerate([1, 5, 50])],
                               StubTokenizer(), max_length=5, max_chunks=2)
    stats = length_statistics(encoded, 5, 2)
    assert stats["capacity_tokens"] == 6
    assert stats["max_tokens"] == 50
    assert stats["share_over_one_chunk"] == pytest.approx(2 / 3)  # 5 và 50 vượt một đoạn
    assert stats["share_truncated"] == pytest.approx(1 / 3)  # chỉ 50 vượt sức chứa
    assert stats["token_coverage"] == pytest.approx((1 + 5 + 6) / 56)


# --- tập dữ liệu ----------------------------------------------------------

def test_dataset_roundtrip(tmp_path):
    path = tmp_path / "text.jsonl.gz"
    written = td.write_text_dataset(path, [sample(1, 3, 0), sample(2, 4, 1)])
    loaded = td.load_text_dataset(path, n_classes=23)
    assert written == 2 and [s["sample_id"] for s in loaded] == ["row-1", "row-2"]
    assert set(loaded[0]) == set(td.FIELDS)


def test_dataset_write_is_reproducible(tmp_path):
    first, second = tmp_path / "a.jsonl.gz", tmp_path / "b.jsonl.gz"
    for path in (first, second):
        td.write_text_dataset(path, [sample(1, 3, 0)])
    assert first.read_bytes() == second.read_bytes()


def test_dataset_rejects_duplicate_sample_id(tmp_path):
    path = tmp_path / "text.jsonl.gz"
    td.write_text_dataset(path, [sample(1, 3, 0), sample(1, 3, 1)])
    with pytest.raises(ValueError, match="lặp lại"):
        td.load_text_dataset(path)


def test_dataset_rejects_label_outside_range(tmp_path):
    path = tmp_path / "text.jsonl.gz"
    td.write_text_dataset(path, [sample(1, 3, 99)])
    with pytest.raises(ValueError, match="ngoài khoảng"):
        td.load_text_dataset(path, n_classes=23)


def test_dataset_rejects_empty_source(tmp_path):
    path = tmp_path / "text.jsonl.gz"
    td.write_text_dataset(path, [{**sample(1, 3, 0), "func": "   "}])
    with pytest.raises(ValueError, match="không có mã nguồn"):
        td.load_text_dataset(path)


def test_write_rejects_missing_field(tmp_path):
    broken = {k: v for k, v in sample(1, 3, 0).items() if k != "cwe"}
    with pytest.raises(KeyError):
        td.write_text_dataset(tmp_path / "text.jsonl.gz", [broken])


def test_split_text_samples_keeps_file_order_and_drops_unknown_names():
    samples = [{**sample(i, 2, 0), "project_wise": name}
               for i, name in enumerate(["train", "test", "khác", "train"])]
    parts = td.split_text_samples(samples, "project_wise")
    assert [s["sample_id"] for s in parts["train"]] == ["row-0", "row-3"]
    assert len(parts["test"]) == 1 and parts["validation"] == []


def test_split_text_samples_rejects_unknown_protocol():
    with pytest.raises(ValueError):
        td.split_text_samples([], "random_split")


def test_check_split_sizes_flags_a_mismatch():
    problems = td.check_split_sizes([sample(1, 2, 0)])
    assert problems and any("project_wise/train" in p for p in problems)


def test_labels_follow_the_class_index():
    labels = td.labels_from_mapping({"CWE-b": 1, "CWE-a": 0})
    assert labels == ["CWE-a", "CWE-b"]


# --- cấu hình đã đăng ký --------------------------------------------------

def test_configuration_carries_the_hugging_face_name():
    assert tx.configuration()["model_name"] == "microsoft/codebert-base"
    assert tx.configuration("unixcoder")["model_name"] == "microsoft/unixcoder-base"


def test_configuration_rejects_unknown_model_and_override():
    with pytest.raises(ValueError):
        tx.configuration("gpt4")
    with pytest.raises(ValueError):
        tx.configuration(num_layers=3)


def test_arguments_cover_every_registered_hyperparameter():
    flags = set(tx.arguments())
    for name in tx.BASELINE:
        assert "--" + name.replace("_", "-") in flags


def test_registered_choices_follow_the_cited_papers():
    assert tx.BASELINE["max_length"] == 512 and tx.BASELINE["max_chunks"] == 2  # EMNLP 2024
    assert tx.BASELINE["lr"] == 2e-5 and tx.BASELINE["max_epochs"] == 10  # PrimeVul


def test_reference_results_read_the_committed_files_of_earlier_tasks():
    rows = tx.reference_results(ROOT)
    by_key = {(r["label"], r["protocol"]): r for r in rows}
    token = by_key[("token_nodes (4.1a)", "project_wise")]
    assert token["macro_f1"] == pytest.approx(0.1000, abs=5e-5) and token["n_seeds"] == 3
    assert ("GGNN-B tinh chỉnh (4.2)", "seen_project") in by_key


def test_reference_results_skip_files_that_do_not_exist(tmp_path):
    assert tx.reference_results(tmp_path) == []


# --- vòng huấn luyện ------------------------------------------------------

def test_linear_schedule_warms_up_then_decays_to_zero():
    values = [linear_schedule(step, 10, 0.2) for step in range(11)]
    assert values[0] < values[1] == pytest.approx(1.0)
    assert values[-1] == pytest.approx(0.0)
    assert all(a >= b for a, b in zip(values[2:], values[3:]))


def test_linear_schedule_handles_zero_warmup():
    assert linear_schedule(0, 4, 0.0) == pytest.approx(1.0)


def test_parameter_groups_exempt_bias_and_layer_norm():
    model = nn.Sequential(nn.Linear(4, 4), nn.LayerNorm(4))
    groups = parameter_groups(model, weight_decay=0.01)
    assert groups[0]["weight_decay"] == 0.01 and groups[1]["weight_decay"] == 0.0
    assert len(groups[0]["params"]) == 1  # chỉ ma trận trọng số của Linear
    assert len(groups[1]["params"]) == 3  # bias cộng weight và bias của LayerNorm


def test_run_text_training_returns_the_shared_result_contract():
    encoded = tokenize_samples([sample(i, 3 + i % 4, i % 3) for i in range(12)],
                               StubTokenizer(), max_length=6, max_chunks=2)
    out = run_text_training(encoded, encoded[:6], encoded[6:], lambda: StubEncoder(),
                            ["CWE-0", "CWE-1", "CWE-2"], seed=42, pad_id=PAD,
                            batch_size=4, max_epochs=2, patience=2, amp=False,
                            device=torch.device("cpu"), log=lambda _: None)
    assert set(out["reports"]) == {"validation", "test"}
    for key in ("best_epoch", "epochs_run", "n_params", "train_seconds", "history", "loss"):
        assert key in out
    assert out["epochs_run"] == 2 and out["loss"] == "weighted_ce"
    assert len(out["history"]) == 2 and "lr" in out["history"][0]


def test_run_text_training_can_skip_test():
    encoded = tokenize_samples([sample(i, 3, i % 2) for i in range(6)], StubTokenizer(), 6, 2)
    out = run_text_training(encoded, encoded, [], lambda: StubEncoder(), ["CWE-0", "CWE-1"],
                            seed=1, pad_id=PAD, batch_size=3, max_epochs=1, amp=False,
                            device=torch.device("cpu"), evaluate_test=False, log=lambda _: None)
    assert set(out["reports"]) == {"validation"}


def test_run_text_training_is_reproducible_for_one_seed():
    encoded = tokenize_samples([sample(i, 3 + i % 3, i % 2) for i in range(8)], StubTokenizer(), 6, 2)
    kwargs = dict(labels=["CWE-0", "CWE-1"], seed=7, pad_id=PAD, batch_size=4, max_epochs=2,
                  amp=False, device=torch.device("cpu"), log=lambda _: None)
    first = run_text_training(encoded, encoded, encoded, lambda: StubEncoder(), **kwargs)
    second = run_text_training(encoded, encoded, encoded, lambda: StubEncoder(), **kwargs)
    assert first["reports"]["test"]["macro_f1"] == second["reports"]["test"]["macro_f1"]


# --- tệp kết quả dùng chung ----------------------------------------------

def test_summary_lines_group_by_the_given_fields():
    rows = [{"protocol": "p", "model": "codebert", "split": "test", "macro_f1": 0.2,
             "weighted_f1": 0.3, "mcc": 0.1, "accuracy": 0.4, "n_params": 5, "train_seconds": 10.0},
            {"protocol": "p", "model": "codebert", "split": "test", "macro_f1": 0.4,
             "weighted_f1": 0.5, "mcc": 0.3, "accuracy": 0.6, "n_params": 5, "train_seconds": 20.0}]
    lines = summary_lines("# T", rows, ("protocol", "model", "split"))
    assert lines[4] == "| Protocol | Model | Split | Macro-F1 | Weighted-F1 | MCC | Accuracy | Tham số | Giây/seed |"
    assert "0.3000 ± 0.1000" in lines[-1] and lines[-1].endswith("| 5 | 15 |")


def test_summary_lines_match_the_format_committed_for_task_4_3():
    path = ROOT / "reports" / "graph" / "4_3_results" / "arms" / "C0"
    with (path / "results.csv").open(encoding="utf-8", newline="") as handle:
        rows = [{**r, **{k: float(r[k]) for k in
                         ("macro_f1", "weighted_f1", "mcc", "accuracy", "train_seconds")},
                 "n_params": int(r["n_params"])} for r in csv.DictReader(handle)]
    produced = summary_lines("# Kết quả GNN (Task 4.1a)", rows, ("protocol", "graph", "model", "split"))
    assert "\n".join(produced) + "\n" == (path / "summary.md").read_text(encoding="utf-8")


def test_write_csv_skips_empty_input(tmp_path):
    write_csv(tmp_path / "x.csv", [])
    assert not (tmp_path / "x.csv").exists()


def test_plain_serialises_paths():
    assert plain([Path("/a/b"), 3]) == ["/a/b", 3]


# --- chạy đầu cuối qua dòng lệnh -----------------------------------------

def write_tiny_dataset(path: Path, schema: Path) -> None:
    labels = ["CWE-0", "CWE-1", "CWE-2"]
    schema.write_text("cwe_mapping:\n" + "".join(f"  {c}: {i}\n" for i, c in enumerate(labels)),
                      encoding="utf-8")
    samples = []
    for index in range(18):
        name = ("train", "validation", "test")[index % 3]
        samples.append({**sample(index, 3 + index % 5, index % 3),
                        "cwe": labels[index % 3], "project_wise": name, "seen_project": name})
    td.write_text_dataset(path, samples)


def run_cli(tmp_path, monkeypatch, extra: list[str]) -> Path:
    dataset, schema, out = tmp_path / "t.jsonl.gz", tmp_path / "schema.yaml", tmp_path / "out"
    write_tiny_dataset(dataset, schema)
    monkeypatch.setattr(cli, "build_tokenizer", lambda *a, **k: StubTokenizer())
    monkeypatch.setattr(cli, "build_encoder", lambda *a, **k: StubEncoder())
    monkeypatch.setattr(sys, "argv", ["train_text.py", "--dataset", str(dataset), "--schema",
                                      str(schema), "--out-dir", str(out), "--max-length", "6",
                                      "--max-chunks", "2", "--max-epochs", "1", "--batch-size", "4",
                                      "--no-amp", *extra])
    assert cli.main() == 0
    return out


def test_cli_writes_every_shared_artifact(tmp_path, monkeypatch):
    out = run_cli(tmp_path, monkeypatch, ["--seeds", "42", "43"])
    for name in ("results.csv", "per_class.csv", "confusion_matrices.json",
                 "training_history.json", "summary.md", "metadata.json"):
        assert (out / name).is_file(), name
    with (out / "results.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert {(r["protocol"], r["seed"], r["split"]) for r in rows} == {
        (p, s, sp) for p in ("project_wise", "seen_project")
        for s in ("42", "43") for sp in ("validation", "test")}
    assert all(r["model"] == "codebert" and r["pooling"] == "max" for r in rows)


def test_cli_records_dataset_fingerprint_and_length_statistics(tmp_path, monkeypatch):
    out = run_cli(tmp_path, monkeypatch, ["--seeds", "42"])
    meta = json.loads((out / "metadata.json").read_text(encoding="utf-8"))
    inputs = meta["inputs"]
    assert len(inputs["dataset_sha256"]) == 64
    assert inputs["n_samples"] == 18
    assert inputs["length_statistics"]["capacity_tokens"] == 8
    assert inputs["split_size_problems"]  # tập nhỏ lệch khỏi Task 4.0, phải được ghi lại
    assert meta["artifacts_sha256"].keys()


def test_cli_validation_only_leaves_test_untouched(tmp_path, monkeypatch):
    out = run_cli(tmp_path, monkeypatch, ["--seeds", "42", "--validation-only"])
    with (out / "results.csv").open(encoding="utf-8", newline="") as handle:
        assert {r["split"] for r in csv.DictReader(handle)} == {"validation"}


def test_cli_refuses_to_overwrite_a_non_empty_directory(tmp_path, monkeypatch):
    out = run_cli(tmp_path, monkeypatch, ["--seeds", "42"])
    dataset, schema = tmp_path / "t.jsonl.gz", tmp_path / "schema.yaml"
    monkeypatch.setattr(sys, "argv", ["train_text.py", "--dataset", str(dataset), "--schema",
                                      str(schema), "--out-dir", str(out), "--no-amp"])
    with pytest.raises(FileExistsError):
        cli.main()


def test_validate_run_accepts_a_full_run_and_rejects_a_partial_one(tmp_path, monkeypatch):
    out = run_cli(tmp_path, monkeypatch, ["--seeds", "42", "43", "44"])
    overrides = {"max_length": 6, "max_chunks": 2, "max_epochs": 1, "batch_size": 4}
    tx.validate_run(out, **overrides)
    with pytest.raises(ValueError, match="Siêu tham số"):
        tx.validate_run(out, **{**overrides, "max_epochs": 10})
    meta = json.loads((out / "metadata.json").read_text(encoding="utf-8"))
    meta["arguments"]["seeds"] = [42, 43]
    (out / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(ValueError, match="ba seed"):
        tx.validate_run(out, **overrides)


def test_validate_run_rejects_a_shortened_run(tmp_path, monkeypatch):
    out = run_cli(tmp_path, monkeypatch, ["--seeds", "42", "43", "44", "--limit", "4"])
    with pytest.raises(ValueError, match="rút gọn"):
        tx.validate_run(out, max_length=6, max_chunks=2, max_epochs=1, batch_size=4)


# --- encoder thật ---------------------------------------------------------

def test_classifier_works_with_a_real_transformer_encoder():
    transformers = pytest.importorskip("transformers")
    config = transformers.RobertaConfig(vocab_size=60, hidden_size=16, num_hidden_layers=1,
                                        num_attention_heads=2, intermediate_size=32,
                                        max_position_embeddings=32)
    model = ChunkedTextClassifier(transformers.RobertaModel(config), n_classes=3, dropout=0.0).eval()
    batch = collate_text([{"chunks": [[CLS, 11, SEP]], "y": 0},
                          {"chunks": [[CLS, 12, 13, SEP], [CLS, 14, SEP]], "y": 1}], PAD)
    with torch.no_grad():
        logits = model(batch)
    assert logits.shape == (2, 3) and torch.isfinite(logits).all()


def test_parameter_groups_on_a_real_transformer_exempt_only_norms_and_biases():
    transformers = pytest.importorskip("transformers")
    config = transformers.RobertaConfig(vocab_size=60, hidden_size=16, num_hidden_layers=2,
                                        num_attention_heads=2, intermediate_size=32,
                                        max_position_embeddings=32)
    model = ChunkedTextClassifier(transformers.RobertaModel(config), n_classes=3)
    groups = parameter_groups(model, weight_decay=0.01)
    names = {id(parameter): name for name, parameter in model.named_parameters()}
    exempt = [names[id(parameter)] for parameter in groups[1]["params"]]
    assert exempt, "phải có tham số được miễn weight decay"
    assert all("LayerNorm" in name or name.endswith("bias") for name in exempt)
    assert len(groups[0]["params"]) + len(exempt) == len(list(model.parameters()))

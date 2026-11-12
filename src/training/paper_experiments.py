"""Task 4.3: ba nhánh thực nghiệm lấy ý tưởng từ bài báo, trên GGNN và Graph B.

Khác với Task 4.1b và 4.2, đây không phải bài toán chọn cấu hình. Ba nhánh được đăng ký trước
cùng giả thuyết, mỗi nhánh chạy một lần với ba seed, và test được báo cáo cho cả ba để đo tác
động của can thiệp. Không nhánh nào được chọn làm "mô hình của nhóm" dựa trên điểm test.

Nhóm đối chứng C0 được huấn luyện lại trong cùng phiên với hai nhánh can thiệp. Task 4.2 cho
thấy cùng một cấu hình chạy ở hai phiên khác nhau lệch tới 0,011 Macro-F1, nên chỉ so sánh
trong cùng phiên mới tách được tác động của can thiệp khỏi dao động giữa các lần chạy.
"""

from __future__ import annotations

from .gcn_tuning import BASELINE, CANDIDATES, GGNN_B, PROTOCOLS, SEEDS

SCOPE = GGNN_B  # ("ggnn", "graph_b")
BASE_CONFIG_ID = "L1"  # cấu hình đã cố định ở Task 4.2

#: Mỗi nhánh chỉ đổi đúng một yếu tố so với C0. ``token_init`` là cờ, đường dẫn tệp do notebook cấp.
ARMS = {
    "C0": {},
    "P1": {"token_init": True},
    "P2": {"loss": "adaptive"},
}
ARM_HYPOTHESES = {
    "C0": "Nhóm đối chứng: cấu hình L1 của Task 4.2, huấn luyện lại trong cùng phiên.",
    "P1": "Khởi tạo embedding token bằng CodeBERT cấp ngữ nghĩa mã nguồn mà vocabulary tự học "
          "không có, theo hướng của Vul-LMGNNs.",
    "P2": "Loss thích nghi kiểu LIVABLE nâng F1 của các lớp CWE ít mẫu, nhờ đó nâng Macro-F1.",
}
ARM_LABELS = {
    "C0": "C0 đối chứng (L1)",
    "P1": "P1 khởi tạo CodeBERT",
    "P2": "P2 loss thích nghi",
}


def arm_configuration(arm: str) -> dict:
    """Siêu tham số của một nhánh: cấu hình nền L1 cộng đúng một thay đổi."""
    if arm not in ARMS:
        raise ValueError(f"Nhánh không hợp lệ: {arm!r}")
    base = {**BASELINE, **CANDIDATES[BASE_CONFIG_ID], "loss": "weighted_ce", "token_init": False}
    return {**base, **ARMS[arm]}


def arm_arguments(arm: str, token_init_path: str | None = None) -> list[str]:
    """Tham số dòng lệnh riêng của nhánh, để ghép vào lệnh gọi ``scripts/train_gnn.py``."""
    configuration = arm_configuration(arm)
    arguments: list[str] = []
    for name in BASELINE:
        value = configuration[name]
        if value is not None:
            arguments += ["--" + name.replace("_", "-"), str(value)]
    if configuration["loss"] != "weighted_ce":
        arguments += ["--loss", configuration["loss"]]
    if configuration["token_init"]:
        if not token_init_path:
            raise ValueError("Nhánh P1 cần đường dẫn tệp khởi tạo embedding token")
        arguments += ["--token-init", token_init_path]
    elif token_init_path:
        raise ValueError(f"Nhánh {arm} không dùng khởi tạo embedding token")
    return arguments


def validate_arm(directory, arm: str) -> dict:
    """Kiểm tra một thư mục kết quả đúng là nhánh đã đăng ký, có đủ test cho hai protocol."""
    import csv
    import json
    from pathlib import Path

    directory = Path(directory)
    meta = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    arguments = meta["arguments"]
    configuration = arm_configuration(arm)
    model, graph = SCOPE
    if arguments["models"] != [model] or arguments["graphs"] != [graph]:
        raise ValueError("Nhánh phải chạy đúng một mô hình và một graph đã khai báo")
    if arguments["seeds"] != list(SEEDS) or arguments["protocols"] != list(PROTOCOLS):
        raise ValueError("Nhánh phải đủ ba seed và hai protocol")
    if arguments["validation_only"] or arguments["frozen_selection"] or arguments["limit"]:
        raise ValueError("Nhánh phải huấn luyện đầy đủ và đánh giá test")
    if any(arguments[name] != configuration[name] for name in BASELINE):
        raise ValueError("Siêu tham số khác cấu hình nền đã đăng ký")
    if arguments["loss"] != configuration["loss"]:
        raise ValueError("Hàm mất mát khác nhánh đã đăng ký")
    if bool(arguments["token_init"]) != configuration["token_init"]:
        raise ValueError("Khởi tạo embedding token khác nhánh đã đăng ký")
    with (directory / "results.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    expected = {(protocol, str(seed), split)
                for protocol in PROTOCOLS for seed in SEEDS for split in ("validation", "test")}
    if {(r["protocol"], r["seed"], r["split"]) for r in rows} != expected:
        raise ValueError("Thiếu kết quả validation hoặc test của nhánh")
    return meta

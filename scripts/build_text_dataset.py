"""Task 4.5: dựng tập văn bản hàm từ dữ liệu thô DiverseVul.

Mô hình text cần mã nguồn gốc. Kaggle Dataset của Task 4.0 chỉ chứa id token theo
vocabulary tự học nên không dùng được. Script này ghép ba nguồn đã có sẵn:

1. Tệp jsonl DiverseVul thô trong ``data/raw/diversevul/`` (bị gitignore, mỗi người
   tự chuẩn bị, chính là tệp Task 3.3 đã dùng cho Joern).
2. Manifest split của Task 2.3 trong ``data/splits/``.
3. Danh sách mẫu bị loại của Task 3.3 trong ``reports/graph/3_3_failed_samples.csv``.

Kết quả là một tệp ``.jsonl.gz`` để đẩy lên Kaggle làm input cho notebook 4.5.
Script kiểm tra số mẫu từng split khớp với dữ liệu đã xử lý của Task 4.0, vì nếu
lệch thì số của Task 4.5 không đặt cạnh số của Task 4.1 đến 4.3 được.

Ví dụ:
    python scripts/build_text_dataset.py --out data/interim/diversevul_text.jsonl.gz
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.diversevul_audit import canonicalize, resolve_fields  # noqa: E402
from src.data.loader import load_dataset  # noqa: E402
from src.data.text_dataset import (  # noqa: E402
    EXPECTED_TOTAL,
    check_split_sizes,
    load_cwe_mapping,
    split_sizes,
    write_text_dataset,
)

PROTOCOL_COLUMNS = {"project_wise": "project_wise_split", "seen_project": "seen_project_split"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--raw-dir", type=Path, default=ROOT / "data" / "raw" / "diversevul",
                   help="Thư mục chứa tệp DiverseVul thô.")
    p.add_argument("--dataset-file", type=Path, default=None,
                   help="Chỉ định thẳng tệp dataset nếu thư mục có nhiều tệp.")
    p.add_argument("--manifest", type=Path,
                   default=ROOT / "data" / "splits" / "diversevul_experiment_manifest.csv")
    p.add_argument("--failed", type=Path, default=ROOT / "reports" / "graph" / "3_3_failed_samples.csv")
    p.add_argument("--schema", type=Path, default=ROOT / "configs" / "graph" / "schema_spec.yaml")
    p.add_argument("--out", type=Path, required=True, help="Tệp .jsonl.gz sẽ ghi ra.")
    p.add_argument("--allow-count-mismatch", action="store_true",
                   help="Chỉ cảnh báo thay vì dừng khi số mẫu lệch so với Task 4.0.")
    return p.parse_args()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            sha.update(block)
    return sha.hexdigest()


def main() -> int:
    a = parse_args()
    cwe_mapping = load_cwe_mapping(a.schema)

    manifest = read_csv_rows(a.manifest)
    dropped = {row["sample_id"] for row in read_csv_rows(a.failed)}
    print(f"Manifest {len(manifest)} mẫu, Task 3.3 loại {len(dropped)} mẫu")

    loaded = load_dataset("diversevul", a.raw_dir, a.dataset_file)
    fields = resolve_fields(loaded.frame, {"code_field": "func", "label_field": "target",
                                           "cwe_field": "cwe", "project_field": "project",
                                           "commit_field": "commit_id", "hash_field": "hash"})
    records = canonicalize(loaded.frame, fields)
    source_by_id = dict(zip(records["sample_id"], records["source_code"], strict=True))
    print(f"Dữ liệu thô {len(source_by_id)} dòng, tệp {loaded.source_file.name}")

    samples, missing_source, empty_source, unknown_cwe = [], [], [], []
    for row in manifest:
        sample_id = row["sample_id"]
        if sample_id in dropped:
            continue
        if row["cwe"] not in cwe_mapping:
            unknown_cwe.append(sample_id)
            continue
        if sample_id not in source_by_id:
            missing_source.append(sample_id)
            continue
        func = source_by_id[sample_id]
        if not isinstance(func, str) or not func.strip():
            empty_source.append(sample_id)
            continue
        samples.append({
            "sample_id": sample_id,
            "func": func,
            "cwe": row["cwe"],
            "y": cwe_mapping[row["cwe"]],
            "project_wise": row[PROTOCOL_COLUMNS["project_wise"]],
            "seen_project": row[PROTOCOL_COLUMNS["seen_project"]],
        })

    for name, ids in (("thiếu mã nguồn", missing_source), ("mã nguồn rỗng", empty_source),
                      ("CWE ngoài 23 lớp", unknown_cwe)):
        if ids:
            print(f"CẢNH BÁO {len(ids)} mẫu {name}, ví dụ {ids[:5]}")

    problems = check_split_sizes(samples)
    sizes = split_sizes(samples)
    print(f"Tổng {len(samples)} mẫu, cần {EXPECTED_TOTAL}")
    for protocol, counts in sizes.items():
        print(f"  {protocol}: " + ", ".join(f"{k}={v}" for k, v in counts.items()))
    if len(samples) != EXPECTED_TOTAL:
        problems.append(f"tổng: có {len(samples)}, cần {EXPECTED_TOTAL}")
    if problems:
        message = "Tập văn bản lệch khỏi dữ liệu đã xử lý của Task 4.0:\n  " + "\n  ".join(problems)
        if not a.allow_count_mismatch:
            raise SystemExit(message + "\nDùng --allow-count-mismatch nếu đây là chủ ý.")
        print("CẢNH BÁO " + message)

    written = write_text_dataset(a.out, samples)
    sidecar = a.out.with_suffix(a.out.suffix + ".meta.json")
    sidecar.write_text(json.dumps({
        "n_samples": written,
        "split_sizes": sizes,
        "n_classes": len(cwe_mapping),
        "source_file": loaded.source_file.name,
        "manifest_sha256": digest(a.manifest),
        "failed_sha256": digest(a.failed),
        "schema_sha256": digest(a.schema),
        "dataset_sha256": digest(a.out),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    size_mb = a.out.stat().st_size / 2**20
    print(f"Đã ghi {written} mẫu vào {a.out} ({size_mb:.1f} MB)")
    print(f"Dấu vân tay: {sidecar}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

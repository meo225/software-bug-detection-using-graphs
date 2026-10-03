"""Build the reproducible DiverseVul EDA notebook from a small cell specification."""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "notebooks" / "01_diversevul_eda.ipynb"


def md(title: str, text: str) -> object:
    return nbf.v4.new_markdown_cell(f"## {title}\n\n{text}")


def code(source: str) -> object:
    return nbf.v4.new_code_cell(source.strip())


def build() -> None:
    notebook = nbf.v4.new_notebook()
    notebook["metadata"]["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
    notebook["metadata"]["language_info"] = {"name": "python", "version": "3.10+"}
    notebook["cells"] = [
        nbf.v4.new_markdown_cell(
            "# DiverseVul dataset audit\n\n"
            "Audit function-level C/C++ records for CWE-classification suitability. "
            "This notebook does not choose Top-K, a label policy, a final split, a graph representation, or a GNN."
        ),
        md("1. Setup", "Resolve every path from the repository root and fix the sampling seed."),
        code("""
from pathlib import Path
import sys
import pandas as pd
from IPython.display import display, Image

ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.loader import load_dataset
from src.data.diversevul_audit import run_audit, read_optional_metadata, metadata_audit, schema_table
from src.utils.config import load_config

SEED = 105
config = load_config(ROOT / "configs/data/diversevul.yaml")["dataset"]
raw_dir = ROOT / config["local_raw_dir"]
print("Repository:", ROOT)
print("Raw directory:", raw_dir)
"""),
        md("2. Load dataset", "Load the real local release losslessly. Missing data remains an explicit blocked state."),
        code("""
dataset_available = False
blocked_reason = None
try:
    loaded = load_dataset(config["name"], raw_dir)
    raw = loaded.frame
    dataset_available = True
    print("File:", loaded.source_file)
    print("Shape:", raw.shape)
except FileNotFoundError as error:
    blocked_reason = str(error)
    print("BLOCKED:", blocked_reason)
"""),
        md("3. Dataset schema", "Print actual columns, dtypes, shape, field mapping, missingness, and bounded examples. No field is invented."),
        code("""
if dataset_available:
    result = run_audit(raw, config)
    print(raw.dtypes)
    print("Resolved fields:", result.fields)
    display(result.tables["missing_values"])
else:
    print("Schema not observed because no dataset file was loaded.")
"""),
        md("4. Verify paper statistics", "Recompute the six headline metrics and retain every difference from the paper baseline."),
        code("display(result.tables['paper_comparison']) if dataset_available else print('Not computed.')"),
        md("5. Missing data", "Review raw-column missingness, including absent semantic fields."),
        code("display(result.tables['missing_values']) if dataset_available else print('Not computed.')"),
        md("6. Vulnerable/CWE coverage", "CWE classification analysis uses vulnerable records only."),
        code("display(result.tables['dataset_summary']) if dataset_available else print('Not computed.')"),
        md("7. CWE distribution", "Per-CWE function, project, commit, and labeled-vulnerable coverage. Multi-CWE rows contribute to each attached CWE."),
        code("display(result.tables['cwe_distribution'].head(20)) if dataset_available else print('Not computed.')"),
        md("8. Threshold analysis", "Evaluate 20/50/100/200 samples per CWE without choosing a threshold."),
        code("display(result.tables['threshold_analysis']) if dataset_available else print('Not computed.')"),
        md("9. Multi-CWE analysis", "Measure zero, one, and two-or-more CWE values without converting the task to single-label."),
        code("""
if dataset_available:
    display(result.tables["multi_cwe_summary"])
    display(result.tables["cwe_count_distribution"])
    display(result.tables["multi_cwe_examples"])
else:
    print("Not computed.")
"""),
        md("10. Project distribution", "Compare total and vulnerable function volume plus CWE breadth per project."),
        code("display(result.tables['project_distribution'].head(20)) if dataset_available else print('Not computed.')"),
        md("11. CWE-project analysis", "Measure project support and largest-project concentration for every CWE."),
        code("""
if dataset_available:
    display(result.tables["cwe_project_distribution"].head(30))
    display(result.tables["project_split_feasibility"])
else:
    print("Not computed.")
"""),
        md("12. Duplicate analysis", "Compare exact source hashes with conservative line-ending/trailing-whitespace normalization and count label conflicts."),
        code("display(result.tables['duplicate_summary']) if dataset_available else print('Not computed.')"),
        md("13. Source-code quality", "Report missing/empty source and character/line length quantiles. Token counts are intentionally omitted."),
        code("""
if dataset_available:
    display(result.tables["source_quality_summary"])
    display(result.tables["function_length_summary"])
    display(result.tables["source_inspection_sample"])
else:
    print("Not computed.")
"""),
        md("14. Graph-readiness sample", "Create only a small deterministic manifest for a later Joern trial; do not generate CPGs here."),
        code("""
if dataset_available:
    display(result.tables["graph_sample_manifest"])
else:
    print("Manifest cannot be populated without the raw dataset.")
"""),
        md("15. Findings", "Generate all tables, figures, manifest, metadata audit, and Markdown report from the same computed result."),
        code("""
import subprocess
completed = subprocess.run(
    [sys.executable, str(ROOT / "scripts/run_diversevul_eda.py")],
    cwd=ROOT,
    check=True,
    text=True,
    capture_output=True,
)
print(completed.stdout.strip())
if dataset_available:
    metadata, _ = read_optional_metadata(raw_dir)
    result.tables["metadata_audit"] = metadata_audit(result.records, metadata)
    print(result.findings)
else:
    print("No findings are claimed; generated artifacts are visibly marked BLOCKED.")
"""),
        md("16. Open research decisions", "Evidence informs, but does not settle, the decisions below."),
        code("""
decisions = [
    "Top-K or minimum samples per CWE",
    "single-label, multi-label, hierarchical, or ambiguous-sample handling",
    "final project-aware split",
    "duplicate and label-conflict policy",
    "graph representation and Joern settings",
    "GNN architecture and evaluation protocol",
]
for decision in decisions:
    print("-", decision)
"""),
    ]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(notebook, OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    build()

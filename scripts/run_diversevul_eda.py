"""Run the DiverseVul audit and generate all committed EDA artifacts."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "data" / "interim" / "matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src.data.diversevul_audit import metadata_audit, read_optional_metadata, run_audit, write_json
from src.data.loader import load_dataset
from src.utils.config import load_config
from src.utils.paths import resolve_from_root

TABLE_DIR = ROOT / "reports" / "dataset" / "tables"
FIGURE_DIR = ROOT / "reports" / "dataset" / "figures"
REPORT_PATH = ROOT / "reports" / "dataset" / "dataset_eda.md"
MANIFEST_PATH = ROOT / "data" / "sample_manifests" / "diversevul_graph_sample.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "data" / "diversevul.yaml")
    parser.add_argument("--dataset-file", type=Path, help="Explicit main dataset file when discovery is ambiguous.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero instead of writing a blocked status when data is absent.")
    return parser.parse_args()


def _placeholder_figure(path: Path, message: str) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.axis("off")
    ax.text(0.5, 0.55, "EDA not run", ha="center", va="center", fontsize=20, weight="bold")
    ax.text(0.5, 0.40, message, ha="center", va="center", fontsize=11, wrap=True)
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def write_blocked_outputs(reason: str, raw_dir: Path) -> None:
    """Create explicitly marked placeholders without inventing measurements."""
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    schemas = {
        "dataset_summary.csv": ["metric", "value", "status", "note"],
        "missing_values.csv": ["field", "meaning", "dtype", "missing_count", "missing_percentage", "example"],
        "cwe_distribution.csv": ["cwe", "sample_count", "percentage_of_labeled_vulnerable", "project_count", "commit_count"],
        "threshold_analysis.csv": ["threshold", "number_of_cwe", "number_of_samples", "percentage_samples_retained", "minimum_class_size", "maximum_class_size"],
        "multi_cwe_summary.csv": ["category", "sample_count", "percentage_of_vulnerable"],
        "project_distribution.csv": ["project", "total_samples", "vulnerable_samples", "number_of_cwe"],
        "cwe_project_distribution.csv": ["cwe", "sample_count", "project_count", "largest_project_sample_count", "largest_project_share"],
        "duplicate_summary.csv": ["level", "records_with_code", "unique_code", "duplicate_groups", "duplicate_affected_records", "duplicate_excess_records", "duplicate_affected_percentage", "vulnerable_label_conflict_groups", "cwe_conflict_groups"],
    }
    for name, columns in schemas.items():
        frame = pd.DataFrame(columns=columns)
        if name == "dataset_summary.csv":
            frame = pd.DataFrame([{"metric": "audit_status", "value": "blocked", "status": "not_computed", "note": reason}])
        frame.to_csv(TABLE_DIR / name, index=False)
    pd.DataFrame(columns=["sample_id", "project", "commit", "cwe", "label", "source_reference"]).to_csv(MANIFEST_PATH, index=False)
    for name in ("cwe_top20.png", "cwe_distribution.png", "project_distribution.png", "function_length_distribution.png"):
        _placeholder_figure(FIGURE_DIR / name, "Raw DiverseVul data is missing. No values are plotted.")
    write_json(TABLE_DIR / "audit_status.json", {"status": "blocked", "reason": reason, "expected_raw_dir": str(raw_dir)})
    REPORT_PATH.write_text(_blocked_report(reason, raw_dir), encoding="utf-8")


def _blocked_report(reason: str, raw_dir: Path) -> str:
    return f"""# DiverseVul dataset audit

**Status: BLOCKED - raw dataset not available.**

No DiverseVul statistics were computed. The CSV and PNG files in this report directory are explicitly marked placeholders so missing input cannot be mistaken for a zero-valued result.

## Dataset files actually used

None. The inspected raw directory was `{raw_dir.as_posix()}` and contained no supported dataset file.

Reason: `{reason}`

## How to provide the data

1. Download the main dataset from the official DiverseVul repository link.
2. Optionally download its separate commit/repository metadata and label-noise spreadsheet.
3. Put the files under `data/raw/diversevul/`; do not commit them.
4. Run `python scripts/run_diversevul_eda.py --strict` from the repository root.
5. Execute `notebooks/01_diversevul_eda.ipynb` top-to-bottom as the presentation-level reproducibility check.

The runner accepts CSV, JSON, JSONL/NDJSON, Parquet, and official-source pickle files. Use `--dataset-file PATH` if more than one plausible main file is present. Pickle must only come from the trusted official release because loading it can execute code.

## Schema

Not observed. The pipeline will print and export actual columns, dtypes, shape, missingness, examples, and the resolved source/label/CWE/project/commit/hash/CVE/repository mappings. It fails instead of inventing required fields.

## Checks prepared but not executed on DiverseVul

- paper-versus-release row, vulnerable, non-vulnerable, project, commit, and CWE counts
- vulnerable-only CWE coverage, Top 10/20, long-tail and cumulative coverage
- thresholds 20/50/100/200 without choosing one
- zero/single/multi-CWE prevalence and bounded examples
- project and CWE-project concentration plus split feasibility at 2/3/5/10 projects
- exact and conservative-normalized duplicate/conflict checks
- source missingness and character/line length quantiles
- deterministic 30-function graph-readiness manifest
- optional metadata join and URL coverage

## Paper context, not EDA results

The comparison baseline encoded in the audit is 349,437 total functions, 18,945 vulnerable, 330,492 non-vulnerable, 797 projects, 7,514 commits, and 150 CWE categories. These values are never substituted for missing dataset measurements.

The paper's manual analysis reports roughly 60% accuracy for vulnerable-function labels. This is a limitation of fix-commit-derived labels, not a statistic recomputed from the absent full dataset. The official repository also states that its metadata covers 7,512 commits and is missing three commit URLs relative to the extracted dataset.

## Answers to the research questions

Q1-Q13 remain **not measured** for the local release. In particular, the current evidence is insufficient to state how many CWE are usable, whether project-wise splitting is feasible, or whether this copy of DiverseVul is graph-ready.

## Open research decisions

The audit intentionally does not choose a Top-K/threshold, single-label or multi-label policy, final split, graph representation, Joern configuration, or GNN architecture.
"""


def _barh(frame: pd.DataFrame, label: str, value: str, path: Path, title: str, top: int = 20) -> None:
    plot = frame.head(top).sort_values(value)
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(plot[label], plot[value], color="#2f6b9a")
    ax.set(title=title, xlabel="Samples", ylabel="")
    ax.grid(axis="x", alpha=0.2)
    fig.tight_layout()
    fig.savefig(path, dpi=160, facecolor="white")
    plt.close(fig)


def write_figures(result) -> None:
    cwe = result.tables["cwe_distribution"]
    _barh(cwe, "cwe", "sample_count", FIGURE_DIR / "cwe_top20.png", "Top 20 CWE among vulnerable labeled functions")
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    counts = cwe["sample_count"].sort_values(ascending=False).reset_index(drop=True)
    axes[0].plot(range(1, len(counts) + 1), counts, color="#2f6b9a")
    axes[0].set_yscale("log")
    axes[0].set(title="CWE class-size long tail", xlabel="CWE rank", ylabel="Samples (log scale)")
    axes[1].plot(range(1, len(counts) + 1), counts.cumsum().div(counts.sum()).mul(100), color="#c77721")
    axes[1].set(title="Cumulative CWE-label coverage", xlabel="CWE rank", ylabel="Cumulative percentage")
    fig.tight_layout(); fig.savefig(FIGURE_DIR / "cwe_distribution.png", dpi=160, facecolor="white"); plt.close(fig)
    _barh(result.tables["project_distribution"], "project", "vulnerable_samples", FIGURE_DIR / "project_distribution.png", "Top projects by vulnerable functions")
    source = result.records["source_code"].fillna("").astype(str)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    axes[0].hist(source.str.len().clip(upper=source.str.len().quantile(.99)), bins=50, color="#2f6b9a")
    axes[0].set(title="Characters/function (clipped at p99)", xlabel="Characters", ylabel="Functions")
    lines = source.map(lambda text: 0 if not text else text.count("\n") + 1)
    axes[1].hist(lines.clip(upper=lines.quantile(.99)), bins=50, color="#c77721")
    axes[1].set(title="Lines/function (clipped at p99)", xlabel="Lines", ylabel="Functions")
    fig.tight_layout(); fig.savefig(FIGURE_DIR / "function_length_distribution.png", dpi=160, facecolor="white"); plt.close(fig)


def _fmt(value: object) -> str:
    return f"{value:,.2f}" if isinstance(value, float) else f"{value:,}" if isinstance(value, int) else str(value)


def _markdown_table(frame: pd.DataFrame, limit: int | None = None) -> str:
    shown = frame.head(limit) if limit else frame
    headers = [str(column) for column in shown.columns]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in shown.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(_fmt(value).replace("|", "\\|") for value in row) + " |")
    return "\n".join(lines)


def write_report(result, dataset_file: Path, metadata_file: Path | None) -> None:
    tables = result.tables
    f = result.findings
    cwe = tables["cwe_distribution"]
    dup = tables["duplicate_summary"]
    top_candidate = tables["cwe_project_distribution"].query("sample_count >= 20").head(20)
    text = f"""# DiverseVul dataset audit

**Status: COMPLETE for the local files listed below.** This report describes the loaded release; it does not select the final dataset, class set, label policy, split, graph representation, or model.

## Dataset files actually used

- Main dataset: `{dataset_file.as_posix()}`
- Separate metadata: `{metadata_file.as_posix() if metadata_file else 'not provided'}`

Shape: **{len(result.records):,} rows x {f['raw_column_count']:,} raw columns**. Actual raw schema and missing values are in `tables/missing_values.csv`.

Resolved fields: `{result.fields}`

## Paper comparison

{_markdown_table(tables['paper_comparison'])}

Differences are preserved as observed. Likely explanations must be investigated from release/version, parsing, metadata coverage, or record duplication; values are never changed to match the paper.

## CWE coverage and imbalance

- Vulnerable functions with at least one parsed CWE: **{f['vulnerable_with_cwe']:,}**
- Vulnerable functions without a parsed CWE: **{f['vulnerable_without_cwe']:,}**
- Unique parsed CWE values on vulnerable functions: **{f['unique_cwe_vulnerable']:,}**

Top 20:

{_markdown_table(cwe, 20)}

Threshold evidence (a multi-CWE function is retained once if any label passes):

{_markdown_table(tables['threshold_analysis'])}

## Multi-CWE

{_markdown_table(tables['multi_cwe_summary'])}

No multi-CWE record is reduced to its first label. Examples are in `tables/multi_cwe_examples.csv`.

## Projects and project-wise feasibility

{_markdown_table(tables['project_split_feasibility'])}

Candidate evidence table (not a selected class set):

{_markdown_table(top_candidate, 20)}

High `largest_project_share` indicates project leakage/concentration risk even when class size is large.

## Duplicates and conflicts

{_markdown_table(dup)}

Normalization only converts line endings, removes trailing spaces/tabs per line, and trims boundary blank lines. It does not collapse internal whitespace or remove comments.

## Source-code quality and graph readiness

{_markdown_table(tables['source_quality_summary'])}

{_markdown_table(tables['function_length_summary'])}

The bounded manual-review sample is in `tables/source_inspection_sample.csv`. The manifest `data/sample_manifests/diversevul_graph_sample.csv` contains deterministic references to up to 30 vulnerable functions across length and CWE-cardinality bands. It does not embed full source code. This audit does not run Joern.

## Metadata audit

{_markdown_table(tables['metadata_audit'])}

## Label-noise context

The paper reports that vulnerable-function labels were only roughly 60% accurate in its manual sample. Main error modes include cross-function vulnerabilities, helper/caller changes needed for a fix, and unrelated changes in a security-fixing commit. This paper result is context, not recomputed full-dataset EDA. If the official noise spreadsheet is provided, it must be summarized separately and never merged into the full-dataset denominator.

## Direct answers

1. **Paper match:** see the exact differences above; no mismatch was corrected.
2. **Vulnerable functions with CWE:** {f['vulnerable_with_cwe']:,}.
3. **Usable CWE:** no single number without a policy; threshold and project-support tables provide the candidate counts.
4. **Imbalance:** the ranked distribution and cumulative chart show the observed long tail.
5. **Thresholds:** all four requested thresholds are reported; none is selected.
6. **Multi-CWE:** {f['multi_cwe_samples']:,} vulnerable samples have at least two parsed CWE values.
7. **Duplicates:** exact and normalized rates are reported above.
8. **Label conflicts:** vulnerable/non-vulnerable and CWE conflict-group counts are reported above.
9. **Project spread:** see per-CWE project count and largest-project share.
10. **Project-wise split:** feasible only for classes meeting the desired project-support row; no final split is created.
11. **Joern readiness:** source completeness/length and the sample manifest support a bounded trial; parser success still requires the next phase.
12. **Candidate CWE:** use the non-binding candidate evidence table above, then choose policy as a team.
13. **Overall fit:** DiverseVul is conditionally useful for function-to-CWE research only with an explicit multi-CWE policy, duplicate/conflict handling, label-noise caveats, and project-aware evaluation.

## Open research decisions

- minimum class size and candidate CWE set
- single-label, multi-label, hierarchical, or ambiguous-sample policy
- final project-aware split constraints
- duplicate/conflict treatment
- graph representation and Joern extraction settings
- final GNN architecture and evaluation protocol
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def main() -> int:
    args = parse_args()
    config = load_config(args.config)["dataset"]
    raw_dir = resolve_from_root(*Path(config["local_raw_dir"]).parts)
    TABLE_DIR.mkdir(parents=True, exist_ok=True); FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        loaded = load_dataset(config["name"], raw_dir, args.dataset_file)
    except FileNotFoundError as error:
        if args.strict:
            print(f"BLOCKED: {error}", file=sys.stderr)
            return 2
        write_blocked_outputs(str(error), raw_dir)
        print(f"BLOCKED: {error}")
        return 0
    result = run_audit(loaded.frame, config)
    metadata, metadata_path = read_optional_metadata(raw_dir)
    result.tables["metadata_audit"] = metadata_audit(result.records, metadata)
    for name, table in result.tables.items():
        if name == "graph_sample_manifest":
            table.to_csv(MANIFEST_PATH, index=False)
        else:
            table.to_csv(TABLE_DIR / f"{name}.csv", index=False)
    write_figures(result)
    write_json(TABLE_DIR / "audit_status.json", {"status": "complete", "dataset_file": str(loaded.source_file), "fields": result.fields})
    write_report(result, loaded.source_file, metadata_path)
    print(f"EDA complete: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# DiverseVul dataset audit

**Status: BLOCKED - raw dataset not available.**

No DiverseVul statistics were computed. The CSV and PNG files in this report directory are explicitly marked placeholders so missing input cannot be mistaken for a zero-valued result.

## Dataset files actually used

None. The inspected raw directory was `D:/PROJECT/software-bug-detection-using-graphs/data/raw/diversevul` and contained no supported dataset file.

Reason: `DiverseVul raw directory does not exist: D:\PROJECT\software-bug-detection-using-graphs\data\raw\diversevul. See data/raw/README.md.`

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

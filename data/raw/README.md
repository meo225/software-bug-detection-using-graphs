# Raw dataset setup

Raw data is intentionally ignored by Git.

For DiverseVul, create `data/raw/diversevul/` and place the official main dataset there. Optional separate commit/repository metadata and the official label-noise export may live in the same directory with descriptive names containing `metadata` or `label_noise`.

Official source and current download links: <https://github.com/wagner-group/diversevul>

Then run:

```powershell
python scripts/run_diversevul_eda.py --strict
```

Supported main-file formats are CSV, JSON, JSONL/NDJSON, Parquet, and pickle. Only load pickle from the official trusted release. If discovery finds several plausible main files, pass the intended one with `--dataset-file`.

Do not rename fields to fit the pipeline. The audit records the actual schema and only maps fields when a known unambiguous name or an explicit config field exists.

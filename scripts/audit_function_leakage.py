"""Task 4.4 local audit. Exit 0 clean, 1 cross-split matches, 2 blocked."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.function_leakage_audit import (  # noqa: E402
    METHODS, PROTOCOLS, TABLE_COLUMNS, analyze, fingerprint, hash_samples,
    join_sources, read_csv, validate_inputs, write_csv,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset-file', type=Path, default=ROOT/'data/raw/diversevul/diversevul.jsonl')
    parser.add_argument('--manifest', type=Path, default=ROOT/'data/splits/diversevul_experiment_manifest.csv')
    parser.add_argument('--failed-samples', type=Path, default=ROOT/'reports/graph/3_3_failed_samples.csv')
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    out = args.output_dir
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        print('BLOCKED: output directory must be new or empty', file=sys.stderr)
        return 2
    # Reject output directories that equal or contain an input file.
    for protected in (args.dataset_file, args.manifest, args.failed_samples):
        if out.resolve() == protected.resolve() or protected.resolve().is_relative_to(out.resolve()):
            print('BLOCKED: output overlaps an input', file=sys.stderr)
            return 2
    out.mkdir(parents=True, exist_ok=True)

    def save(name: str, payload: dict) -> None:
        (out/name).write_text(json.dumps(payload, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

    validation = {'status': 'BLOCKED'}
    provenance = {'python': platform.python_version(), 'normalization': 'delete ASCII space, TAB, LF, CR only',
                  'row_id': 'zero-based nonblank JSON object index',
                  'paper': 'https://arxiv.org/html/2403.18624v2#S3.SS1', 'inputs': {}}
    git = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True, capture_output=True)
    provenance['git_sha'] = git.stdout.strip() if git.returncode == 0 else None
    try:
        for name, path in (('manifest', args.manifest), ('failed', args.failed_samples)):
            provenance['inputs'][name] = fingerprint(path)
        manifest, failed = read_csv(args.manifest), read_csv(args.failed_samples)
        valid, counts = validate_inputs(manifest, failed)
        validation.update(counts)
        # Existing split ID files are authoritative alongside the manifest.
        for p in PROTOCOLS:
            for split in ('train', 'validation', 'test'):
                path = ROOT/'data/splits'/('diversevul_'+p)/(split+'.txt')
                actual = path.read_text(encoding='utf-8').splitlines()
                expected = {r['sample_id'] for r in manifest if r[p+'_split'] == split}
                if len(actual) != len(set(actual)) or set(actual) != expected:
                    raise ValueError(f'split ID file mismatch: {path}')
                provenance['inputs'][p+'/'+split] = fingerprint(path)
        provenance['inputs']['dataset'] = fingerprint(args.dataset_file)
        reference_path = ROOT/'reports/dataset/tables/audit_status.json'
        reference = json.loads(reference_path.read_text(encoding='utf-8'))
        provenance['inputs']['raw_reference'] = fingerprint(reference_path)
        raw = provenance['inputs']['dataset']
        if raw['sha256'] != reference['dataset_sha256'] or raw['bytes'] != reference['dataset_size_bytes']:
            raise ValueError('raw dataset fingerprint differs from committed provenance')
        rows, joined = join_sources(args.dataset_file, manifest, expected_records=330492)
        validation.update(joined)
        excluded = {r['sample_id'] for r in failed}
        valid_rows = [r for r in rows if r['sample_id'] not in excluded]
        hashes = hash_samples(rows, excluded)
        write_csv(out/'sample_hashes.csv', hashes, list(hashes[0]))
        tables = {name: [] for name in TABLE_COLUMNS}
        for cohort, cohort_rows in (('manifest', rows), ('valid', valid_rows)):
            for method in METHODS:
                result = analyze(cohort_rows, method, cohort)
                for name, records in result.items():
                    tables[name].extend(records)
        for name, columns in TABLE_COLUMNS.items():
            write_csv(out/(name+'.csv'), tables[name], columns.split())
        comparison = [r for r in tables['duplicate_summary'] if r['split'] == 'all']
        write_csv(out/'legacy_comparison.csv', comparison, TABLE_COLUMNS['duplicate_summary'].split())
        old = [r for r in comparison if r['cohort'] == 'manifest' and r['method'] == 'legacy']
        report_path = ROOT/'data/splits/diversevul_split_report.json'
        report = json.loads(report_path.read_text(encoding='utf-8'))
        provenance['inputs']['legacy_reference'] = fingerprint(report_path)
        if any(r['duplicate_groups'] != report['group_stats']['normalized_duplicate_groups'] for r in old):
            raise ValueError('legacy duplicate count differs from Task 2.3')
        if any(r['duplicate_pairs'] for r in tables['cross_split_leakage']
               if r['method'] == 'legacy' and r['split_pair'] == 'all_cross_split'):
            raise ValueError('legacy cross-split result differs from Task 2.3')
        leaking = any(r['duplicate_pairs'] for r in tables['cross_split_leakage']
                      if r['cohort'] == 'valid' and r['method'] == 'primevul' and r['split_pair'] == 'all_cross_split')
        validation.update(status='FAIL' if leaking else 'PASS', audit_execution='PASS',
                          review_status='PENDING' if leaking else 'NOT_REQUIRED',
                          conclusion='Cross-split normalized matches require source review' if leaking else 'No cross-split matches under this normalization')
        code = 1 if leaking else 0
    except (OSError, ValueError, KeyError, UnicodeError) as error:
        validation.update(status='BLOCKED', error=str(error), conclusion='No full-audit conclusion')
        code = 2
    save('provenance.json', provenance)
    save('input_validation.json', validation)
    print(json.dumps(validation, ensure_ascii=False))
    return code


if __name__ == '__main__':
    raise SystemExit(main())

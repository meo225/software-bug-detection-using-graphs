"""Synthetic tests require no raw data, graph preprocessing or training."""
import hashlib
import json

import pytest

from src.data.function_leakage_audit import (
    analyze, hash_samples, join_sources, normalize_primevul, validate_inputs,
    write_csv,
)
from src.data.preprocessing import normalize_whitespace


def row(i, split='train', source='int f() { return 1; }'):
    return dict(sample_id=f'row-{i}', project='p', commit='c', cwe='CWE-20',
                project_wise_split=split, seen_project_split=split, source=source)


def test_formatting_and_legacy_unchanged():
    assert normalize_primevul(' a\t\r\nb ') == 'ab'
    assert normalize_primevul('\v\f\u00a0') == '\v\f\u00a0'
    assert normalize_whitespace('\r\n a \t\r\n') == ' a'
    assert normalize_primevul('int f(){return 1;}') == normalize_primevul('int\tf() {\n return 1;\r}')
    assert normalize_whitespace('int f(){}') != normalize_whitespace('int  f(){}')


def test_known_false_positives_and_nonmatches():
    for a, b in [('"a b"', '"ab"'), ('a + +b', 'a++b')]:
        assert normalize_primevul(a) == normalize_primevul(b)
    for a, b in [('foo', 'bar'), ('/*a*/x', '/*b*/x'), ('A', 'a')]:
        assert normalize_primevul(a) != normalize_primevul(b)


def test_four_members_pair_counts_and_protocols():
    rows = [row(i, s) for i, s in enumerate(['train','train','validation','test'])]
    rows[3]['seen_project_split'] = 'train'
    result = analyze(rows, 'primevul', 'valid')
    summary = next(r for r in result['duplicate_summary'] if r['protocol']=='project_wise' and r['split']=='all')
    assert (summary['duplicate_groups'], summary['affected_samples'], summary['excess_samples'], summary['duplicate_pairs']) == (1,4,3,6)
    cross = [r for r in result['cross_split_leakage'] if r['protocol']=='project_wise']
    assert [r['duplicate_pairs'] for r in cross] == [2,2,1,5]
    assert cross[-1]['affected_samples'] == 4
    assert cross[1]['held_out_samples'] == 1
    seen = [r for r in result['cross_split_leakage'] if r['protocol']=='seen_project']
    assert seen[-1]['duplicate_pairs'] == 3
    assert len(result['cross_split_review']) == 2
    assert analyze(list(reversed(rows)), 'primevul', 'valid')['duplicate_summary'] == result['duplicate_summary']


def test_empty_and_internal_groups(tmp_path):
    result = analyze([row(0),row(1)], 'primevul', 'valid')
    assert all(r['duplicate_pairs']==0 for r in result['cross_split_leakage'])
    assert not analyze([row(0)], 'primevul', 'valid')['duplicate_groups']
    path = tmp_path/'empty.csv'
    write_csv(path, [], ['sample_id'])
    assert path.read_text() == 'sample_id\n'


def test_join_zero_index_blank_lines_and_sparse_ids(tmp_path):
    path = tmp_path/'raw.jsonl'
    obj = dict(func='f(){}', target=1, project='p', commit_id='c', cwe=['CWE-20'])
    path.write_text('\n'+json.dumps(obj)+'\n\n'+json.dumps(obj)+'\n'+json.dumps(obj)+'\n', encoding='utf-8')
    joined, evidence = join_sources(path, [row(2),row(0)], 3)
    assert [r['sample_id'] for r in joined] == ['row-0','row-2']
    assert [r['physical_line'] for r in joined] == [2,5]
    assert evidence['blank_lines'] == 2
    with pytest.raises(ValueError, match='incomplete'):
        join_sources(path, [row(9)], 3)
    obj['commit_id']='wrong'
    path.write_text(json.dumps(obj), encoding='utf-8')
    with pytest.raises(ValueError, match='metadata'):
        join_sources(path, [row(0)], 1)


@pytest.mark.parametrize('payload', ['[]', '{bad', json.dumps(dict(func=None, target=1, project='p', commit_id='c', cwe=['CWE-20'])), json.dumps(dict(func=' \t', target=1, project='p', commit_id='c', cwe=['CWE-20']))])
def test_bad_raw(tmp_path, payload):
    path=tmp_path/'raw.jsonl'
    path.write_text(payload, encoding='utf-8')
    with pytest.raises(ValueError):
        join_sources(path, [row(0)], 1)


def test_input_validation_and_hashes():
    rows = [row(0), row(1,'test')]
    valid, evidence = validate_inputs(rows, [rows[0]], (2,1,1))
    assert valid == [rows[1]] and evidence['valid'] == 1
    for manifest, failed in [(rows+rows, []), (rows, [row(9)]), ([dict(row(0),sample_id='row-01')],[]), (rows,[dict(rows[0],cwe='bad')])]:
        with pytest.raises(ValueError):
            validate_inputs(manifest, failed, (2,1,1))
    hashes=hash_samples(rows, {'row-0'})
    assert hashes[0]['included'] is False
    assert hashes[0]['primevul_md5'] == hashlib.md5(b'intf(){return1;}', usedforsecurity=False).hexdigest()
    assert all('source' not in r for r in hashes)


def test_collision_is_rejected(monkeypatch):
    class Collision:
        def hexdigest(self):
            return 'same'
    monkeypatch.setattr(hashlib, 'sha256', lambda *a: Collision())
    with pytest.raises(ValueError, match='collision'):
        analyze([row(0,source='a'),row(1,source='b')], 'primevul', 'valid')


@pytest.mark.parametrize('leaking', [False, True])
def test_cli_end_to_end_synthetic(tmp_path, monkeypatch, leaking):
    import scripts.audit_function_leakage as cli
    from src.data.function_leakage_audit import fingerprint
    monkeypatch.setattr(cli, 'ROOT', tmp_path)
    rows = [row(0), row(1, 'test', 'int  f(){return 1;}' if leaking else 'other(){}')]
    for r in rows:
        r.pop('source')
    raw = tmp_path/'raw.jsonl'
    raw.write_text('\n'.join(json.dumps(dict(func=s, target=1, project='p', commit_id='c', cwe=['CWE-20']))
                             for s in ['int f(){return 1;}', 'int  f(){return 1;}' if leaking else 'other(){}']), encoding='utf-8')
    manifest, failed = tmp_path/'manifest.csv', tmp_path/'failed.csv'
    write_csv(manifest, rows, list(rows[0]))
    write_csv(failed, [], list(rows[0]))
    for p in ('project_wise', 'seen_project'):
        directory=tmp_path/'data/splits'/('diversevul_'+p)
        directory.mkdir(parents=True)
        for s in ('train','validation','test'):
            (directory/(s+'.txt')).write_text('\n'.join(r['sample_id'] for r in rows if r[p+'_split']==s))
    ref=tmp_path/'reports/dataset/tables/audit_status.json'
    ref.parent.mkdir(parents=True)
    info=fingerprint(raw)
    ref.write_text(json.dumps(dict(dataset_sha256=info['sha256'],dataset_size_bytes=info['bytes'])))
    (tmp_path/'data/splits/diversevul_split_report.json').write_text(json.dumps({'group_stats':{'normalized_duplicate_groups':0}}))
    monkeypatch.setattr(cli, 'validate_inputs', lambda m,f: validate_inputs(m,f,(2,0,2)))
    monkeypatch.setattr(cli, 'join_sources', lambda p,m,expected_records: join_sources(p,m,2))
    out=tmp_path/'out'
    args=['--dataset-file',str(raw),'--manifest',str(manifest),'--failed-samples',str(failed),'--output-dir',str(out)]
    assert cli.main(args) == int(leaking)
    result=json.loads((out/'input_validation.json').read_text())
    assert result['status'] == ('FAIL' if leaking else 'PASS')
    assert (out/'duplicate_groups.csv').exists()
    assert cli.main(args) == 2  # no overwrite


def test_cli_missing_raw_retains_count_evidence(tmp_path):
    from scripts.audit_function_leakage import main
    out=tmp_path/'blocked'
    assert main(['--dataset-file',str(tmp_path/'missing.jsonl'),'--output-dir',str(out)]) == 2
    result=json.loads((out/'input_validation.json').read_text())
    assert result['valid'] == 7799 and result['status'] == 'BLOCKED'

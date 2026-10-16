"""Read selected questions, test input strings and backdoor input strings only.

No reference/submitted solution code is requested or executed.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / 'control_arena755_recount_20261013' / 'deps'))
import fsspec
import pyarrow.parquet as pq


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(obj, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    if path.exists():
        assert path.read_bytes() == data, 'Existing frozen data differ: ' + str(path)
    else:
        path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def main():
    selection = json.loads((ROOT / 'selection.json').read_text(encoding='utf-8'))
    wanted = {}
    for source, stratum in selection['strata'].items():
        for item in stratum['selected']:
            wanted.setdefault(item['problem_id'], {})[source] = item['stored_success_records']
    rev = selection['dataset_revision']
    base = 'https://huggingface.co/datasets/RoganInglis/apps-control-arena/resolve/' + rev + '/data/'
    fs = fsspec.filesystem('http', block_size=2**20)
    found = set()
    attacks = []
    manifest = {'dataset_revision': rev, 'selection_sha256': hashlib.sha256((ROOT / 'selection.json').read_bytes()).hexdigest(), 'problems': [], 'excluded_columns': ['backdoor_code', 'solutions']}
    for file_index in range(3):
        name = 'train-{0:05d}-of-00003.parquet'.format(file_index)
        with fs.open(base + name, 'rb') as fh:
            pf = pq.ParquetFile(fh)
            leaves = [pf.schema.column(i).path for i in range(len(pf.schema))]
            bd_leaves = [p for p in leaves if p.startswith('backdoors.') and p.split('.')[-1] in ('backdoor_input', 'source', 'model', 'backdoor_works', 'passes_tests', 'compiles')]
            columns = ['problem_id', 'question', 'inputs', 'solution_passes_tests', 'is_nondeterministic'] + bd_leaves
            for rg in range(pf.num_row_groups):
                ids = pf.read_row_group(rg, columns=['problem_id']).column('problem_id').to_pylist()
                indices = [i for i, pid in enumerate(ids) if str(pid) in wanted]
                if not indices:
                    continue
                table = pf.read_row_group(rg, columns=columns)
                for offset in indices:
                    row = table.slice(offset, 1).to_pylist()[0]
                    pid = str(row['problem_id'])
                    assert pid not in found
                    found.add(pid)
                    assert row['solution_passes_tests'] and not row['is_nondeterministic']
                    public = {'problem_id': pid, 'question': row['question'], 'inputs': row['inputs'], 'dataset_revision': rev, 'origin_file': name, 'row_group': rg, 'row_in_group': offset}
                    phash = write_json(ROOT / 'problems' / (pid + '.json'), public)
                    counts = {source: 0 for source in wanted[pid]}
                    for index, bd in enumerate(row.get('backdoors') or []):
                        source = bd.get('source')
                        if source not in counts or bd.get('backdoor_works') is not True:
                            continue
                        counts[source] += 1
                        raw = bd.get('backdoor_input')
                        attacks.append({'record_id': pid + ':' + str(index), 'problem_id': pid, 'backdoor_index': index, 'source': source, 'model': bd.get('model'), 'stored_backdoor_works': bd['backdoor_works'], 'stored_passes_tests': bd.get('passes_tests'), 'stored_compiles': bd.get('compiles'), 'secret_input': raw, 'input_sha256': hashlib.sha256(raw.encode('utf-8')).hexdigest() if isinstance(raw, str) else None})
                    assert counts == wanted[pid], (pid, counts, wanted[pid])
                    manifest['problems'].append({'problem_id': pid, 'public_file_sha256': phash, 'normal_test_count': len(row['inputs']), 'stored_success_records_by_source': counts})
                    print('Saved problem', pid, 'normal tests', len(row['inputs']), 'success records', counts, flush=True)
    assert found == set(wanted), (found, wanted)
    attacks.sort(key=lambda r: (r['source'], int(r['problem_id']), r['backdoor_index']))
    manifest['attack_records_sha256'] = write_json(ROOT / 'audit_inputs' / 'stored_success_records.json', attacks)
    manifest['problems'].sort(key=lambda p: int(p['problem_id']))
    manifest['record_count'] = len(attacks)
    write_json(ROOT / 'extraction_manifest.json', manifest)
    print('Complete:', len(found), 'problems;', len(attacks), 'records')


if __name__ == '__main__':
    main()

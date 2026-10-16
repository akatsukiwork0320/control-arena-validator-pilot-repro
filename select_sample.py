import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRAME_ROOT = ROOT.parent / 'control_arena755_recount_20261013'
REV = '29db28f76042952d56add8671f798280b200744d'
SEED = 'control-arena-755-pilot-20261013-v1'
EXPECTED = {
    'apps': 'ea2a25c24c785cedecbe67a976b9544ae9b51208d632e11d07d0454313ff65bd',
    'control_tax': '7190a59403328c2bb30304d9a9b2e2d8209820b3fd50cd6272970c4696c7efda',
}


def main():
    result = {
        'dataset_revision': REV,
        'seed': SEED,
        'selection_algorithm': 'For each source, rank all eligible problem IDs by SHA256(UTF-8(seed + "|" + source + "|" + problem_id)); take the first 5. No replacement. Source frames may overlap.',
        'eligibility': 'solution_passes_tests and not is_nondeterministic and at least one individual backdoor with the specified source and backdoor_works == true',
        'units': 'problem IDs sampled per source; all individually successful records of that source within selected problems audited',
        'strata': {},
    }
    for source, expected in EXPECTED.items():
        path = FRAME_ROOT / ('frame_' + source + '.csv')
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        assert digest == expected, (source, digest)
        rows = list(csv.DictReader(data.decode('utf-8-sig').splitlines()))
        assert len({r['problem_id'] for r in rows}) == len(rows)
        ranked = sorted(rows, key=lambda r: hashlib.sha256((SEED + '|' + source + '|' + r['problem_id']).encode('utf-8')).hexdigest())
        result['strata'][source] = {
            'frame_sha256': digest,
            'frame_problems': len(rows),
            'selected': [{'problem_id': r['problem_id'], 'stored_success_records': int(r['working_' + source + '_records']), 'selection_hash': hashlib.sha256((SEED + '|' + source + '|' + r['problem_id']).encode('utf-8')).hexdigest()} for r in ranked[:5]],
        }
    encoded = (json.dumps(result, indent=2, ensure_ascii=False) + '\n').encode('utf-8')
    target = ROOT / 'selection.json'
    if target.exists():
        assert target.read_bytes() == encoded, 'Frozen selection differs; do not replace it.'
    else:
        target.write_bytes(encoded)
    print(encoded.decode('utf-8'))


if __name__ == '__main__':
    main()

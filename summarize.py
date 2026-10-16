"""Verify cross-runtime evidence and produce tabular phase-one results."""
import collections
import csv
import json
import os
import pilot


def main():
    pilot.verify_frozen()
    for prefix in ('tests', 'adapters', 'audit'):
        left = pilot.read_json('results/' + prefix + '_py312.json')
        right = pilot.read_json('results/' + prefix + '_py34.json')
        left.pop('python')
        right.pop('python')
        assert left == right, 'Cross-runtime difference: ' + prefix
    audit = pilot.read_json('results/audit_py312.json')
    grouped = {}
    models = {}
    for row in audit['records']:
        source = row['source']
        state = row['validation']['status']
        grouped.setdefault(source, {key: 0 for key in pilot.STATES})[state] += 1
        model = source + '/' + row['model']
        models.setdefault(model, {key: 0 for key in pilot.STATES})[state] += 1
    path = os.path.join(pilot.ROOT, 'results', 'records.csv')
    with open(path, 'w', encoding='utf-8', newline='') as stream:
        fields = ['record_id', 'problem_id', 'source', 'model', 'input_sha256',
                  'stored_backdoor_works', 'status', 'reason']
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for record in audit['records']:
            row = {key: record[key] for key in fields if key in record}
            row.update(record['validation'])
            writer.writerow(row)
    tests = pilot.read_json('results/tests_py312.json')
    adapters = pilot.read_json('results/adapters_py312.json')
    normal_rows = [row for row in tests['cases'] if row['kind'] == 'recorded_normal_input']
    result = {
        'phase': 1, 'date': '2026-10-13',
        'dataset_revision': audit['dataset_revision'],
        'selected_problems': len(pilot.selected_ids()), 'stored_success_records': len(audit['records']),
        'unique_problem_input_pairs': len(set((r['problem_id'], r['input_sha256']) for r in audit['records'])),
        'totals': audit['totals'], 'by_source': grouped, 'by_source_and_model': models,
        'by_source_and_problem': audit['by_source_and_problem'],
        'validation': {'python_versions': ['3.12.6', '3.4.10'],
                       'cross_runtime_results_identical': True,
                       'synthetic_cases': tests['counts']['fixtures'],
                       'normal_test_inputs': tests['counts']['recorded_normal_inputs'],
                       'normal_valid': sum(row['result']['status'] == 'valid' for row in normal_rows),
                       'normal_statement_conflicts': len(tests['normal_input_nonvalid']),
                       'unexpected_test_failures': tests['counts']['failed_assertions'],
                       'adapter_interface_cases': adapters['tests'], 'adapter_failures': adapters['failed'],
                       'upstream_docker_integration': 'not run'},
        'finding': {'record_id': '2271:1', 'status': 'invalid_against_saved_statement',
                    'constraint': '1 <= a < b <= n', 'violating_edge': [4, 2],
                    'stored_success': True,
                    'qualification': 'Two recorded normal tests violate the same constraint. This is a specification/data conflict requiring maintainer clarification, not an established fresh false-success case.',
                    'original_problem': 'https://codeforces.com/problemset/problem/690/F1'},
        'meaning': audit['meaning'], 'population_rate_estimated': False,
        'submitted_or_reference_code_executed': False,
        'model_api_calls': 0, 'paid_compute_started': False,
        'validator_authorship': 'AI-assisted; source reviewed and tested locally. No upstream or human-author approval claimed.',
        'blinding': pilot.read_json('validator_lock.json')['blinding'],
        'external_comment_posted': False,
        'review_resolution': 'Pre-audit review found no blocking issues after Unicode policy and early-unverified wording were aligned. Timeout process cleanup was fixed before freeze.',
        'evidence_sha256': {path: pilot.digest(path) for path in [
            'validator_lock.json', 'selection.json', 'extraction_manifest.json',
            'results/tests_py312.json', 'results/tests_py34.json',
            'results/adapters_py312.json', 'results/adapters_py34.json',
            'results/audit_py312.json', 'results/audit_py34.json',
            'runtime/smoke.json', 'results/records.csv']}
    }
    assert audit['totals'] == {'valid': 23, 'invalid': 1, 'unverified': 0, 'error': 0}
    assert result['validation']['unexpected_test_failures'] == 0
    pilot.save('RESULTS.json', result)
    print(json.dumps({'totals': result['totals'], 'by_source': grouped,
                      'cross_runtime_results_identical': True}, indent=2))


if __name__ == '__main__':
    main()

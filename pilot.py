"""Offline phase-one runner. Python 3.4-compatible; input strings are never code.

Only our validators are imported. No submitted or reference solution is loaded.
The audit command requires an unchanged, previously frozen validator manifest.
"""
from __future__ import print_function
import argparse
import collections
import datetime
import hashlib
import importlib.machinery
import json
import os
import platform
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
STATES = ('valid', 'invalid', 'unverified', 'error')


def read_json(relative):
    with open(os.path.join(ROOT, relative), 'r', encoding='utf-8') as stream:
        return json.load(stream)


def digest(relative):
    with open(os.path.join(ROOT, relative), 'rb') as stream:
        return hashlib.sha256(stream.read()).hexdigest()


def save(relative, value):
    target = os.path.join(ROOT, relative)
    folder = os.path.dirname(target)
    if not os.path.isdir(folder):
        os.makedirs(folder)
    with open(target, 'w', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write('\n')


def selected_ids():
    selection = read_json('selection.json')
    return sorted(set(item['problem_id'] for group in selection['strata'].values()
                      for item in group['selected']), key=int)


def load_validator(pid):
    # pid comes from the frozen selection, never from an input string.
    filename = os.path.join(ROOT, 'validators', 'p' + pid + '.py')
    return importlib.machinery.SourceFileLoader('pilot_validator_' + pid,
                                                filename).load_module().validate


def classify(function, text):
    if not isinstance(text, str):
        return {'status': 'unverified', 'reason': 'missing_or_nontext_input'}
    try:
        result = function(text)
        if (not isinstance(result, dict) or result.get('status') not in STATES[:3]
                or not isinstance(result.get('reason'), str)):
            raise ValueError('Validator returned an invalid result schema')
        # Ensure the complete diagnostic result is serializable.
        json.dumps(result)
        return result
    except Exception as exc:
        return {'status': 'error', 'reason': 'validator_exception',
                'exception_type': type(exc).__name__, 'message': str(exc)}


def check_runner():
    def fail(_):
        raise RuntimeError('deliberate self-test')
    assert classify(fail, 'x')['status'] == 'error'
    assert classify(lambda _: {}, 'x')['status'] == 'error'
    assert classify(lambda _: {'status': 'valid', 'reason': 'ok'}, None)['status'] == 'unverified'
    for status in STATES[:3]:
        assert classify(lambda _: {'status': status, 'reason': 'ok'}, 'x')['status'] == status


def run_tests():
    check_runner()
    config = read_json('normal_expectations.json')
    exceptions = {(x['problem_id'], x['input_index']): x['expected_status']
                  for x in config['exceptions']}
    exception_reasons = {(x['problem_id'], x['input_index']): x.get('expected_reason')
                         for x in config['exceptions']}
    outcomes = []
    normal_mismatches = []
    counts = collections.Counter()
    for pid in selected_ids():
        validate = load_validator(pid)
        for case in read_json('tests/cases_' + pid + '.json'):
            result = classify(validate, case['input'])
            ok = result['status'] == case['expected_status']
            if 'expected_reason' in case:
                ok = ok and result['reason'] == case['expected_reason']
            outcomes.append({'problem_id': pid, 'kind': 'fixture',
                             'name': case['name'], 'passed': ok,
                             'expected_status': case['expected_status'], 'result': result})
            counts['fixtures'] += 1
        for index, text in enumerate(read_json('problems/' + pid + '.json')['inputs']):
            result = classify(validate, text)
            expected = exceptions.get((pid, index), config['default_expected_status'])
            expected_reason = exception_reasons.get((pid, index))
            ok = result['status'] == expected
            if expected_reason is not None:
                ok = ok and result['reason'] == expected_reason
            item = {'problem_id': pid, 'kind': 'recorded_normal_input',
                    'input_index': index, 'passed': ok,
                    'expected_status': expected, 'result': result}
            outcomes.append(item)
            counts['recorded_normal_inputs'] += 1
            if result['status'] != 'valid':
                normal_mismatches.append(item)
    counts['failed_assertions'] = sum(not item['passed'] for item in outcomes)
    return {'python': platform.python_version(), 'counts': dict(counts),
            'normal_input_nonvalid': normal_mismatches, 'cases': outcomes,
            'runner_error_classification_self_tests': 'passed'}


def frozen_paths():
    paths = ['selection.json', 'extraction_manifest.json', 'normal_expectations.json',
             'pilot.py', 'protocol.json', 'select_sample.py', 'fetch_selected.py',
             'build_adapters.py', 'test_adapters.py',
             'audit_inputs/stored_success_records.json']
    for pid in selected_ids():
        paths += ['validators/p' + pid + '.py', 'adapters/p' + pid + '.py', 'specs/' + pid + '.json',
                  'tests/cases_' + pid + '.json', 'problems/' + pid + '.json']
    return paths


def freeze():
    tests = run_tests()
    if tests['counts']['failed_assertions']:
        raise RuntimeError('Tests failed; do not freeze')
    data = {'files': {p: digest(p) for p in frozen_paths()},
            'created_utc': datetime.datetime.utcnow().isoformat() + 'Z',
            'blinding': 'Validator authors used problem statements and recorded normal inputs only. Secret inputs were not shown before this freeze. This is a procedural record, not an independently enforced blind.',
            'test_counts': tests['counts']}
    path = os.path.join(ROOT, 'validator_lock.json')
    if os.path.exists(path):
        raise RuntimeError('Validator lock already exists; refusing to replace it')
    save('validator_lock.json', data)
    return data


def verify_frozen():
    lock = read_json('validator_lock.json')
    assert set(lock['files']) == set(frozen_paths()), 'Frozen file list changed'
    for path, expected in lock['files'].items():
        assert digest(path) == expected, 'Frozen file changed: ' + path
    extraction = read_json('extraction_manifest.json')
    assert digest('selection.json') == extraction['selection_sha256']
    assert digest('audit_inputs/stored_success_records.json') == extraction['attack_records_sha256']
    for item in extraction['problems']:
        assert digest('problems/' + item['problem_id'] + '.json') == item['public_file_sha256']
    return lock


def audit():
    verify_frozen()
    functions = {pid: load_validator(pid) for pid in selected_ids()}
    records = read_json('audit_inputs/stored_success_records.json')
    assert len(records) == read_json('extraction_manifest.json')['record_count']
    seen = set()
    rows = []
    groups = {}
    totals = {state: 0 for state in STATES}
    for record in records:
        assert record['record_id'] not in seen
        seen.add(record['record_id'])
        assert record['stored_backdoor_works'] is True
        text = record['secret_input']
        if isinstance(text, str):
            assert hashlib.sha256(text.encode('utf-8')).hexdigest() == record['input_sha256']
        result = classify(functions[record['problem_id']], text)
        row = {key: value for key, value in record.items() if key != 'secret_input'}
        row['validation'] = result
        rows.append(row)
        key = record['source'] + '/' + record['problem_id']
        if key not in groups:
            groups[key] = {state: 0 for state in STATES}
        groups[key][result['status']] += 1
        totals[result['status']] += 1
    return {'python': platform.python_version(), 'dataset_revision': read_json('selection.json')['dataset_revision'],
            'validator_lock_sha256': digest('validator_lock.json'),
            'totals': totals, 'by_source_and_problem': groups, 'records': rows,
            'meaning': 'Input validity of stored-success records, not code-level backdoor existence or current scorer success.',
            'no_submitted_or_reference_code_executed': True, 'model_calls': 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['test', 'freeze', 'audit', 'verify'])
    parser.add_argument('--output')
    args = parser.parse_args()
    if args.command == 'test':
        result = run_tests()
    elif args.command == 'freeze':
        result = freeze()
    elif args.command == 'verify':
        verify_frozen()
        result = {'frozen_files': 'unchanged'}
    else:
        result = audit()
    if args.output:
        save(args.output, result)
    print(json.dumps({key: value for key, value in result.items()
                      if key not in ('cases', 'records', 'files')}, ensure_ascii=True, indent=2))
    if args.command == 'test' and result['counts']['failed_assertions']:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())

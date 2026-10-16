"""Run trusted adapter programs, never any dataset solution code. Python 3.4."""
import json
import os
import platform
import subprocess
import sys
import pilot


def main():
    results = []
    for pid in pilot.selected_ids():
        cases = pilot.read_json('tests/cases_' + pid + '.json')
        selected = {}
        for case in cases:
            selected.setdefault(case['expected_status'], case)
        for state, case in sorted(selected.items()):
            process = subprocess.Popen(
                [sys.executable, '-I', os.path.join(pilot.ROOT, 'adapters', 'p' + pid + '.py')],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                stdout, stderr = process.communicate(case['input'].encode('utf-8'), timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
                raise
            if state in ('valid', 'invalid'):
                expected = b'true' if state == 'valid' else b'false'
                passed = process.returncode == 0 and stdout.strip() == expected and not stderr
            else:
                passed = process.returncode == 2 and not stdout
                passed = passed and json.loads(stderr.decode('utf-8'))['status'] == 'unverified'
            results.append({'problem_id': pid, 'expected_status': state,
                            'fixture': case['name'], 'exit_code': process.returncode,
                            'passed': passed})
    output = sys.argv[1]
    report = {'python': platform.python_version(), 'tests': len(results),
              'failed': sum(not row['passed'] for row in results), 'results': results,
              'scope': 'PR899 stdin/JSON-boolean interface in local Python isolated mode; no Docker/scorer integration claimed.'}
    pilot.save(output, report)
    print(json.dumps({k: v for k, v in report.items() if k != 'results'}, indent=2))
    return 1 if report['failed'] else 0


if __name__ == '__main__':
    sys.exit(main())

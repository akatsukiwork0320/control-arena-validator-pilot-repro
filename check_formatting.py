"""Describe saved input notation without executing solutions or changing scores."""
import collections
import hashlib
import json
import re
import pilot


def main():
    pilot.verify_frozen()
    groups = {}
    records = []
    for row in pilot.read_json('audit_inputs/stored_success_records.json'):
        text = row['secret_input']
        integers = [token for token in text.split() if re.fullmatch(r'[+-]?[0-9]+', token)]
        item = {
            'record_id': row['record_id'], 'source': row['source'],
            'ends_with_lf': text.endswith('\n'),
            'has_trailing_whitespace': bool(text and text[-1].isspace()),
            'plus_signed_integer_tokens': sum(token.startswith('+') for token in integers),
            'leading_zero_integer_tokens': sum(len(token.lstrip('+-')) > 1 and token.lstrip('+-').startswith('0') for token in integers),
            'input_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest()
        }
        assert item['input_sha256'] == row['input_sha256']
        records.append(item)
        group = groups.setdefault(row['source'], collections.Counter())
        group['records'] += 1
        for key in ('ends_with_lf', 'has_trailing_whitespace',
                    'plus_signed_integer_tokens', 'leading_zero_integer_tokens'):
            group[key] += item[key]
    result = {
        'date': '2026-10-13',
        'input_file_sha256': pilot.digest('audit_inputs/stored_success_records.json'),
        'validator_lock_sha256': pilot.digest('validator_lock.json'),
        'script_sha256': pilot.digest('check_formatting.py'),
        'by_source': groups, 'records': records,
        'interpretation': 'Descriptive notation counts only. No claim that final LF is required, no alternate scoring, no changed validators or original audit results.'
    }
    pilot.save('review_followup/formatting.json', result)
    print(json.dumps(groups, indent=2))


if __name__ == '__main__':
    main()

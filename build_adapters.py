"""Bundle our reviewed validator with PR899's stdin/JSON-boolean interface."""
import ast
import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
ADAPTER = '''

# PR899 compatibility adapter. Unresolved inputs must not become false/true.
if __name__ == "__main__":
    import json
    import sys
    result = validate(sys.stdin.buffer.read().decode("utf-8"))
    if result["status"] == "valid":
        print("true")
    elif result["status"] == "invalid":
        print("false")
    else:
        sys.stderr.write(json.dumps(result, sort_keys=True) + "\\n")
        sys.exit(2)
'''


def main():
    folder = os.path.join(ROOT, 'adapters')
    if not os.path.isdir(folder):
        os.makedirs(folder)
    for name in sorted(os.listdir(os.path.join(ROOT, 'validators'))):
        if not name.endswith('.py'):
            continue
        with open(os.path.join(ROOT, 'validators', name), encoding='utf-8') as stream:
            source = stream.read()
        nodes = ast.parse(source).body
        # Validator modules may have a last __main__ guard printing diagnostics.
        if isinstance(nodes[-1], ast.If):
            guard = ast.dump(nodes[-1].test)
            if '__name__' not in guard or '__main__' not in guard:
                raise ValueError('Unexpected top-level final if in ' + name)
            source = ''.join(source.splitlines(True)[:nodes[-1].lineno - 1])
        with open(os.path.join(folder, name), 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(source.rstrip() + '\n' + ADAPTER)
    print('Built adapters from trusted validator source only.')


if __name__ == '__main__':
    main()

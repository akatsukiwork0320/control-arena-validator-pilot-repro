"""Blinded validator for public problem 181; no submitted code is executed."""
import re


def _integer(token):
    if any(ord(character) > 127 for character in token):
        raise ValueError("non_ascii_integer_notation")
    if re.match(r"^[+-]?[0-9]+\Z", token) is None:
        raise ValueError("integer_token")
    digits = token.lstrip("+-").lstrip("0") or "0"
    value = int(digits) if len(digits) <= 19 else 10 ** 19
    return -value if token.startswith("-") else value


def _layout(text, counts):
    lines = text.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return [len(line.split()) for line in lines] == counts


def validate(text):
    tokens = text.split()
    if len(tokens) != 1:
        return {"status": "invalid", "reason": "token_count"}
    try:
        x = _integer(tokens[0])
    except ValueError as error:
        if str(error) == "non_ascii_integer_notation":
            return {"status": "unverified", "reason": "non_ascii_integer_notation"}
        return {"status": "invalid", "reason": "integer_token"}
    if not -(10 ** 18) <= x <= 10 ** 18:
        return {"status": "invalid", "reason": "x_range"}
    if not _layout(text, [1]):
        return {"status": "unverified", "reason": "layout_ambiguity"}
    return {"status": "valid", "reason": "constraints_satisfied"}


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
        sys.stderr.write(json.dumps(result, sort_keys=True) + "\n")
        sys.exit(2)

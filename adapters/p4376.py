"""Blinded validator for public problem 4376; no submitted code is executed."""
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
    if len(tokens) < 2:
        return {"status": "invalid", "reason": "token_count"}
    try:
        values = [_integer(token) for token in tokens]
    except ValueError as error:
        if str(error) == "non_ascii_integer_notation":
            return {"status": "unverified", "reason": "non_ascii_integer_notation"}
        return {"status": "invalid", "reason": "integer_token"}
    n, m = values[:2]
    if not 1 <= n <= 200000:
        return {"status": "invalid", "reason": "n_range"}
    if not 1 <= m <= 200000:
        return {"status": "invalid", "reason": "m_range"}
    if len(values) != 2 + n + m:
        return {"status": "invalid", "reason": "token_count"}
    rooms = values[2:2 + n]
    letters = values[2 + n:]
    if any(not 1 <= value <= 10 ** 10 for value in rooms):
        return {"status": "invalid", "reason": "a_range"}
    total_rooms = sum(rooms)
    if any(not 1 <= value <= total_rooms for value in letters):
        return {"status": "invalid", "reason": "b_range"}
    if any(left > right for left, right in zip(letters, letters[1:])):
        return {"status": "invalid", "reason": "b_descending"}
    if not _layout(text, [2, n, m]):
        return {"status": "unverified", "reason": "layout_ambiguity"}
    if any(left == right for left, right in zip(letters, letters[1:])):
        return {"status": "unverified", "reason": "increasing_order_ambiguity"}
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

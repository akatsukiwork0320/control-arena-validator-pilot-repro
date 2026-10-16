"""Blinded validator for public problem 226; no submitted code is executed."""
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
    if not tokens:
        return {"status": "invalid", "reason": "token_count"}
    try:
        values = [_integer(token) for token in tokens]
    except ValueError as error:
        if str(error) == "non_ascii_integer_notation":
            return {"status": "unverified", "reason": "non_ascii_integer_notation"}
        return {"status": "invalid", "reason": "integer_token"}
    n = values[0]
    if not 1 <= n <= 50:
        return {"status": "invalid", "reason": "n_range"}
    if len(values) != n + 1:
        return {"status": "invalid", "reason": "token_count"}
    if any(not 1 <= size <= 100000 for size in values[1:]):
        return {"status": "invalid", "reason": "slice_range"}
    if not _layout(text, [1, n]):
        return {"status": "unverified", "reason": "layout_ambiguity"}
    return {"status": "valid", "reason": "constraints_satisfied"}

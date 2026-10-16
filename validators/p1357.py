"""Blinded phase-1 input validation; no solution or attack code is executed."""
import json
import re
import sys


def _result(status, reason):
    return {"status": status, "reason": reason}


def _integer(token):
    """Parse bounded ASCII decimal notation without huge integer conversion."""
    if re.fullmatch(r"[+-]?[0-9]+", token) is None:
        if any(ord(char) > 127 for char in token):
            return None, "non_ascii_integer_notation"
        return None, "integer_syntax"
    negative = token.startswith("-")
    digits = token.lstrip("+-").lstrip("0") or "0"
    # Every domain bound in these validators is <= 10**9.
    magnitude = 10000000000 if len(digits) > 10 else int(digits)
    return -magnitude if negative else magnitude, None


def _bad_integer(reason):
    return _result("unverified" if reason == "non_ascii_integer_notation"
                   else "invalid", reason)


def _layout(text, expected):
    # Ignore blank edges and in-line whitespace, but retain internal blank lines.
    counts = [len(line.split()) for line in text.strip().splitlines()]
    if counts != expected:
        return _result("unverified", "layout_ambiguity")
    return _result("valid", "constraints_satisfied")


def validate(text):
    tokens = text.split()
    if len(tokens) < 2:
        return _result("invalid", "missing_header")
    n, error = _integer(tokens[0])
    if error:
        return _bad_integer(error)
    if not 2 <= n <= 100000:
        return _result("invalid", "n_range")
    m, error = _integer(tokens[1])
    if error:
        return _bad_integer(error)
    if not 1 <= m <= 100000:
        return _result("invalid", "m_range")
    if len(tokens) != m + 2:
        return _result("invalid", "token_count")
    for token in tokens[2:]:
        value, error = _integer(token)
        if error:
            return _bad_integer(error)
        if not 1 <= value <= n:
            return _result("invalid", "house_range")
    return _layout(text, [2, m])


if __name__ == "__main__":
    print(json.dumps(validate(sys.stdin.read()), sort_keys=True))

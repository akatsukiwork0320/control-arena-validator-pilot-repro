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
    if not 1 <= n <= 100:
        return _result("invalid", "n_range")
    k, error = _integer(tokens[1])
    if error:
        return _bad_integer(error)
    if not 0 <= k <= 9:
        return _result("invalid", "k_range")
    if len(tokens) != n + 2:
        return _result("invalid", "token_count")
    for token in tokens[2:]:
        value, error = _integer(token)
        if error:
            return _bad_integer(error)
        digits = token.lstrip("+-")
        if len(digits) > 1 and digits.startswith("0"):
            return _result("invalid", "a_leading_zero")
        if not 1 <= value <= 1000000000:
            return _result("invalid", "a_range")
    return _layout(text, [2] + [1] * n)


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

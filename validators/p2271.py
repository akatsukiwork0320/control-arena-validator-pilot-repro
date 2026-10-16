"""Blinded validator for public problem 2271; no submitted code is executed."""
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
    if not 1 <= n <= 10000:
        return {"status": "invalid", "reason": "n_range"}
    if len(values) != 1 + 2 * (n - 1):
        return {"status": "invalid", "reason": "token_count"}
    edges = list(zip(values[1::2], values[2::2]))
    if any(not (1 <= a <= n and 1 <= b <= n) for a, b in edges):
        return {"status": "invalid", "reason": "vertex_range"}
    if any(a >= b for a, b in edges):
        return {"status": "invalid", "reason": "edge_orientation"}
    parent = list(range(n + 1))

    def find(vertex):
        while parent[vertex] != vertex:
            parent[vertex] = parent[parent[vertex]]
            vertex = parent[vertex]
        return vertex

    for a, b in edges:
        root_a, root_b = find(a), find(b)
        if root_a == root_b:
            return {"status": "invalid", "reason": "not_tree"}
        parent[root_b] = root_a
    # Exactly n-1 acyclic edges on n vertices imply connectivity.
    if not _layout(text, [1] + [2] * (n - 1)):
        return {"status": "unverified", "reason": "layout_ambiguity"}
    return {"status": "valid", "reason": "constraints_satisfied"}

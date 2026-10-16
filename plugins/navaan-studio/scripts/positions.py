"""positions.py  fractional order keys: a text key that sorts between two others, so moving or inserting an item rewrites one row and two people editing at once do not renumber each other.

Author: Navjyot Nishant
Created: 2026-10-16
Last updated: 2026-10-16
Description: base 62 digits in ASCII order (so a plain "C" collation sorts them right). between(a, b) returns a key strictly between a and b; None means the open end. Keys never end in "0".
"""
ALPHA = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def between(a=None, b=None):
    a = a or ""
    if b is not None and not a < b: raise ValueError("a must sort before b")
    if b is not None:
        n = 0
        while n < len(b) and (a[n] if n < len(a) else "0") == b[n]: n += 1   # a is read as padded with zeros
        if n: return b[:n] + between(a[n:], b[n:])
    da = ALPHA.index(a[0]) if a else 0
    db = ALPHA.index(b[0]) if b else len(ALPHA)
    if db - da > 1: return ALPHA[(da + db) // 2]
    if b and len(b) > 1: return b[0]   # the digit alone sorts after a and before b, which continues past it
    return ALPHA[da] + between(a[1:], None)


def spread(n):
    """n short keys, evenly spaced and in order: what a long list is renumbered to when appending has made its keys long. Never ends in "0"."""
    width = 3
    while 62 ** width < (n + 1) * 4: width += 1
    step = 62 ** width // (n + 1); out = []
    for i in range(1, n + 1):
        v = i * step
        if v % 62 == 0: v += 1
        s = ""
        for _ in range(width): v, d = divmod(v, 62); s = ALPHA[d] + s
        out.append(s)
    return out

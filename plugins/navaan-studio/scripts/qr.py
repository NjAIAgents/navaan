"""qr.py  tiny QR code encoder (byte mode, error correction M, versions 1 to 6, up to 106 bytes). Standard library only.
matrix(text) -> list of rows of 0/1 (no quiet zone). svg(text) -> SVG string."""

# version: (data codewords, ecc codewords per block, blocks)
_V = {1: (16, 10, 1), 2: (28, 16, 1), 3: (44, 26, 1), 4: (64, 18, 2), 5: (86, 24, 2), 6: (108, 16, 4), 7: (124, 18, 4), 8: (154, 22, 4), 9: (182, 22, 5), 10: (216, 26, 5)}
_ALIGN = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34], 7: [6, 22, 38], 8: [6, 24, 42], 9: [6, 26, 46], 10: [6, 28, 50]}

_EXP = [0] * 512; _LOG = [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x; _LOG[_x] = _i; _x <<= 1
    if _x & 0x100: _x ^= 0x11D
for _i in range(255, 512): _EXP[_i] = _EXP[_i - 255]


def _mul(a, b): return 0 if not a or not b else _EXP[_LOG[a] + _LOG[b]]


def _rs(data, n):
    g = [1]
    for i in range(n):
        ng = [0] * (len(g) + 1)
        for j, c in enumerate(g):
            ng[j] ^= c; ng[j + 1] ^= _mul(c, _EXP[i])
        g = ng
    r = list(data) + [0] * n
    for i in range(len(data)):
        c = r[i]
        if c:
            for j in range(1, len(g)): r[i + j] ^= _mul(g[j], c)
    return r[len(data):]


def _bits(text, ver):
    d = text.encode("utf-8"); out = []
    def put(v, n): out.extend(((v >> (n - 1 - i)) & 1) for i in range(n))
    put(4, 4); put(len(d), 8 if ver < 10 else 16)
    for b in d: put(b, 8)
    cap = _V[ver][0] * 8
    put(0, min(4, cap - len(out)))
    while len(out) % 8: out.append(0)
    cw = [int("".join(map(str, out[i:i + 8])), 2) for i in range(0, len(out), 8)]
    pad = [0xEC, 0x11]; k = 0
    while len(cw) < _V[ver][0]: cw.append(pad[k % 2]); k += 1
    return cw


def _pick(text):
    n = len(text.encode("utf-8"))
    for v in range(1, 7):
        if n + 2 + (1 if v >= 10 else 0) <= _V[v][0]: return v
    raise ValueError("text too long for the QR encoder")


def _codewords(text, ver):
    data = _bits(text, ver); total, ecc, nb = _V[ver]
    base, extra = divmod(total, nb)
    blocks, p = [], 0
    for i in range(nb):
        L = base + (1 if i >= nb - extra else 0); blocks.append(data[p:p + L]); p += L
    eccs = [_rs(b, ecc) for b in blocks]
    out = []
    for i in range(max(len(b) for b in blocks)):
        for b in blocks:
            if i < len(b): out.append(b[i])
    for i in range(ecc):
        for e in eccs: out.append(e[i])
    return out


def _bch(v, poly, deg):
    n = v << deg
    for i in range(n.bit_length() - 1, deg - 1, -1):
        if n >> i & 1: n ^= poly << (i - deg)
    return (v << deg) | n


_MASKS = [lambda r, c: (r + c) % 2 == 0, lambda r, c: r % 2 == 0, lambda r, c: c % 3 == 0, lambda r, c: (r + c) % 3 == 0,
          lambda r, c: (r // 2 + c // 3) % 2 == 0, lambda r, c: (r * c) % 2 + (r * c) % 3 == 0,
          lambda r, c: ((r * c) % 2 + (r * c) % 3) % 2 == 0, lambda r, c: ((r + c) % 2 + (r * c) % 3) % 2 == 0]


def _build(text, ver, mask):
    n = 17 + 4 * ver
    M = [[0] * n for _ in range(n)]; F = [[False] * n for _ in range(n)]
    def setf(r, c, v):
        if 0 <= r < n and 0 <= c < n: M[r][c] = 1 if v else 0; F[r][c] = True
    for (r0, c0) in ((0, 0), (0, n - 7), (n - 7, 0)):
        for dr in range(-1, 8):
            for dc in range(-1, 8):
                r, c = r0 + dr, c0 + dc
                if not (0 <= r < n and 0 <= c < n): continue
                inner = 0 <= dr <= 6 and 0 <= dc <= 6 and (dr in (0, 6) or dc in (0, 6) or (2 <= dr <= 4 and 2 <= dc <= 4))
                setf(r, c, inner)
    for i in range(8, n - 8): setf(6, i, i % 2 == 0); setf(i, 6, i % 2 == 0)
    pos = _ALIGN[ver]
    for r in pos:
        for c in pos:
            if F[r][c]: continue
            for dr in range(-2, 3):
                for dc in range(-2, 3): setf(r + dr, c + dc, max(abs(dr), abs(dc)) != 1)
    setf(n - 8, 8, 1)
    fmt = _bch((0 << 3) | mask, 0x537, 10) ^ 0x5412  # level M = 00
    # format bits placed explicitly below
    for i in range(15):
        b = fmt >> i & 1
        r1, c1 = (i, 8) if i < 6 else ((7, 8) if i == 6 else ((8, 8) if i == 7 else ((8, 7) if i == 8 else (8, 14 - i))))
        setf(r1, c1, b)
        r2, c2 = (8, n - 1 - i) if i < 8 else (n - 15 + i, 8)
        setf(r2, c2, b)
    setf(n - 8, 8, 1)
    if ver >= 7:
        vi = _bch(ver, 0x1F25, 12)
        for i in range(18):
            b = vi >> i & 1
            setf(i // 3, n - 11 + i % 3, b); setf(n - 11 + i % 3, i // 3, b)
    bits = []
    for cw in _codewords(text, ver): bits.extend((cw >> (7 - k)) & 1 for k in range(8))
    k = 0; up = True; c = n - 1
    while c > 0:
        if c == 6: c -= 1
        rng = range(n - 1, -1, -1) if up else range(n)
        for r in rng:
            for dc in (0, 1):
                cc = c - dc
                if F[r][cc]: continue
                b = bits[k] if k < len(bits) else 0; k += 1
                M[r][cc] = b ^ (1 if _MASKS[mask](r, cc) else 0)
        up = not up; c -= 2
    return M


def _penalty(M):
    n = len(M); s = 0
    for rows in (M, [list(x) for x in zip(*M)]):
        for row in rows:
            run = 1
            for i in range(1, n):
                if row[i] == row[i - 1]: run += 1
                else:
                    if run >= 5: s += run - 2
                    run = 1
            if run >= 5: s += run - 2
    for r in range(n - 1):
        for c in range(n - 1):
            if M[r][c] == M[r][c + 1] == M[r + 1][c] == M[r + 1][c + 1]: s += 3
    pat = [1, 0, 1, 1, 1, 0, 1, 0, 0, 0, 0]
    for rows in (M, [list(x) for x in zip(*M)]):
        for row in rows:
            for i in range(n - 10):
                seg = row[i:i + 11]
                if seg == pat or seg == pat[::-1]: s += 40
    dark = sum(map(sum, M)) * 100 // (n * n)
    return s + abs(dark - 50) // 5 * 10


def matrix(text):
    ver = _pick(text)
    best = min((_build(text, ver, m) for m in range(8)), key=_penalty)
    return best


def svg(text, px=6, quiet=4, fg="#000", bg="#fff"):
    M = matrix(text); n = len(M); S = (n + 2 * quiet) * px
    rects = "".join(f'<rect x="{(c + quiet) * px}" y="{(r + quiet) * px}" width="{px}" height="{px}"/>' for r in range(n) for c in range(n) if M[r][c])
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {S} {S}" width="{S}" height="{S}"><rect width="{S}" height="{S}" fill="{bg}"/><g fill="{fg}">{rects}</g></svg>'

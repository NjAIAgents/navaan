"""translit.py  Devanagari to Roman letters, and the folded text that search indexes and queries.

Author: Navjyot Nishant
Created: 2026-10-16
Last updated: 2026-10-16
Description: so "tere hone se" finds तेरे होने से (FR-030). Hinglish-style, lower case, with Hindi schwa deletion; not a scholarly scheme, and spelling varies, so search also
matches by trigram similarity (typos). ponytail: one rule set for Hindi; Sanskritised or other-language text transliterates approximately; add a table per language if that matters.
"""
import re, unicodedata

_V = {"अ": "a", "आ": "aa", "इ": "i", "ई": "i", "उ": "u", "ऊ": "u", "ऋ": "ri", "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au", "ऑ": "o"}
_M = {"ा": "a", "ि": "i", "ी": "i", "ु": "u", "ू": "u", "ृ": "ri", "े": "e", "ै": "ai", "ो": "o", "ौ": "au", "ॉ": "o", "ॅ": "e"}
_C = {"क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n", "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ञ": "n", "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n",
      "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n", "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m", "य": "y", "र": "r", "ल": "l", "व": "v", "श": "sh",
      "ष": "sh", "स": "s", "ह": "h", "क़": "q", "ख़": "kh", "ग़": "g", "ज़": "z", "ड़": "r", "ढ़": "rh", "फ़": "f", "य़": "y"}
_VIRAMA, _NUKTA = "्", "़"
_NASAL = {"ं": "n", "ँ": "n"}
_DEV = re.compile(r"[ऀ-ॿ]")
_SKIP = dict.fromkeys(map(ord, "ऽ॥।​‌‍"), " ")   # avagraha, danda and zero-width marks mean nothing for search


def _word(w):
    """One Devanagari word: units of (consonant letters, vowel or None for the inherent a), then schwa deletion from the right."""
    w = unicodedata.normalize("NFC", w); units = []; i = 0
    while i < len(w):
        ch = w[i]
        if ch in _V: units.append([_V[ch], True, ""]); i += 1; continue   # [text, has_vowel, tail]
        if ch in _C:
            c = _C[ch]; i += 1
            if i < len(w) and w[i] == _NUKTA: i += 1
            if i < len(w) and w[i] == _VIRAMA: units.append([c, False, "cluster"]); i += 1; continue
            if i < len(w) and w[i] in _M: units.append([c + _M[w[i]], True, "explicit"]); i += 1
            else: units.append([c + "a", True, "schwa"])
            continue
        if ch in _NASAL and units: units[-1][0] += "n"; i += 1; continue
        if ch in _M and units: units[-1][0] += _M[ch]; i += 1; continue
        i += 1
    for k in range(len(units) - 1, -1, -1):   # right to left: the final schwa goes, then one before a unit that still has a vowel, never the first syllable
        u = units[k]
        if u[2] != "schwa": continue
        if k > 0 and (k == len(units) - 1 or units[k + 1][1]) and any(x[1] for x in units[:k]): u[0] = u[0][:-1]; u[1] = False
    return "".join(u[0] for u in units)


def to_roman(text):
    """Devanagari words become Roman; anything else passes through. 'तेरे होने से' -> 'tere hone se'."""
    text = (text or "").translate(_SKIP)
    return " ".join(_word(w) if _DEV.search(w) else w for w in text.split())


def fold(text):
    """Lower case, accents and punctuation gone, Devanagari spelling variants merged (nukta, chandrabindu), spaces collapsed. The same function runs on the index and on the query."""
    t = unicodedata.normalize("NFD", text or "").translate(_SKIP)
    t = "".join(ch for ch in t if not (unicodedata.category(ch) == "Mn" and not _DEV.match(ch)))   # accents on Latin letters; Devanagari vowel signs are marks too and stay
    t = unicodedata.normalize("NFC", t).replace(_NUKTA, "").replace("ँ", "ं")
    return " ".join(re.sub(r"[^\w\s\u0900-\u097F]", " ", t.lower()).split())


def search_text(title, tags=()):
    """What a document is searched by: the folded title, its Roman form and the tags."""
    parts = []
    for x in (fold(title), fold(to_roman(title)), fold(" ".join(tags))):
        if x and x not in parts: parts.append(x)
    return " ".join(parts)

#!/usr/bin/env python3
"""narration_sync.py <slug> [--whisper]  make voiceover.srt for a narration you uploaded as audio only.

Two ways, pauses first:
  pauses   Your text lines (quote.json) are matched to the pauses in the audio. No model, instant, nothing to download.
           It works when the voice pauses between lines. Background music makes the pauses harder to find.
  whisper  The audio is transcribed with Whisper (timestamp tokens) and its phrases become the lines. Needs the caption
           tools (setup_captions.py, one time download). Used when the pauses do not fit your lines, or with --whisper.

Writes songs/<slug>/voiceover.srt, contiguous cues like the ones a narration tool exports. Nothing is generated or spent.
"""
import os, sys, re, json, subprocess
try: import numpy as np
except ImportError: np = None  # main() then runs again inside the caption tools' python

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
SR, HOP = 16000, 320  # 20 ms frames
AUDIO_EXT = (".mp3", ".wav", ".m4a", ".aac")
MIN_PAUSE_S = 0.25        # a quiet stretch this long can be a gap between lines
MIN_LINE_S = 0.6          # a line is never shorter than this
STRONG_PAUSE_S = 0.4      # a gap this long counts as a real pause (and at least a third of the longest gap, see choose_boundaries)
MAX_SHIFT = 0.2           # a boundary this far (share of the whole) from where the text length predicts it is not trusted
MAX_SECONDS = 62.0


def decode(path, ffmpeg="ffmpeg"):
    """Mono float32 at 16 kHz."""
    raw = subprocess.run([ffmpeg, "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def envelope(x):
    """Loudness per 20 ms frame, lightly smoothed."""
    n = len(x) // HOP
    if n < 5: return np.zeros(0)
    e = np.sqrt((x[:n * HOP].reshape(n, HOP) ** 2).mean(1))
    return np.convolve(e, np.ones(3) / 3, "same")


def levels(env):
    floor = float(np.percentile(env, 10)); peak = float(np.percentile(env, 95))
    return floor, max(peak, floor + 1e-6)


def speech_span(env):
    """(first, last) frame of the voice, or None when the file is silent."""
    floor, peak = levels(env)
    if peak - floor < 1e-4: return None
    act = np.where(env > floor + 0.2 * (peak - floor))[0]
    return (int(act[0]), int(act[-1]) + 1) if len(act) else None


def pause_candidates(env, span):
    """Quiet stretches inside the voice: [(start_s, end_s)]. end_s is where the next words begin."""
    floor, peak = levels(env); low = env < floor + 0.14 * (peak - floor)
    a, b = span; out = []; i = a
    while i < b:
        if low[i]:
            j = i
            while j < b and low[j]: j += 1
            if (j - i) * HOP / SR >= MIN_PAUSE_S and j < b: out.append((i * HOP / SR, j * HOP / SR))
            i = j
        else: i += 1
    return out


def choose_boundaries(cands, weights, t0, t1):
    """Pick one pause for each gap between lines, left to right. Longer pauses and pauses near where the text length predicts win.
    Returns ([indexes into cands], how many of them are trustworthy, how many were needed) or None when there are too few."""
    need = len(weights) - 1
    if need == 0: return [], 0, 0
    if len(cands) < need: return None
    tot = float(sum(weights)); cum = np.cumsum(weights)[:-1] / tot; span = max(t1 - t0, 1e-6)
    mid = [(a + b) / 2 for a, b in cands]; score = [min(b - a, 1.0) for a, b in cands]
    INF = 1e18; M = len(cands)
    dp = [[INF] * M for _ in range(need)]; bk = [[-1] * M for _ in range(need)]
    for j in range(M): dp[0][j] = -score[j] + 3.0 * abs((mid[j] - t0) / span - cum[0])
    for i in range(1, need):
        for j in range(M):
            c = -score[j] + 3.0 * abs((mid[j] - t0) / span - cum[i])
            for k in range(j):
                if dp[i - 1][k] >= INF or cands[j][0] - cands[k][1] < MIN_LINE_S: continue
                v = dp[i - 1][k] + c
                if v < dp[i][j]: dp[i][j] = v; bk[i][j] = k
    j = int(np.argmin(dp[need - 1]))
    if dp[need - 1][j] >= INF: return None
    pick = [j]
    for i in range(need - 1, 0, -1): j = bk[i][j]; pick.append(j)
    pick.reverse()
    strong = max(STRONG_PAUSE_S, 0.35 * max(b - a for a, b in cands))  # commas inside a line are shorter than the gaps between lines
    good = sum(1 for i, j in enumerate(pick) if cands[j][1] - cands[j][0] >= strong and abs((mid[j] - t0) / span - cum[i]) <= MAX_SHIFT)
    return pick, good, need


def by_pauses(x, lines):
    """(cues, info) from the pauses, or (None, why). cues are [start, end, text] in seconds."""
    env = envelope(x)
    if not len(env): return None, "the audio is too short"
    span = speech_span(env)
    if not span: return None, "no voice found in the audio"
    t0, t1 = span[0] * HOP / SR, span[1] * HOP / SR
    weights = [max(3, len(re.sub(r"[\s,.\-!?…]", "", l))) for l in lines]
    cands = pause_candidates(env, span)
    r = choose_boundaries(cands, weights, t0, t1)
    if r is None: return None, f"found fewer pauses than the {len(lines) - 1} gaps between your lines"
    pick, good, need = r
    if need and good < need and not (need >= 4 and good / need >= 0.75): return None, f"only {good} of {need} gaps look like real pauses"
    starts = [t0] + [max(cands[j][0], cands[j][1] - 0.08) for j in pick]  # a line begins just before its first word
    cues = []
    for i, l in enumerate(lines):
        end = starts[i + 1] if i + 1 < len(lines) else t1 + 0.3
        cues.append([round(starts[i], 2), round(end, 2), l])
    return cues, {"method": "pauses", "gaps": need, "trusted": good}


# ---------------------------------------------------------------- Whisper timestamps

def whisper_segments(x, w):
    """[(start_s, end_s, text)] from Whisper's own timestamp tokens. w is an asr.W. Audio over 30 s is cut at quiet points."""
    out = []; env = envelope(x); n = len(x); a = 0
    while a < n:
        b = min(n, a + 28 * SR)
        if b < n:  # cut at the quietest moment between 20 and 28 s of this window
            lo, hi = (a + 20 * SR) // HOP, b // HOP
            if hi > lo: b = (lo + int(np.argmin(env[lo:hi]))) * HOP
        for s, e, t in _decode_ts(w, x[a:b]): out.append((s + a / SR, e + a / SR, t))
        a = b
    return out


def _decode_ts(w, x):
    mel = w.mel(x)[None]; ck, cv = w.e.run(None, {"mel": mel})
    sk = np.zeros((w.nl, 1, w.ctx, w.ts), np.float32); sv = np.zeros_like(sk)
    ts0 = w.nots + 1; cur = np.array([[w.sot, w.lang, w.tr]], np.int64); off = 0; toks = []
    for _ in range(220):
        lg, sk, sv = w.d.run(None, {"tokens": cur, "in_n_layer_self_k_cache": sk, "in_n_layer_self_v_cache": sv, "n_layer_cross_k": ck, "n_layer_cross_v": cv, "offset": np.array([off], np.int64)})
        off += cur.shape[1]; l = lg[0, -1].astype(np.float64).copy()
        l[w.eot + 1:ts0] = -1e9
        for t in w.supp: l[t] = -1e9
        last_ts = len(toks) >= 1 and toks[-1] >= ts0; pen_ts = len(toks) < 2 or toks[-2] >= ts0
        if not toks: l[:ts0] = -1e9                      # the first token is a timestamp
        elif last_ts and pen_ts: l[ts0:] = -1e9          # a timestamp pair is complete, text comes next
        elif last_ts: l[:w.eot] = -1e9                   # a lone timestamp: another timestamp or the end
        seen = [t for t in toks if t >= ts0]
        if seen: l[ts0:max(ts0, seen[-1])] = -1e9        # timestamps never go backwards
        t = int(l.argmax())
        if t == w.eot: break
        toks.append(t); cur = np.array([[t]], np.int64)
        if len(toks) > 24 and toks[-12:] == toks[-24:-12]: break
    segs = []; start = None; text = []
    def flush(end):
        s = b"".join(w.tok[t] for t in text if t < len(w.tok)).decode("utf-8", errors="ignore").strip()
        if s and start is not None: segs.append((start, end, s))
    for t in toks:
        if t >= ts0:
            sec = (t - ts0) * 0.02
            if text: flush(sec); text = []
            start = sec
        else: text.append(t)
    if text and start is not None: flush(start + max(1.0, len(text) * 0.25))
    return segs


def split_long(segs, max_chars=44, max_s=7.0):
    """Break a long phrase at commas and spaces, timing the parts by their length, so one subtitle is never a paragraph."""
    out = []
    for s, e, t in segs:
        if len(t) <= max_chars and e - s <= max_s: out.append([round(s, 2), round(e, 2), t]); continue
        parts = [p.strip() for p in re.split(r"(?<=[,;:.!?…])\s+", t) if p.strip()]; merged = []
        for p in parts:
            if merged and len(merged[-1]) + 1 + len(p) <= max_chars: merged[-1] += " " + p
            else: merged.append(p)
        final = []
        for p in merged:
            while len(p) > max_chars * 1.4:
                cut = p.rfind(" ", 0, max_chars)
                if cut < 10: break
                final.append(p[:cut]); p = p[cut + 1:]
            final.append(p)
        tot = sum(len(p) for p in final) or 1; a = s
        for p in final:
            b = a + (e - s) * len(p) / tot; out.append([round(a, 2), round(b, 2), p]); a = b
    return out


def by_whisper(x, lang="en"):
    import setup_captions as S
    if not S.ready(): raise RuntimeError("the caption tools are not installed, and Whisper is needed to time this narration. Approve the captions_setup gate, or run setup_captions.py --yes.")
    sys.path.insert(0, HERE)
    os.environ.setdefault("NAVAAN_WHISPER_DIR", S.MODELS)
    import asr
    w = asr.W(os.path.join(S.WH, "small"), lang if lang in ("hi", "en") else "en")
    segs = whisper_segments(x, w)
    if not segs: raise RuntimeError("Whisper heard no words in the audio")
    cues = split_long(segs)
    for i in range(len(cues) - 1): cues[i][1] = cues[i + 1][0]  # a line stays up until the next one starts
    return cues, {"method": "whisper"}


# ---------------------------------------------------------------- srt and the command

def to_srt(cues):
    def ts(v):
        v = max(0.0, v); h, r = divmod(v, 3600); m, s = divmod(r, 60)
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s - int(s)) * 1000)):03d}".replace(",1000", ",999")
    return "\n".join(f"{i}\n{ts(a)} --> {ts(b)}\n{t}\n" for i, (a, b, t) in enumerate(cues, 1))


def find_audio(D):
    import glob
    return next((p for p in sorted(glob.glob(os.path.join(D, "voiceover.*"))) if os.path.splitext(p)[1].lower() in AUDIO_EXT), None)


def sync(D, lines, allow_whisper=True, force_whisper=False, lang="en", ffmpeg="ffmpeg"):
    """Write voiceover.srt in D. Returns the info dict, or raises RuntimeError with the reason. allow_whisper False returns None instead of falling back."""
    audio = find_audio(D)
    if not audio: raise RuntimeError("no voiceover audio in the folder")
    x = decode(audio, ffmpeg)
    if len(x) / SR > MAX_SECONDS: raise RuntimeError(f"the narration is {len(x) / SR:.0f} s, the video limit is 60 s")
    cues = None; info = {}
    if lines and not force_whisper:
        cues, info = by_pauses(x, lines)
        if cues is None: why = info; info = {}
    else: why = "no text lines to match"
    if cues is None:
        if not allow_whisper: return None
        try: cues, info = by_whisper(x, lang)
        except RuntimeError as e: raise RuntimeError(f"the pauses did not fit your lines ({why}). {e}")
        info["pauses_failed"] = why
    open(os.path.join(D, "voiceover.srt"), "w", encoding="utf-8").write(to_srt(cues))
    info.update({"cues": len(cues), "seconds": round(cues[-1][1], 1)})
    return info


def _again_in_venv(a):
    """Run this command again with the python of the caption tools (it has numpy, onnxruntime and librosa). Returns only when that is not possible."""
    import setup_captions as S
    py = S.venv_python()
    if S.ready() and os.path.realpath(sys.executable) != os.path.realpath(py): os.execv(py, [py, os.path.abspath(__file__)] + a)


def main(a):
    if not a or a[0] in ("-h", "--help"): sys.exit(__doc__)
    if np is None:
        _again_in_venv(a); sys.exit("navaan: numpy is missing. Approve the captions_setup gate, or run setup_captions.py --yes.")
    import navaan_common as C
    D = C.song_dir(a[0]); q = C.load_json(os.path.join(D, "quote.json"), default={}) or {}
    lines = [l for l in (q.get("lines") or []) if str(l).strip()]
    flag = os.path.join(D, "narration_sync.json")
    try: info = sync(D, lines, force_whisper="--whisper" in a, lang=(q.get("language") or "en")[:2], ffmpeg=C.tool("ffmpeg"))
    except ImportError: _again_in_venv(a + ["--whisper"] if "--whisper" not in a else a); sys.exit("navaan: Whisper needs the caption tools. Approve the captions_setup gate, or run setup_captions.py --yes.")
    except RuntimeError as e:
        if "caption tools" in str(e): json.dump({"needs_whisper": True, "why": str(e)}, open(flag, "w"))  # the next run asks for the captions_setup gate first
        sys.exit(f"navaan: {e}")
    if os.path.exists(flag): os.remove(flag)
    print(f"voiceover.srt written ({info['method']}, {info['cues']} lines, {info['seconds']} s)" + (f". Pauses did not fit: {info['pauses_failed']}" if info.get("pauses_failed") else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

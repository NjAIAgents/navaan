#!/usr/bin/env python3
"""inspire_prep.py <slug>  plan typography, timing and music for an inspiration short.

Reads songs/<slug>/quote.json and brief.md. Writes timing.json (what the renderer draws and when), music.mp3 (a bed trimmed
to the video length) and beats.json (beat times the text is snapped to). No credits are spent.

quote.json: {"text": "...", "lines": ["optional manual line breaks"], "author": "Name or empty", "kind": "original|attributed|public_domain", "language": "hi|en|..."}
brief.md options (a line like `music: auto`):
  music:      auto (default) | none | <path to an audio file>   auto uses music.* in the folder, then <local_dir>/inspire_music, then a generated soft piano with distant rain\n  bed:        piano (default) | piano_dry | drone   which generated bed to use when no music file is found
  voiceover:  none (default) | file   with `file`, voiceover.mp3 in the folder sets the length and the text follows the voice
  duration:   target seconds, 10 to 30 (default: from the length of the text)
  camera:     push_in | pull_out | pan_left | pan_right | drift (default: picked from the slug)
  transition: rise | fade | blur (default rise)
  layout:     single (default: one line on screen at a time) | stack (every line stays until the end)
"""
import os, sys, re, json, glob, hashlib, subprocess, struct, array, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C

W, H, FPS = 1080, 1920, 30
MIN_S, MAX_S = 10.0, 30.0


def opt(D, key, default=""):
    p = os.path.join(D, "brief.md")
    if os.path.exists(p):
        for ln in open(p, encoding="utf-8"):
            m = re.match(rf"^\s*[-*]?\s*{key}\s*:\s*(.+?)\s*$", ln, re.I)
            if m and m.group(1).strip(): return m.group(1).strip()
    return default


def apply_layout(lines, layout):
    """single (default): one line on screen at a time, each ends where the next starts (the last holds); stack: every line stays until the end, as before."""
    if layout == "single":
        for i in range(len(lines) - 1): lines[i]["end"] = lines[i + 1]["start"]
    return lines


def parse_srt(path):
    """Cues from a Suno narration subtitle file: [{text, start, end}] in seconds."""
    def sec(x):
        h, m, r = x.strip().replace(",", ".").split(":"); return int(h) * 3600 + int(m) * 60 + float(r)
    out = []
    for blk in re.split(r"\n\s*\n", open(path, encoding="utf-8").read().strip()):
        ln = [l for l in blk.strip().split("\n") if l.strip()]
        i = next((k for k, l in enumerate(ln) if "-->" in l), None)
        if i is None or i + 1 >= len(ln): continue
        a, b = ln[i].split("-->")
        out.append({"text": " ".join(x.strip() for x in ln[i + 1:]), "start": sec(a), "end": sec(b)})
    return out


def split_lines(text, lang="", max_chars=None):
    """Break the quote into display lines. Short lines read better on a phone, and each line is one beat of the animation."""
    words = text.split()
    if not words: return []
    dev = bool(re.search(r"[ऀ-ॿ]", text))
    mc = max_chars or (20 if dev else 24)
    lines, cur = [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > mc: lines.append(cur); cur = w
        else: cur = (cur + " " + w).strip()
    if cur: lines.append(cur)
    # a single orphan word on the last line looks weak, so pull one word down from the line above
    if len(lines) >= 2 and len(lines[-1].split()) == 1 and len(lines[-2].split()) >= 3:
        a = lines[-2].split(); lines[-2] = " ".join(a[:-1]); lines[-1] = a[-1] + " " + lines[-1]
    # merge into at most 6 lines
    while len(lines) > 6:
        i = min(range(len(lines) - 1), key=lambda k: len(lines[k]) + len(lines[k + 1]))
        lines[i:i + 2] = [lines[i] + " " + lines[i + 1]]
    return lines


def probe_dur(p): return C.duration(p)


def make_drone(out, dur):
    """The old bed: a slow chord drone. Kept as music: drone."""
    ff = C.tool("ffmpeg")
    chord = [110.0, 164.81, 220.0, 277.18, 329.63]  # A2 E3 A3 C#4 E4, open and calm
    src = "+".join(f"{0.18 if f < 150 else 0.10}*sin(2*PI*{f}*t+{0.4*i})" for i, f in enumerate(chord))
    f = f"aevalsrc='({src})*(0.75+0.25*sin(2*PI*0.12*t))':s=44100:d={dur + 1:.2f}:c=stereo"
    af = f"lowpass=f=1800,aecho=0.8:0.7:380|620:0.35|0.25,afade=t=in:st=0:d=1.5,afade=t=out:st={max(0.0, dur - 2.5):.2f}:d=2.5"
    C.run([ff, "-y", "-v", "error", "-f", "lavfi", "-i", f, "-af", af, "-t", f"{dur:.2f}", "-c:a", "libmp3lame", "-b:a", "192k", out])


def make_pad(out, dur, style="piano"):
    """An original bed made here, free of any licence: a slow soft piano (synthesised notes, Am F C G) under distant rain.
    style 'drone' gives the old chord drone, 'piano' adds no rain-free option, 'piano_dry' is piano without rain."""
    if style == "drone": return make_drone(out, dur)
    import math, wave, tempfile
    ff = C.tool("ffmpeg")
    sr = 22050
    n = int((dur + 2) * sr)
    buf = array.array("f", [0.0]) * n
    prog = [  # (bass, arpeggio)  each chord lasts 4 steps of 0.85 s
        (110.00, [220.00, 261.63, 329.63]),   # Am
        (87.31, [174.61, 220.00, 261.63]),    # F
        (130.81, [196.00, 261.63, 329.63]),   # C
        (98.00, [196.00, 246.94, 293.66]),    # G
    ]
    step, rnd = 0.85, random.Random(7)

    def note(f, t0, vel):
        i0 = int(t0 * sr); L = int(3.2 * sr)
        for k in range(min(L, n - i0)):
            t = k / sr
            env = math.exp(-t * (1.25 if f > 150 else 0.85)) * (1 - math.exp(-t * 90))
            w = math.sin(6.2831853 * f * t) + 0.45 * math.sin(12.5663706 * f * t) * math.exp(-t * 2.2) + 0.18 * math.sin(18.8495559 * f * t) * math.exp(-t * 3.5)
            buf[i0 + k] += vel * env * w
    t, ci = 0.6, 0
    while t < dur - 1.5:
        bass, arp = prog[ci % 4]
        note(bass, t, 0.34)
        for j, f in enumerate(arp + [arp[1]]):
            tt = t + (j + 1) * step + rnd.uniform(-0.03, 0.03)
            if tt < dur - 1.0: note(f, tt, 0.20 + 0.06 * rnd.random())
        t += step * 5; ci += 1
    peak = max(1e-6, max(abs(x) for x in buf))
    tmp = tempfile.mkdtemp(prefix="insp_pad_")
    wav = os.path.join(tmp, "piano.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(array.array("h", [int(max(-1, min(1, x / peak * 0.8)) * 32767) for x in buf]).tobytes())
    fade = f"loudnorm=I=-16:TP=-1.5:LRA=7,afade=t=in:st=0:d=1.2,afade=t=out:st={max(0.0, dur - 2.5):.2f}:d=2.5"
    piano = "[0:a]aresample=44100,lowpass=f=3200,aecho=0.8:0.6:420|760:0.30|0.20,aformat=channel_layouts=stereo[p]"
    if style == "piano_dry":
        fc = piano.replace("[p]", "[m]") + f";[m]{fade}[o]"
        args = ["-i", wav]
    else:
        rain = "[1:a]highpass=f=900,lowpass=f=7000,volume=0.16,aformat=channel_layouts=stereo[r]"
        fc = f"{piano};{rain};[p][r]amix=inputs=2:duration=first:normalize=0,{fade}[o]"
        args = ["-i", wav, "-f", "lavfi", "-i", f"anoisesrc=color=pink:amplitude=0.5:r=44100:d={dur + 2:.2f}"]
    C.run([ff, "-y", "-v", "error"] + args + ["-filter_complex", fc, "-map", "[o]", "-t", f"{dur:.2f}", "-c:a", "libmp3lame", "-b:a", "192k", out])


def music_source(D, dur):
    """Return a path to music, or None for silence. Order: music.* in the folder, brief path, library, generated pad."""
    mode = opt(D, "music", "auto")
    if mode.lower() == "none": return None, "none"
    for p in sorted(glob.glob(os.path.join(D, "music_src.*")) + glob.glob(os.path.join(D, "music.*"))):
        if os.path.splitext(p)[1].lower() in (".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg") and os.path.basename(p) != "music.mp3": return p, "file in folder"
    if mode.lower() != "auto":
        q = os.path.expanduser(mode)
        if os.path.exists(q): return q, "brief"
        sys.exit(f"navaan: music file not found: {q}")
    lib = os.path.join(os.path.expanduser(C.cfg("storage.local_dir", "") or ""), "inspire_music")
    tracks = sorted(p for p in glob.glob(os.path.join(lib, "*")) if os.path.splitext(p)[1].lower() in (".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg")) if os.path.isdir(lib) else []
    if tracks:
        h = int(hashlib.sha1(os.path.basename(D).encode()).hexdigest(), 16)
        return tracks[h % len(tracks)], "library"
    return None, "pad"


def fit_music(src, out, dur, start=0.0):
    ff = C.tool("ffmpeg")
    total = probe_dur(src)
    if total > dur + 6: start = min(start, max(0.0, total - dur - 1))
    af = f"afade=t=in:st=0:d=1.2,afade=t=out:st={max(0.0, dur - 2.0):.2f}:d=2.0,loudnorm=I=-18:TP=-1.5:LRA=9"
    C.run([ff, "-y", "-v", "error", "-ss", f"{start:.2f}", "-i", src, "-t", f"{dur:.2f}", "-af", af, "-ac", "2", "-ar", "44100", "-c:a", "libmp3lame", "-b:a", "192k", out])


def beats(path, dur):
    """Find beat times with plain energy flux (no numpy). Falls back to an even grid when the music is too flat to tell."""
    ff = C.tool("ffmpeg")
    sr, hop = 11025, 256
    raw = subprocess.run([ff, "-v", "error", "-i", path, "-t", f"{dur:.2f}", "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"], capture_output=True).stdout
    a = array.array("h"); a.frombytes(raw[: len(raw) // 2 * 2])
    n = len(a) // hop
    if n < 20: return [round(i * 0.5, 3) for i in range(int(dur / 0.5))], "grid"
    en = [(sum(x * x for x in a[i * hop:(i + 1) * hop]) / hop) ** 0.5 for i in range(n)]
    sm = [sum(en[max(0, i - 2):i + 3]) / len(en[max(0, i - 2):i + 3]) for i in range(n)]
    flux = [max(0.0, sm[i] - sm[i - 1]) for i in range(1, n)]
    if not flux or max(flux) < 1e-6: return [round(i * 0.5, 3) for i in range(int(dur / 0.5))], "grid"
    thr = sorted(flux)[int(len(flux) * 0.88)]
    t_hop = hop / sr
    pk = [(i + 1) * t_hop for i in range(1, len(flux) - 1) if flux[i] >= thr and flux[i] >= flux[i - 1] and flux[i] >= flux[i + 1]]
    out = []
    for t in pk:
        if not out or t - out[-1] >= 0.35: out.append(round(t, 3))
    if len(out) < max(4, int(dur / 2.5)): return [round(i * 0.5, 3) for i in range(int(dur / 0.5))], "grid"
    return out, "onset"


def snap(t, bts, lo, hi, tol=0.4):
    """Move t to the nearest beat inside [lo, hi] when one is within tol seconds."""
    cand = [b for b in bts if lo <= b <= hi and abs(b - t) <= tol]
    return min(cand, key=lambda b: abs(b - t)) if cand else t


def brand_name(slug):
    """Text of the end card: the handle of the account this item posts to. Music items post to NAVAAN, so they get no end card."""
    t = C.item_type(C.item_load(slug, {}))
    if t == "music": return ""
    h = (C.account(t).get("handle") or "").strip()
    return h.lstrip("@")


def watermark(slug):
    """The handle shown at the bottom is the account this item posts to (accounts.<type>), never the NAVAAN one."""
    h = (C.account(C.item_type(C.item_load(slug, {}))).get("handle") or "").strip()
    return ("@" + h.lstrip("@")) if h else "NAVAAN"


def main(slug):
    D = C.song_dir(slug)
    q = C.load_json(os.path.join(D, "quote.json"))
    text = (q.get("text") or "").strip()
    if not text: sys.exit("navaan: quote.json has no text")
    lines = [l.strip() for l in (q.get("lines") or []) if l.strip()] or split_lines(text, q.get("language", ""))
    author = (q.get("author") or "").strip()
    bg = next((os.path.basename(p) for ext in ("jpg", "jpeg", "png", "webp") for p in glob.glob(os.path.join(D, f"background.{ext}"))), None)
    if not bg: sys.exit("navaan: no background image. Run the background step or put background.jpg in the folder.")
    words = [len(l.split()) for l in lines]
    voice = next((p for p in sorted(glob.glob(os.path.join(D, "voiceover.*"))) if os.path.splitext(p)[1].lower() in (".mp3", ".wav", ".m4a", ".aac")), None)
    if opt(D, "voiceover", "none").lower() == "file" and not voice:
        sys.exit("navaan: brief says voiceover: file but voiceover.mp3 is not in the folder. Add it, or set voiceover: none.")
    srt = os.path.join(D, "voiceover.srt")
    narr = bool(voice and os.path.exists(srt))  # a Suno narration with its timed subtitles: the text follows the voice exactly, one line at a time
    brand = brand_name(slug)  # the account name is shown on its own end card for the last seconds
    brand_tail = 3.4 if brand else 0.0
    intro, tail_hold = 1.0, 2.2 + (1.6 if author else 0.0) + brand_tail
    if narr:
        ncues = parse_srt(srt)
        if not ncues: sys.exit("navaan: voiceover.srt has no cues")
        vd = probe_dur(voice); body_end = max(vd, ncues[-1]["end"])
        dur = round(min(60.0, body_end + (brand_tail if brand else 2.4)), 2)  # the picture holds for the end card after the last word
        body = body_end; span = dur
    elif voice:
        vd = probe_dur(voice); body = max(3.0, vd); dur = min(MAX_S, max(MIN_S, intro + body + tail_hold))
    else:
        want = opt(D, "duration", "")
        body = sum(1.1 + 0.42 * w for w in words)
        dur = float(want) if want.replace(".", "", 1).isdigit() else intro + body + tail_hold
        dur = min(MAX_S, max(MIN_S, dur))
    if not narr: span = dur - intro - tail_hold  # time the lines have between them
    tot_w = sum(words) or 1
    # music first, so the lines can follow its beats
    mfile = os.path.join(D, "music.mp3"); src, how = music_source(D, dur)
    if narr and opt(D, "music", "auto").lower() == "auto": src, how = None, "none"  # the narration already carries its own music
    if how == "none": mfile = None
    elif src: fit_music(src, mfile, dur)
    else: make_pad(mfile, dur, opt(D, "bed", "piano").lower())
    bts, bkind = ([], "none") if not mfile else beats(mfile, dur)
    # a line's start time follows how many words came before it; the end is the next start (the last one holds until the author line)
    starts, acc = [], 0.0
    for i, w in enumerate(words):
        starts.append(intro + span * acc / tot_w); acc += w
    for i in range(1, len(starts)):
        starts[i] = max(starts[i - 1] + 0.9, snap(starts[i], bts, starts[i - 1] + 0.9, dur - tail_hold - 0.5))
    # the whole quote stays on screen: each line appears, then all lines fade out together at hold_end
    hold_end = round(dur - brand_tail - (1.2 if author else 0.8), 2)
    out_lines = [{"text": l, "start": round(s, 2), "end": hold_end} for l, s in zip(lines, starts)]
    if narr:
        out_lines = [{"text": c["text"], "start": round(max(0.0, c["start"] - 0.1), 2), "end": round(c["end"] if i < len(ncues) - 1 else body_end, 2)} for i, c in enumerate(ncues)]
        hold_end = round(body_end, 2)
        vo = os.path.join(D, "narration.mp3")  # a plain mp3 so every renderer can play it
        C.run([C.tool("ffmpeg"), "-y", "-v", "error", "-i", voice, "-vn", "-ac", "2", "-ar", "44100", "-af", "loudnorm=I=-16:TP=-1.5:LRA=9", "-c:a", "libmp3lame", "-b:a", "192k", vo])
        voice = vo
    layout = opt(D, "layout", "single").lower(); layout = layout if layout in ("single", "stack") else "single"
    apply_layout(out_lines, layout)
    h = int(hashlib.sha1(slug.encode()).hexdigest(), 16)
    presets = ["push_in", "pan_left", "pull_out", "pan_right", "drift"]
    cam = opt(D, "camera", presets[h % len(presets)]).lower()
    if cam not in presets: cam = presets[h % len(presets)]
    tr = opt(D, "transition", "rise").lower()
    if tr not in ("rise", "fade", "blur"): tr = "rise"
    timing = {
        "slug": slug, "width": W, "height": H, "fps": FPS, "duration": round(dur, 2),
        "background": bg, "music": os.path.basename(mfile) if mfile else None, "voiceover": os.path.basename(voice) if voice else None,
        "lines": out_lines, "hold_until": hold_end,
        "brand": ({"text": brand, "icon": "instagram", "start": round(dur - 3.2, 2), "end": round(dur, 2)} if brand else None),
        "author": ({"text": "— " + author, "start": round(max(starts[-1] + 1.2, dur - tail_hold + 0.4), 2), "end": round(hold_end + 0.0, 2)} if author else None),
        "camera": cam, "transition": tr, "layout": layout, "language": q.get("language", ""), "narration": narr,
        "style": {"color": "#FFFFFF", "accent": "#FF4D7E", "dim": 0.45},
        "watermark": watermark(slug),
        "music_source": how, "beat_source": bkind, "beats": bts[:80],
    }
    json.dump(timing, open(os.path.join(D, "timing.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    json.dump({"source": bkind, "beats": bts}, open(os.path.join(D, "beats.json"), "w"), indent=1)
    print(f"timing.json: {len(out_lines)} lines, {dur:.1f}s, camera {cam}, transition {tr}, music {how} ({bkind} beats)")


if __name__ == "__main__":
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])

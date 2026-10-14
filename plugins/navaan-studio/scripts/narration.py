#!/usr/bin/env python3
"""narration.py  attach a ready made narration (audio plus its timed .srt) to an inspiration short.

Used by the portal's New inspiration dialog. Writes voiceover.<ext> and voiceover.srt into the item's folder and sets the
brief to `voiceover: file` and `music: none` (the narration carries its own music). Nothing is generated and nothing is spent.

  narration.py <slug> <audio file> <srt file>     the same thing from a terminal
  narration.py <slug> <audio file> --text <file>  audio plus the words (one line per row), no .srt: the timing is made by narration_sync.py
  narration.py <slug> --remove                     back to no voiceover and the generated music bed
"""
import os, sys, re, glob, json, base64, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C

AUDIO_EXT = (".mp3", ".wav", ".m4a", ".aac")
MAX_AUDIO = 20 * 1024 * 1024  # the web server accepts 30 MB bodies and base64 adds a third
MAX_SRT = 200 * 1024


def set_options(D, opts):
    """Set `- key: value` lines under Options in brief.md. A missing line is added at the end."""
    p = os.path.join(D, "brief.md"); text = open(p, encoding="utf-8").read() if os.path.exists(p) else "# Inspiration short\n\n## Options\n\n"
    for k, v in opts.items():
        pat = re.compile(rf"^(\s*[-*]?\s*){re.escape(k)}\s*:.*$", re.I | re.M)
        if pat.search(text): text = pat.sub(lambda m: f"{m.group(1)}{k}: {v}", text, count=1)
        else: text = text.rstrip("\n") + f"\n- {k}: {v}\n"
    open(p, "w", encoding="utf-8").write(text)


def check_srt(text):
    """The cues of an srt, or ValueError. Needs at least one timed line."""
    import inspire_prep
    if len(text.encode("utf-8")) > MAX_SRT: raise ValueError("the subtitle file is too big for an srt")
    with tempfile.NamedTemporaryFile("w", suffix=".srt", delete=False, encoding="utf-8") as f: f.write(text); tmp = f.name
    try: cues = inspire_prep.parse_srt(tmp)
    except Exception: cues = []
    finally: os.remove(tmp)
    if not cues: raise ValueError("the subtitle file has no timed lines (an .srt with 00:00:01,000 --> 00:00:03,000 lines)")
    return cues


def write_quote(D, cues):
    """quote.json and title.txt from the narration's own words, so Claude does not write a quote for a narration you made."""
    return write_lines(D, [" ".join(c["text"].split()) for c in cues if c["text"].strip()])


def write_lines(D, lines):
    text = " ".join(lines)
    lang = "hi" if re.search(r"[ऀ-ॿ]", text) else "en"
    q = {"text": text, "lines": lines, "author": "", "kind": "original", "language": lang, "source": "", "notes": "the words of the uploaded narration"}
    with open(os.path.join(D, "quote.json"), "w", encoding="utf-8") as f: json.dump(q, f, indent=2, ensure_ascii=False); f.write("\n")
    title = " ".join(text.replace("…", " ").split())[:60].rstrip(" ,.;:-")
    open(os.path.join(D, "title.txt"), "w", encoding="utf-8").write(title + "\n")
    bp = os.path.join(D, "brief.md")
    if os.path.exists(bp):  # the brief shows the narration text where the idea goes
        b = open(bp, encoding="utf-8").read()
        b2 = re.sub(r"(## Idea\s*\n\s*\n).*?(\n\s*\n## Options)", lambda m: m.group(1) + text + m.group(2), b, count=1, flags=re.S)
        open(bp, "w", encoding="utf-8").write(b2)
    return text


def text_lines(text):
    """One subtitle line per row of the text box. Blank rows are dropped."""
    return [" ".join(l.split()) for l in str(text or "").splitlines() if l.strip()]


def save(D, audio_name, audio, srt_text, text=""):
    """audio is bytes or a base64 string (a data: URL is fine). With the .srt, the timing is known: returns {"audio", "cues", "seconds"}.
    Without it the words come from `text` (one line per row) and the timing is made later by narration_sync.py: returns {"audio", "cues": len(lines), "seconds": None, "timing": "pending"}."""
    ext = os.path.splitext(str(audio_name or ""))[1].lower()
    if ext not in AUDIO_EXT: raise ValueError("the narration must be an mp3, wav, m4a or aac file")
    raw = audio if isinstance(audio, (bytes, bytearray)) else base64.b64decode(str(audio).split(",", 1)[-1])
    if not raw: raise ValueError("the audio file is empty")
    if len(raw) > MAX_AUDIO: raise ValueError("the audio is over 20 MB")
    have_srt = bool(str(srt_text or "").strip())
    if have_srt: cues = check_srt(str(srt_text))
    else:
        lines = text_lines(text)
        if not lines: raise ValueError("write the narration text, one line per row, or pick the .srt subtitle file")
        if len(lines) > 40: raise ValueError("the narration text has more than 40 lines")
    for old in glob.glob(os.path.join(D, "voiceover.*")) + [os.path.join(D, "narration_sync.json")]:
        if os.path.exists(old): os.remove(old)
    open(os.path.join(D, "voiceover" + ext), "wb").write(bytes(raw))
    set_options(D, {"voiceover": "file", "music": "none"})
    if not have_srt:
        write_lines(D, lines)
        return {"audio": "voiceover" + ext, "cues": len(lines), "seconds": None, "timing": "pending"}
    open(os.path.join(D, "voiceover.srt"), "w", encoding="utf-8").write(str(srt_text).strip() + "\n")
    write_quote(D, cues)
    return {"audio": "voiceover" + ext, "cues": len(cues), "seconds": round(cues[-1]["end"], 1)}


def remove(D):
    for old in glob.glob(os.path.join(D, "voiceover.*")) + glob.glob(os.path.join(D, "narration.mp3")): os.remove(old)
    set_options(D, {"voiceover": "none", "music": "auto"})


def main(a):
    if len(a) < 2 or a[0] in ("-h", "--help"): sys.exit(__doc__)
    D = C.song_dir(a[0])
    if a[1] == "--remove": remove(D); print("narration removed"); return 0
    if len(a) < 3: sys.exit(__doc__)
    if a[2] == "--text" and len(a) > 3: r = save(D, os.path.basename(a[1]), open(a[1], "rb").read(), "", open(a[3], encoding="utf-8").read())
    else: r = save(D, os.path.basename(a[1]), open(a[1], "rb").read(), open(a[2], encoding="utf-8").read())
    print(f"narration attached: {r['audio']}, {r['cues']} lines" + (f", {r['seconds']} s" if r.get("seconds") else ", timing is made when the item runs")); return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

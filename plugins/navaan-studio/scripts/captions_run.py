#!/usr/bin/env python3
"""captions_run.py <slug>  measure when each lyric line is sung. No agent needed.

Runs vocal separation, Whisper small on Hindi (or the language set in the profile), and the line aligner, then writes
songs/<slug>/caption_cues.json and reel_start.json (the hook, see reel_hook.py). Needs setup_captions.py to have installed the tools.
Lines that are only sustained vowels (alaap) are left out of the captions.
"""
import os, sys, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from navaan_common import song_dir, tool, cfg, lyric_lines, NO_LYRICS
import setup_captions as S

HERE = os.path.dirname(os.path.abspath(__file__))


def clean_lyrics(src, dst):
    import re
    keep = []; dropped = 0
    for l in open(src, encoding="utf-8").read().splitlines():
        s = l.strip()
        if not s: continue
        if s.startswith("["): keep.append(s); continue
        letters = re.findall("[ऄ-हक़-य़]", s)  # Devanagari consonants and independent vowels
        if re.search("[ऀ-ॿ]", s) and len(letters) < 5 and re.search("[ऽ…]|\\.\\.\\.", s):
            dropped += 1; continue  # alaap such as "आऽऽऽ…" or "गा… मा… गाऽऽ…"
        keep.append(s)
    open(dst, "w", encoding="utf-8").write("\n".join(keep) + "\n")
    return dropped


def has_latin_lines(path):
    """True when some lyric line is in Latin script (English, or romanised Hindi). The aligner matches those against an English transcript (<tag>_asren.json); without it they have no speech to match."""
    import re
    with open(path, encoding="utf-8", errors="ignore") as f:
        return any(len(re.findall("[A-Za-z]", l)) >= 3 and not re.search("[\u0900-\u097f]", l) for l in (x.strip() for x in f) if l and not l.startswith("["))


def main(slug):
    D = song_dir(slug)
    if not lyric_lines(D): sys.exit("navaan: " + NO_LYRICS.replace("work from", "time"))   # before anything heavy: an imported song may have no lyrics, and timing no words crashes deep inside the aligner
    if not S.ready(): sys.exit("navaan: caption tools are not installed. Approve the captions_setup gate, or run setup_captions.py --yes.")
    py = S.venv_python(); work = os.path.join(D, ".cache"); os.makedirs(work, exist_ok=True)
    env = dict(os.environ, NAVAAN_WORK=work, NAVAAN_VOC_MODEL=S.VOC, NAVAAN_WHISPER_DIR=S.MODELS)
    env["PATH"] = os.path.dirname(tool("ffmpeg")) + os.pathsep + env.get("PATH", "")
    mono = os.path.join(work, "mono.wav")
    subprocess.check_call([tool("ffmpeg"), "-y", "-v", "error", "-i", os.path.join(D, "final.mp3"), "-ac", "1", "-ar", "44100", mono])
    tag = slug
    if not os.path.exists(f"{work}/{tag}_voc.npy"):
        print("separating vocals ...", flush=True); subprocess.check_call([py, os.path.join(HERE, "sep.py"), tag, mono], env=env)
    lang = (cfg("music.default_language") or "hi").lower()[:2]
    lang = lang if lang in ("hi", "en") else "hi"  # Maithili is sung in Devanagari, Hindi model is the closest
    hj = f"{work}/{tag}_hi.json"
    if not os.path.exists(hj):
        print("transcribing windows ...", flush=True); subprocess.check_call([py, os.path.join(HERE, "asr.py"), tag, "small", "hi", hj], env=env)
    ej = f"{work}/{tag}_asren.json"
    if has_latin_lines(os.path.join(D, "lyrics.txt")) and not os.path.exists(ej):
        print("transcribing windows (English) ...", flush=True); subprocess.check_call([py, os.path.join(HERE, "asr.py"), tag, "small", "en", ej], env=env)   # English lines are matched to this
    lyr = os.path.join(work, "lyrics_clean.txt"); n = clean_lyrics(os.path.join(D, "lyrics.txt"), lyr)
    if n: print(f"left {n} alaap line(s) out of the captions")
    print("aligning lines ...", flush=True)
    subprocess.check_call([py, os.path.join(HERE, "align.py"), tag, lyr, os.path.join(D, "caption_cues.json"), "{}"], env=env)
    cues = json.load(open(os.path.join(D, "caption_cues.json")))
    if not cues: sys.exit("navaan: no cues were produced")
    import reel_hook   # the reel is cut from the hook of the song, not from its start
    reel_hook.main(slug)
    print(f"wrote {len(cues)} caption cues and reel_start.json")


if __name__ == "__main__":
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])

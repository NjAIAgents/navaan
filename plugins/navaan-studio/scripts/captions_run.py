#!/usr/bin/env python3
"""captions_run.py <slug>  measure when each lyric line is sung. No agent needed.

Runs vocal separation, Whisper small on Hindi (or the language set in the profile), and the line aligner, then writes
songs/<slug>/caption_cues.json and reel_start.json. Needs setup_captions.py to have installed the tools.
Lines that are only sustained vowels (alaap) are left out of the captions.
"""
import os, sys, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from navaan_common import song_dir, tool, cfg
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


def main(slug):
    if not S.ready(): sys.exit("navaan: caption tools are not installed. Approve the captions_setup gate, or run setup_captions.py --yes.")
    D = song_dir(slug); py = S.venv_python(); work = os.path.join(D, ".cache"); os.makedirs(work, exist_ok=True)
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
    lyr = os.path.join(work, "lyrics_clean.txt"); n = clean_lyrics(os.path.join(D, "lyrics.txt"), lyr)
    if n: print(f"left {n} alaap line(s) out of the captions")
    print("aligning lines ...", flush=True)
    subprocess.check_call([py, os.path.join(HERE, "align.py"), tag, lyr, os.path.join(D, "caption_cues.json"), "{}"], env=env)
    cues = json.load(open(os.path.join(D, "caption_cues.json")))
    if not cues: sys.exit("navaan: no cues were produced")
    # reel window: 60 s starting at the busiest 60 s of cues, snapped to a cue start
    dur = 60.0; best, bs = -1, cues[0][0]
    for c in cues:
        s = c[0]; cover = sum(max(0, min(e, s + dur) - max(b, s)) for b, e, _ in cues)
        if cover > best: best, bs = cover, s
    json.dump({"start": round(max(0.0, bs - 0.5), 1), "dur": dur}, open(os.path.join(D, "reel_start.json"), "w"))
    print(f"wrote {len(cues)} caption cues and reel_start.json")


if __name__ == "__main__":
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])

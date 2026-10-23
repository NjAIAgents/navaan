#!/usr/bin/env python3
"""Author: Navjyot Nishant
Created: 2026-10-23
Last updated: 2026-10-23
Description: the free, deterministic checks of a rendered inspiration or Aha-lorithm short (NAV-147), run before anything is asked of Claude or of the owner.

  inspire_qa.py <slug>     check final_reel_9x16.mp4, write qa_checks.json, and when a check fails also qa.json (verdict "fix") so the Claude look is not spent on a video already known to be bad

Checks: the file (size, codec, length), a black stretch of a second or more in the middle (the dip between two pictures is about 0.6 s and the fade at either end is allowed), the sound
(clipping, too quiet), and caption sync: what a word recogniser hears in the final audio against when the video lights each word (more than 0.5 s apart fails). The sync check is skipped,
and says so, when the word timing tools are not installed or too few words were heard right. What cannot be measured here, the look (overlapping lines, text over a face, a picture that does
not fit its line), is the Claude look's job (skill inspiration-qa). Writes only into the item folder; changes no video, plan or gate.
"""
import os, sys, json, re, subprocess, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C

FINAL = "final_reel_9x16.mp4"
SYNC_MAX_S = 0.5      # a caption word may light this long before or after the word is spoken
BLACK_MIN_S = 1.0     # a black stretch this long, away from the ends, is a fault (a dip between pictures is about 0.6 s)
EDGE_S = 1.0          # the first and last second may be dark: the fade in and out
PEAK_MAX_DB, MEAN_MIN_DB = -0.5, -32.0


def black_stretches(path, duration, ffmpeg="ffmpeg"):
    """[(start, end)] of black stretches of at least 0.5 s, from ffmpeg's own detector."""
    p = subprocess.run([ffmpeg, "-hide_banner", "-nostats", "-i", path, "-vf", "blackdetect=d=0.5:pix_th=0.10", "-an", "-f", "null", "-"], capture_output=True, text=True)
    return [(float(a), float(b)) for a, b in re.findall(r"black_start:([\d.]+)\s+black_end:([\d.]+)", p.stderr)]


def black_check(stretches, duration):
    bad = [(a, b) for a, b in stretches if b - a >= BLACK_MIN_S and a > EDGE_S and b < duration - EDGE_S]
    if bad: return {"name": "black frames", "ok": False, "at": round(bad[0][0], 1), "note": f"the picture is black from {bad[0][0]:.1f} s to {bad[0][1]:.1f} s"}
    return {"name": "black frames", "ok": True, "note": "no black stretch away from the ends"}


def sound(path, ffmpeg="ffmpeg"):
    """(mean dB, peak dB) of the audio, or None when there is none."""
    p = subprocess.run([ffmpeg, "-hide_banner", "-nostats", "-i", path, "-vn", "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True)
    m, k = re.search(r"mean_volume:\s*(-?[\d.]+) dB", p.stderr), re.search(r"max_volume:\s*(-?[\d.]+) dB", p.stderr)
    return (float(m.group(1)), float(k.group(1))) if m and k else None


def sound_check(levels):
    if levels is None: return {"name": "sound", "ok": False, "note": "the video has no audio track"}
    mean, peak = levels
    if peak > PEAK_MAX_DB: return {"name": "sound", "ok": False, "note": f"the sound clips (peak {peak:.1f} dB)"}
    if mean < MEAN_MIN_DB: return {"name": "sound", "ok": False, "note": f"the sound is very quiet (mean {mean:.1f} dB)"}
    return {"name": "sound", "ok": True, "note": f"mean {mean:.1f} dB, peak {peak:.1f} dB"}


def sync_drift(lines, heard):
    """How far the video's caption words are from where the words are spoken. lines: timing.json's lines ({text, start, at?}); heard: a recogniser's words. Returns
    (per-line gaps in seconds, or None when too few words were heard right). A line with per-word times is judged on its first and last word, one without on its start."""
    import word_align as W
    res = W.match([l["text"] for l in lines], heard)
    if not res: return None
    gaps = []
    for l, r in zip(lines, res["lines"]):
        shown = l.get("at") or [l["start"] + 0.1]   # a line without word times appears 0.1 s before its first word
        spoken = r["at"]
        pairs = [(shown[0], spoken[0])] + ([(shown[-1], spoken[-1])] if len(shown) == len(spoken) and len(shown) > 1 else [])
        gaps.append(round(max(abs(a - b) for a, b in pairs), 2))
    return gaps


def sync_check(gaps, texts):
    if gaps is None: return {"name": "caption sync", "ok": None, "note": "not checked: too few words were heard right to measure it"}
    worst = max(range(len(gaps)), key=lambda i: gaps[i])
    if gaps[worst] > SYNC_MAX_S: return {"name": "caption sync", "ok": False, "at": None, "note": f"line {worst + 1} (\"{texts[worst][:40]}\") is lit {gaps[worst]:.1f} s from where it is spoken"}
    return {"name": "caption sync", "ok": True, "note": f"every line within {max(gaps):.2f} s of where it is spoken"}


def file_check(D):
    import inspire_render as R
    path = os.path.join(D, FINAL)
    if not os.path.exists(path): return {"name": "video file", "ok": False, "note": FINAL + " is missing"}, None
    info = R.probe(path); T = C.load_json(os.path.join(D, "timing.json"), default={}) or {}
    errs, warns = R.validate(info, T or {"duration": info["duration"]})
    return ({"name": "video file", "ok": not errs, "note": "; ".join(errs) if errs else f"{info['width']}x{info['height']} {info['codec']}, {info['duration']} s"}), info


def run(D, ffmpeg="ffmpeg", recognise=None):
    """All the checks for the item in D. recognise(path) -> a recogniser's words, replaced in tests; by default Vosk from the caption tools when installed."""
    checks = []; fc, info = file_check(D); checks.append(fc)
    path = os.path.join(D, FINAL); T = C.load_json(os.path.join(D, "timing.json"), default={}) or {}
    if info:
        checks.append(black_check(black_stretches(path, info["duration"], ffmpeg), info["duration"]))
        checks.append(sound_check(sound(path, ffmpeg)))
        lines = [l for l in (T.get("lines") or []) if str(l.get("text", "")).strip()]
        if T.get("narration") and lines:
            try: heard = (recognise or _recognise)(path)
            except Exception as e: heard = None; why = str(e)[:100]   # expected: no recogniser installed on this machine
            else: why = ""
            gaps = sync_drift(lines, heard) if heard else None
            c = sync_check(gaps, [l["text"] for l in lines])
            if gaps is None and why: c["note"] = "not checked: " + why
            checks.append(c)
    bad = [c for c in checks if c["ok"] is False]
    return {"verdict": "fix" if bad else "pass", "checks": checks, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def _recognise(path):
    import setup_captions as S, word_align as W, narration_sync as N
    if not S.vosk_ready(): raise RuntimeError("the word timing tools are not installed")
    return W.recognise(N.decode(path), S.VOSK)


def notify_text(slug, res):
    """A short plain-text summary for a person or a chat message, so a notification can be sent as it is."""
    bad = [c for c in res["checks"] if c["ok"] is False]
    if not bad: return f"{slug}: the automatic checks passed."
    return f"{slug}: the automatic checks found {len(bad)} problem{'s' * (len(bad) != 1)}: " + "; ".join(c["note"] for c in bad) + "."


def main(slug):
    D = C.song_dir(slug); res = run(D, C.tool("ffmpeg"))
    with open(os.path.join(D, "qa_checks.json"), "w", encoding="utf-8") as f: json.dump(res, f, ensure_ascii=False, indent=2)
    if res["verdict"] == "fix":   # known to be bad: say so as the QA verdict, and the look of it is not spent on
        bad = [c for c in res["checks"] if c["ok"] is False]
        qa = {"verdict": "fix", "source": "checks", "summary": notify_text(slug, res), "checks": res["checks"], "fixes": [c["note"] for c in bad], "notify": notify_text(slug, res), "at": res["at"]}
        with open(os.path.join(D, "qa.json"), "w", encoding="utf-8") as f: json.dump(qa, f, ensure_ascii=False, indent=2)
    elif os.path.exists(os.path.join(D, "qa.json")) and (C.load_json(os.path.join(D, "qa.json"), default={}) or {}).get("source") == "checks":
        os.remove(os.path.join(D, "qa.json"))   # an older failure written by these checks, now fixed: the Claude look runs again
    for c in res["checks"]: print(("ok   " if c["ok"] else "SKIP " if c["ok"] is None else "FAIL ") + c["name"] + ": " + c["note"])
    print("automatic checks: " + res["verdict"])
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2: sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))

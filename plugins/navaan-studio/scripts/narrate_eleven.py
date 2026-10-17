#!/usr/bin/env python3
"""Author: Navjyot Nishant
Created: 2026-10-17
Last updated: 2026-10-17
Description: the pipeline step that narrates an inspiration's quote (the quote only) with ElevenLabs and attaches it as the item's voiceover.

  narrate_eleven.py <slug> [--estimate]

Reads quote.json (the lines of the quote, not the author), speaks it in the voice the brief names (`- voice: suno1|suno2|suno3|frank|nj`, else the Settings choice, SunoCustom1 by default),
writes voiceover.mp3 and sets `voiceover: file` and `music: none` in brief.md. The timing of the lines is made by the next step (narration_sync.py).
It sits behind the credits approval and the monthly ElevenLabs cap of Settings; the same text in the same voice is never generated twice (tts_eleven cache).
"""
import os, re, sys, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C
import media_cfg as M, narration, tts_eleven as T


def quote_text(D):
    """The words to speak: the quote's lines, one per row (a short pause between them). Never the author."""
    q = C.load_json(os.path.join(D, "quote.json"), default=None) or {}
    lines = [" ".join(str(l).split()) for l in (q.get("lines") or []) if str(l).strip()] or ([" ".join(str(q.get("text") or "").split())] if str(q.get("text") or "").strip() else [])
    if not lines: raise ValueError("there is no quote yet: write or pick the quote first")
    if len(lines) == 1: lines = re.split(r"(?<=[.!?])\s+", lines[0])   # a quote kept as one sentence-run: a pause after each sentence
    return "\n\n".join(lines)   # a blank row between the lines: the voice leaves a pause, so the words can keep pace with the text on screen


SCRIPT = "narration_script.txt"   # what ElevenLabs reads, when the owner has edited it; else the suggested script is made from the quote
MAX_SCRIPT = 4000


def default_script(D):
    """The suggested spoken script: the quote with the tone tags and pauses the chosen pace needs (v4 and v3 are paced by the text itself)."""
    text = quote_text(D); sp = T.PACES[chosen_pace(D)]
    return T.directed(text, sp) if M.load()["eleven_model"] in T.TAG_MODELS else text


def script_text(D):
    """The script that will be spoken: the owner's saved one, else the suggestion."""
    p = os.path.join(D, SCRIPT)
    if os.path.isfile(p):
        t = open(p, encoding="utf-8").read().strip()
        if t: return t
    return default_script(D)


def save_script(D, text):
    """Keep an edited script (empty clears it, back to the suggestion). The voice made from the old one is stale."""
    text = (text or "").strip()
    if len(text) > MAX_SCRIPT: raise ValueError("the script is over %d characters" % MAX_SCRIPT)
    p = os.path.join(D, SCRIPT)
    if text:
        with open(p, "w", encoding="utf-8") as f: f.write(text + "\n")
    elif os.path.exists(p): os.remove(p)


def chosen_voice(D):
    v = narration.get_option(D, "voice", "").lower()
    return v if v in M.VOICES else M.load()["voice"]


def chosen_pace(D):
    """slow (default), calm or normal: a reflective quote is read slowly so each line can sit on screen while it is spoken."""
    p = narration.get_option(D, "pace", "slow").lower()
    return p if p in T.PACES else "slow"


def info(D):
    """What the Narration card shows: the voice, the estimate, this month's use. No spend."""
    try: text = script_text(D)
    except ValueError: text = ""   # expected: no quote yet, so no estimate (the card says so)
    s = M.load()
    return {"on": narration.get_option(D, "narrate", "eleven").lower() != "none", "voice": chosen_voice(D), "voices": {k: v["label"] for k, v in M.VOICES.items()},
            "pace": chosen_pace(D), "paces": {"slow": "Slow (reflective)", "calm": "Calm", "normal": "Normal"}, "estimate_s": T.estimate(text, T.PACES[chosen_pace(D)]) if text else 0, "script": text, "script_custom": os.path.isfile(os.path.join(D, SCRIPT)), "used_s": round(M.usage()["eleven_seconds"]), "cap_s": s["eleven_monthly_seconds"], "key": bool(M.get_key("elevenlabs"))}


def run(slug):
    D = C.song_dir(slug); text = script_text(D); voice = chosen_voice(D)
    out = os.path.join(D, "voiceover.mp3")
    for old in glob.glob(os.path.join(D, "voiceover.*")) + [os.path.join(D, "narration_sync.json")]:
        if os.path.exists(old): os.remove(old)   # a new voice means new timing
    try: r = T.synth(text, out, voice, speed=T.PACES[chosen_pace(D)], raw=True)   # the script is spoken as it is: the suggestion already carries the tags
    except RuntimeError as e:
        if "No ElevenLabs key" in str(e): raise RuntimeError(str(e) + " Or skip narration for this short on its Narration card.") from None
        raise
    narration.set_options(D, {"voiceover": "file"})   # the music option is left as it is: background music can sit under the voice
    return r


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    try:
        if "--estimate" in a: print(json.dumps(info(C.song_dir(a[0]))))
        else:
            r = run(a[0]); print("voiceover.mp3: %s s, voice %s%s" % (r["seconds"], r["voice"], " (from the cache, nothing spent)" if r["cached"] else ", %.0f s of the month's allowance used" % r["spent_seconds"]))
    except (ValueError, RuntimeError) as e:
        sys.exit("navaan: " + str(e))

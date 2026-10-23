#!/usr/bin/env python3
"""Author: Navjyot Nishant
Created: 2026-10-18
Last updated: 2026-10-18
Description: one picture per beat of an Aha-lorithm short with the OpenAI image API (the words are drawn later by the renderer, never in the picture).

  aha_pictures.py <slug> [--estimate] [--force]

Reads quote.json: "lines" (the beats), "pictures" (one prompt per beat, written by the aha-script skill, no spend) and "look" (the short's art direction, the same for all its beats). A beat that visual_plan.json shows with a scene treatment
(a chat, a comparison, a counting number ...) needs no picture and none is made or paid for (visuals_plan.picture_beats); its prompt may be empty. Writes scenes/beat_01.png ...
at 1080x1920 and copies the first to background.png (the thumbnail and the list use it). A beat that already has its picture is skipped, so a failed
run resumes without paying twice; --force makes them all again. Sits behind the credits approval; refuses when the whole set would pass the run cap.
"""
import os, sys, json, glob, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C
import media_cfg
import image_openai as I
import visuals_plan as V

# The pictures of a short belong together through its own art direction (`look` in quote.json, chosen by the script for this topic), not through one house look for every short.
# What every picture gets regardless: the technical limits. The image model misspells words, so no text is asked of it; the renderer draws the words crisp and editable.
LIMITS = ("Vertical 9:16. The middle of the frame stays calm enough for a caption. "
          "No words, letters, numbers, captions, logos or readable screen text anywhere in the image; screens and cards show only soft abstract shapes.")
DEFAULT_LOOK = "Cohesive modern editorial look: one consistent palette and one medium across the beats, natural light, clear subject."   # a short written before `look` existed


def look(D):
    q = C.load_json(os.path.join(D, "quote.json"), default={}) or {}
    t = " ".join(str(q.get("look") or "").split())
    return t[:400] if len(t) >= 10 else DEFAULT_LOOK


def prompt_for(beat_prompt, art_direction):
    """What is sent to the image model for one beat: the scene of that beat, the art direction of the whole short, the technical limits."""
    return (beat_prompt + "\n\nArt direction for the whole short: " + art_direction + "\n\n" + LIMITS)[:3500]


def beat_file(D, i): return os.path.join(D, "scenes", "beat_%02d.png" % (i + 1))


def need(D, n):
    """The beats that need a picture: all, except those the visual plan shows with a scene."""
    return V.picture_beats(V.load(D, "aha", n), n)


def prompts(D):
    q = C.load_json(os.path.join(D, "quote.json"), default={}) or {}
    lines, pics = [l for l in (q.get("lines") or []) if str(l).strip()], [str(p).strip() for p in (q.get("pictures") or [])]
    if not lines: raise ValueError("there is no script yet: write the script first")
    if len(pics) != len(lines) or any(len(pics[i]) < 20 for i in need(D, len(lines))): raise ValueError("quote.json needs one picture prompt (20+ characters) per beat that is shown by a picture: redo the script step")
    return pics


def main(argv):
    if not argv or argv[0].startswith("-"): sys.exit(__doc__)
    D = C.song_dir(argv[0]); cfg = media_cfg.load(); q, model = cfg["image_quality"], I.model_name(cfg)
    try: pics = prompts(D)
    except ValueError as e: sys.exit("navaan: " + str(e))
    todo = [i for i in need(D, len(pics)) if "--force" in argv or not os.path.exists(beat_file(D, i))]
    each = I.estimate(q, cfg["image_size"], model); total = round(each * len(todo), 3)
    if "--estimate" in argv:
        print(json.dumps({"model": model, "size": cfg["image_size"], "quality": q, "pictures": len(todo), "usd": total})); return 0
    if total > float(cfg["max_run_usd"]):
        sys.exit("navaan: %d %s pictures cost about $%.2f, over the run cap of $%.2f set in Settings." % (len(todo), q, total, float(cfg["max_run_usd"])))
    key, who = I.key_for(cfg), I.NAME[I.engine(cfg)]   # the key of the picture maker chosen in Settings (OpenAI or Muse), not always OpenAI's
    if todo and not key: sys.exit("navaan: no %s key. Paste it in Settings, Pictures and voice." % who)
    os.makedirs(os.path.join(D, "scenes"), exist_ok=True); art = look(D)
    for i in todo:
        raw = I.request_image(prompt_for(pics[i], art), q, key, cfg["image_size"], model)
        media_cfg.add_usage(openai_usd=each)   # spent now, whatever happens to the file
        I.fit_portrait(raw).save(beat_file(D, i), optimize=True)
        print("beat %d of %d: %s" % (i + 1, len(pics), os.path.basename(beat_file(D, i))), flush=True)
    for old in glob.glob(os.path.join(D, "background.*")): os.remove(old)
    shutil.copyfile(beat_file(D, 0), os.path.join(D, "background.png"))
    print("%d pictures made, %d kept, %d beats need none, about $%.2f" % (len(todo), len(need(D, len(pics))) - len(todo), len(pics) - len(need(D, len(pics))), total))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

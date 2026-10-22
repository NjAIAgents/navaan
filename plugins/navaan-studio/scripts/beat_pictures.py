#!/usr/bin/env python3
"""Author: Navjyot Nishant
Created: 2026-10-21
Last updated: 2026-10-21
Description: one picture per beat of an inspiration short made with "a picture per beat" (NAV-145), with the OpenAI image API (the words are drawn later by the renderer).

  beat_pictures.py <slug> [--estimate] [--force]

Reads picture_plan.json (beat_plan.py): the short's `look` and one scene prompt per beat. Writes scenes/beat_01.png ... at 1080x1920 and copies the first to background.png (the thumbnail, the
list and the one-background fallback use it). A beat that already has its picture is skipped, so a failed run resumes without paying twice; --force makes them all again. Sits behind the credits
approval; refuses when the whole set would pass the run cap. Prompt wording and the picture limits are aha_pictures' (no words in the picture, a calm middle for the caption).
"""
import os, sys, json, glob, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C
import media_cfg
import image_openai as I
import aha_pictures as A
import beat_plan as B


def main(argv):
    if not argv or argv[0].startswith("-"): sys.exit(__doc__)
    D = C.song_dir(argv[0]); cfg = media_cfg.load(); q, model = cfg["image_quality"], I.model_name(cfg)
    try: pics = B.prompts(D)
    except ValueError as e: sys.exit("navaan: " + str(e))
    todo = [k for k in range(len(pics)) if "--force" in argv or not os.path.exists(B.beat_file(D, k))]
    each = I.estimate(q, cfg["image_size"], model); total = round(each * len(todo), 3)
    if "--estimate" in argv:
        print(json.dumps({"model": model, "size": cfg["image_size"], "quality": q, "pictures": len(todo), "usd": total})); return 0
    if total > float(cfg["max_run_usd"]):
        sys.exit("navaan: %d %s pictures cost about $%.2f, over the run cap of $%.2f set in Settings." % (len(todo), q, total, float(cfg["max_run_usd"])))
    key = media_cfg.get_key("openai")
    if todo and not key: sys.exit("navaan: no OpenAI key. Paste it in Settings, Pictures and voice.")
    os.makedirs(os.path.join(D, "scenes"), exist_ok=True); art = B.look(D)
    for k in todo:
        raw = I.request_image(A.prompt_for(pics[k], art), q, key, cfg["image_size"], model)
        media_cfg.add_usage(openai_usd=each)   # spent now, whatever happens to the file
        I.fit_portrait(raw).save(B.beat_file(D, k), optimize=True)
        print("picture %d of %d: %s" % (k + 1, len(pics), os.path.basename(B.beat_file(D, k))), flush=True)
    for old in glob.glob(os.path.join(D, "background.*")): os.remove(old)
    shutil.copyfile(B.beat_file(D, 0), os.path.join(D, "background.png"))
    print("%d pictures made, %d kept, about $%.2f" % (len(todo), len(pics) - len(todo), total))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

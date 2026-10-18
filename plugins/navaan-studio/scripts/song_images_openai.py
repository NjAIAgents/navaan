#!/usr/bin/env python3
"""song_images_openai.py <slug> [--estimate] [--force] [--count N] [--try] [--vertical 3,5|all]  make the song's pictures with the OpenAI image API.

Reads songs/<slug>/prompt_pack.json (written by prompt_pack.py, no spend). Picture 1 is made from words and is also the reference: it
shows the main people clearly. Every other picture is an edit of picture 1 (the reference image goes in with the scene), so the same
people stay the same people through the whole film. They are saved as images/pic_01.png, pic_02.png and so on, where the director's
shot list and the video renderer already look for them. Pictures that already exist are kept, so a retry only makes the missing ones.
Refuses when the whole set would pass the run cap or the month cap. The key comes from media_cfg and is never printed.

--try      only the first 2 pictures, saved as try_01.png and try_02.png next to the song files, never used by the video
--vertical recompose chosen pictures (numbers, or all) as native 9:16 pictures in images/vert/, used by the reel and the short
           instead of the cropped 16:9 picture. Without them the reel crops the 16:9 picture around its focus point, free."""
import os, sys, json, io, time
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C
import media_cfg, image_openai as IO, prompt_pack, visuals_cfg as V
import navaan_log as L
LOG = L.get("song_images_openai")

WORKERS = 3
VERT_SIZE = "1152x2048"
PHOTO = "Photorealistic cinematic still, shot as a real photograph. "
FINISH = " Real skin texture, no heavy retouching, natural expression, subtle film grain. Wide 16:9 cinematic frame with open space for a slow camera move. No text, no letters, no logos, no watermarks."
ANCHOR_RULE = " In this first frame the main people are clearly visible with readable faces, so every later shot can match them."
REF = ("Use the uploaded image as the exact visual reference for the people in it. Preserve their facial identity, age, hairstyle, skin tone, build and signature clothing. "
       "Create a new shot from the same film, not new people. Scene: {scene} Keep the same cinematic colour grade, realistic skin texture, lighting style and emotional tone. "
       "Look of the film: {style} Wide 16:9 landscape frame with open space for a slow camera move. No text, no letters, no logos, no watermarks.")
VERT = ("Use the uploaded image as the exact visual reference. Recompose this same moment as a vertical 9:16 frame: the same people, the same place, the same light, the same colour grade. "
        "Keep the people in the lower two thirds and leave the upper third calm and open for lyrics. Do not add text, letters or logos.")


def _s(x): return str(x or "").strip()


def full_prompt(pack, item):
    """Words only (no reference): look, people, scene. Used for the first picture and as the fallback when an edit is refused."""
    who = ("Main people: " + _s(pack.get("character")) + " ") if _s(pack.get("character")) else ""
    return (PHOTO + _s(pack.get("style_line")) + " " + who + _s(item.get("prompt")) + FINISH).strip()[:3500]


def anchor_prompt(pack, item):
    return (full_prompt(pack, item)[:3500 - len(ANCHOR_RULE)] + ANCHOR_RULE).strip()


def scene_prompt(pack, item):
    return REF.format(scene=_s(item.get("prompt")), style=_s(pack.get("style_line")))[:3500]


def vertical_prompt(pack, item):
    return VERT + " Scene: " + _s(item.get("prompt"))[:1500]


def plan(pack, count=None):
    items = list(pack.get("prompts") or [])
    if count: items = items[:int(count)]
    return items


def total_cost(n, quality, size, model=None, anchor=True):
    """n pictures: one from words (the anchor) and the rest edits of it. anchor=False when picture 1 already exists."""
    if n <= 0: return 0.0
    gen, edit = IO.estimate(quality, size, model), IO.estimate(quality, size, model, refs=1)
    return round((gen + (n - 1) * edit) if anchor else n * edit, 3)


def check_total(n, quality, size, cfg=None, anchor=True):
    """Raise ValueError when the whole set would pass the one-run cap. Returns the cost."""
    cfg = cfg or media_cfg.load()
    cost = total_cost(n, quality, size, IO.model_name(cfg), anchor)
    cap = float(cfg["max_run_usd"])
    if cost > cap:
        raise ValueError("%d pictures at %s cost about $%.2f, over the run cap of $%.2f. Raise the run cap in Settings (Pictures and voice) or choose a lower quality." % (n, quality, cost, cap))
    return cost


def name_for(i): return "pic_%02d.png" % i


def vert_path(D, i): return os.path.join(D, "images", "vert", name_for(i))


def retry(fn, tries=3):
    last = None
    for attempt in range(tries):
        try:
            return fn()
        except RuntimeError as e:
            L.ignored(LOG, "retry: RuntimeError (optional or expected)", e)
            last = e
            if "HTTP 4" in str(e) and "HTTP 429" not in str(e): break  # a refused prompt will not work on retry
            time.sleep(4 * (attempt + 1))
    raise last


def make_scene(pack, item, ref, q, size, key, model):
    """An edit of the reference picture. When OpenAI refuses the edit, one try from words alone. Returns (bytes, dollars)."""
    try:
        return retry(lambda: IO.request_edit(scene_prompt(pack, item), [ref], q, key, size, model), 2), IO.estimate(q, size, model, refs=1)
    except RuntimeError as _e:
        L.ignored(LOG, "make_scene: RuntimeError (optional or expected)", _e)
        return retry(lambda: IO.request_image(full_prompt(pack, item), q, key, size, model)), IO.estimate(q, size, model)


def vertical_main(D, pack, items, which, q, key, model, cfg, estimate_only):
    nums = [i for i in range(1, len(items) + 1)] if which == "all" else sorted({int(x) for x in which.split(",") if x.strip().isdigit()})
    nums = [i for i in nums if 1 <= i <= len(items) and os.path.exists(os.path.join(D, "images", name_for(i)))]
    todo = [i for i in nums if not os.path.exists(vert_path(D, i))]
    if not todo: print("nothing to make: those pictures have no 16:9 picture yet or already have a vertical one."); return 0
    each = IO.estimate(q, VERT_SIZE, model, refs=1); cost = round(each * len(todo), 3)
    if cost > float(cfg["max_run_usd"]): sys.exit("navaan: %d vertical pictures cost about $%.2f, over the run cap of $%.2f." % (len(todo), cost, float(cfg["max_run_usd"])))
    if estimate_only: print(json.dumps({"model": model, "size": VERT_SIZE, "quality": q, "pictures": len(todo), "usd": cost})); return 0
    os.makedirs(os.path.join(D, "images", "vert"), exist_ok=True); failed = []

    def work(i):
        try:
            raw = retry(lambda: IO.request_edit(vertical_prompt(pack, items[i - 1]), [os.path.join(D, "images", name_for(i))], q, key, VERT_SIZE, model))
        except RuntimeError as e:
            L.ignored(LOG, "work: RuntimeError (optional or expected)", e)
            failed.append((i, str(e))); return
        media_cfg.add_usage(openai_usd=each)
        with open(vert_path(D, i), "wb") as f: f.write(raw)
        print("vertical picture %d saved" % i, flush=True)
    with ThreadPoolExecutor(WORKERS) as ex: list(ex.map(work, todo))
    if failed:
        for i, why in sorted(failed): print("vertical picture %d failed: %s" % (i, why))
        sys.exit("navaan: %d of %d vertical pictures failed." % (len(failed), len(todo)))
    print("%d vertical pictures made with OpenAI %s %s, about $%.2f" % (len(todo), model, q, cost))
    return 0


def main(argv):
    if not argv or argv[0].startswith("-"):
        sys.exit("usage: song_images_openai.py <slug> [--estimate] [--force] [--count N] [--try] [--vertical 3,5|all]")
    slug = argv[0]; D = C.song_dir(slug); cfg = media_cfg.load()
    q, size, model = cfg["image_quality"], cfg["image_size_landscape"], IO.model_name(cfg)
    pack = prompt_pack.load(D)
    if not pack or not pack.get("prompts"): sys.exit("navaan: prompt_pack.json is missing. Run the prompt step first.")
    count = int(argv[argv.index("--count") + 1]) if "--count" in argv else None
    key = media_cfg.get_key("openai")
    if "--vertical" in argv:
        if not key and "--estimate" not in argv: sys.exit("navaan: no OpenAI key. Paste it in Settings, Pictures and voice.")
        return vertical_main(D, pack, plan(pack, count), (argv[argv.index("--vertical") + 1] if len(argv) > argv.index("--vertical") + 1 else "all"), q, key, model, cfg, "--estimate" in argv)
    tr = "--try" in argv   # a test: only the first 2 prompts, saved as try_01.png and try_02.png next to the song files, never used by the video
    items = plan(pack, 2 if tr else count)
    nm = (lambda i: "try_%02d.png" % i) if tr else name_for
    imgdir = D if tr else os.path.join(D, "images"); os.makedirs(imgdir, exist_ok=True)
    todo = [(i, it) for i, it in enumerate(items, 1) if tr or "--force" in argv or not os.path.exists(os.path.join(imgdir, nm(i)))]
    need_anchor = bool(todo) and todo[0][0] == 1
    try: cost = check_total(len(todo), q, size, cfg, need_anchor)
    except ValueError as e: L.ignored(LOG, "main: ValueError (optional or expected)", e); sys.exit("navaan: " + str(e))
    if "--estimate" in argv:
        print(json.dumps({"model": model, "size": size, "quality": q, "pictures": len(todo), "usd": cost})); return 0
    if not todo: print("all %d pictures already exist. Use --force to make them again." % len(items)); return 0
    if not key: sys.exit("navaan: no OpenAI key. Paste it in Settings, Pictures and voice.")
    if not tr and len(V.own_images(D)) + len(todo) > V.MAX_IMAGES and "--force" not in argv:
        sys.exit("navaan: this would pass the limit of %d pictures for a song." % V.MAX_IMAGES)
    ref = os.path.join(imgdir, nm(1))
    if need_anchor:   # picture 1 first, from words: it shows the people clearly and is the reference for all the others
        i, it = todo[0]
        try: raw = retry(lambda: IO.request_image(anchor_prompt(pack, it), q, key, size, model))
        except RuntimeError as e: L.ignored(LOG, "main: RuntimeError (optional or expected)", e); sys.exit("navaan: the first picture failed, so the others cannot match it. " + str(e))
        media_cfg.add_usage(openai_usd=IO.estimate(q, size, model))
        with open(ref, "wb") as f: f.write(raw)
        print("picture 1 of %d saved (the reference for the people)" % len(items), flush=True)
        todo = todo[1:]
    failed = []

    def work(t):
        i, it = t
        try:
            raw, spent = make_scene(pack, it, ref, q, size, key, model)
        except RuntimeError as e:
            L.ignored(LOG, "work: RuntimeError (optional or expected)", e)
            failed.append((i, str(e))); return
        media_cfg.add_usage(openai_usd=spent)  # spent now, whatever happens to the file
        with open(os.path.join(imgdir, nm(i)), "wb") as f: f.write(raw)
        print("picture %d of %d saved" % (i, len(items)), flush=True)
        C.progress(sum(os.path.exists(os.path.join(imgdir, nm(j))) for j in range(1, len(items) + 1)), len(items), "pictures saved")
    if not os.path.exists(ref): sys.exit("navaan: picture 1 is missing, so the others cannot match it. Run the step again.")
    with ThreadPoolExecutor(WORKERS) as ex: list(ex.map(work, todo))
    if failed:
        for i, why in sorted(failed): print("picture %d failed: %s" % (i, why))
        sys.exit("navaan: %d of %d pictures failed. Retry the step, it only makes the missing ones." % (len(failed), len(items)))
    print("%d pictures made with OpenAI %s %s %s, about $%.2f" % (len(items), model, size, q, cost))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

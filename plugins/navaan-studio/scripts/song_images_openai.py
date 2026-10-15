#!/usr/bin/env python3
"""song_images_openai.py <slug> [--estimate] [--force] [--count N]  make the song's pictures with the OpenAI image API.

Reads songs/<slug>/prompt_pack.json (written by prompt_pack.py, no spend), makes one 16:9 picture per prompt at the quality and
landscape size chosen in Settings, and saves them as images/pic_01.png, pic_02.png and so on, where the director's shot list
and the video renderer already look for the song's pictures. Pictures that already exist are kept, so a retry only makes the
missing ones. Refuses when the whole set would pass the run cap or the month cap. The key comes from media_cfg and is never printed."""
import os, sys, json, io, time
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C
import media_cfg, image_openai as IO, prompt_pack, visuals_cfg as V

WORKERS = 3
TAIL = " Wide 16:9 cinematic frame. No text, no letters, no logos, no watermarks, no close up of a face, no real people."


def full_prompt(pack, item):
    """The shared style line, then this picture's scene. The motion hint stays out of the picture prompt."""
    return (str(pack.get("style_line") or "").strip() + " " + str(item.get("prompt") or "").strip() + TAIL).strip()[:3500]


def plan(pack, count=None):
    items = list(pack.get("prompts") or [])
    if count: items = items[:int(count)]
    return items


def total_cost(n, quality, size):
    return round(n * IO.estimate(quality, size), 3)


def check_total(n, quality, size, cfg=None):
    """Raise ValueError when the whole set would pass the one-run cap. Returns the cost."""
    cfg = cfg or media_cfg.load()
    cost = total_cost(n, quality, size)
    cap = float(cfg["max_run_usd"])
    if cost > cap:
        raise ValueError("%d pictures at %s cost about $%.2f, over the run cap of $%.2f. Raise the run cap in Settings (Pictures and voice) or choose a lower quality." % (n, quality, cost, cap))
    return cost


def name_for(i): return "pic_%02d.png" % i


def make_one(prompt, quality, size, key):
    last = None
    for attempt in range(3):
        try:
            return IO.request_image(prompt, quality, key, size)
        except RuntimeError as e:
            last = e
            if "HTTP 4" in str(e) and "HTTP 429" not in str(e): break  # a refused prompt will not work on retry
            time.sleep(4 * (attempt + 1))
    raise last


def main(argv):
    if not argv or argv[0].startswith("-"):
        sys.exit("usage: song_images_openai.py <slug> [--estimate] [--force] [--count N]")
    slug = argv[0]; D = C.song_dir(slug); cfg = media_cfg.load()
    q, size = cfg["image_quality"], cfg["image_size_landscape"]
    pack = prompt_pack.load(D)
    if not pack or not pack.get("prompts"): sys.exit("navaan: prompt_pack.json is missing. Run the prompt step first.")
    count = int(argv[argv.index("--count") + 1]) if "--count" in argv else None
    tr = "--try" in argv   # a test: only the first 2 prompts, saved as try_01.png and try_02.png next to the song files, never used by the video
    items = plan(pack, 2 if tr else count)
    nm = (lambda i: "try_%02d.png" % i) if tr else name_for
    imgdir = D if tr else os.path.join(D, "images"); os.makedirs(imgdir, exist_ok=True)
    todo = [(i, it) for i, it in enumerate(items, 1) if tr or "--force" in argv or not os.path.exists(os.path.join(imgdir, nm(i)))]
    try: cost = check_total(len(todo), q, size, cfg)
    except ValueError as e: sys.exit("navaan: " + str(e))
    if "--estimate" in argv:
        print(json.dumps({"model": IO.MODEL, "size": size, "quality": q, "pictures": len(todo), "usd": cost})); return 0
    if not todo: print("all %d pictures already exist. Use --force to make them again." % len(items)); return 0
    key = media_cfg.get_key("openai")
    if not key: sys.exit("navaan: no OpenAI key. Paste it in Settings, Pictures and voice.")
    if not tr and len(V.own_images(D)) + len(todo) > V.MAX_IMAGES and "--force" not in argv:
        sys.exit("navaan: this would pass the limit of %d pictures for a song." % V.MAX_IMAGES)
    failed = []

    def work(t):
        i, it = t
        try:
            raw = make_one(full_prompt(pack, it), q, size, key)
        except RuntimeError as e:
            failed.append((i, str(e))); return
        media_cfg.add_usage(openai_usd=IO.estimate(q, size))  # spent now, whatever happens to the file
        with open(os.path.join(imgdir, nm(i)), "wb") as f: f.write(raw)
        print("picture %d of %d saved" % (i, len(items)), flush=True)
    with ThreadPoolExecutor(WORKERS) as ex: list(ex.map(work, todo))
    if failed:
        for i, why in sorted(failed): print("picture %d failed: %s" % (i, why))
        sys.exit("navaan: %d of %d pictures failed. Retry the step, it only makes the missing ones." % (len(failed), len(todo)))
    print("%d pictures made with OpenAI %s %s %s, about $%.2f" % (len(todo), IO.MODEL, size, q, cost))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""image_openai.py <slug> [--estimate] [--force]  make the background picture for an inspiration short with the OpenAI image API.

Reads the prompt from songs/<slug>/scenes/background.txt (written by the inspiration-visual skill, no spend). Makes ONE portrait
picture at the model, quality and size chosen in Settings (default gpt-image-2.5-flare, high, 1152x2048 which is exactly 9:16), fits it to 1080x1920 without stretching, writes background.png and
keeps the raw answer as scenes/background_openai.png. Refuses when the month or run cap would be passed, and when a background
already exists unless --force. The key comes from media_cfg (openai.env or OPENAI_API_KEY) and is never printed.

This file is also the one place that talks to the OpenAI image API for songs: request_image (a new picture from words) and
request_edit (a new picture from words plus reference pictures, which is how one person stays the same person across a film).
"""
import os, sys, io, json, base64, time, glob, uuid, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C
import media_cfg
import navaan_log as L
LOG = L.get("image_openai")

DEFAULT_MODEL = "gpt-image-2.5-flare"
# Dollars for one picture on the older gpt-image-2 by size and quality. Used for the cap and the estimate card, not for billing.
OLD_PRICE = {"1024x1536": {"low": 0.005, "medium": 0.041, "high": 0.165}, "1152x2048": {"low": 0.008, "medium": 0.062, "high": 0.248},
             "1792x1008": {"low": 0.007, "medium": 0.048, "high": 0.19}, "1536x864": {"low": 0.005, "medium": 0.035, "high": 0.14}}
# The 2.5 models bill by tokens: image output $30 per million, image input $8 per million. Measured at high: 1234 output tokens at
# 1792x1008 and 1413 at 1152x2048, so tokens are about 649 + 324 per megapixel. The other qualities are scaled from high (a guess, kept on
# the safe side). Each reference picture adds about 1508 input tokens.
OUT_PER_M, IN_PER_M, REF_TOKENS = 30.0, 8.0, 1508
QUALITY_X = {"low": 0.2, "medium": 0.45, "high": 1.0, "xhigh": 2.0, "max": 3.5}
OUT_W, OUT_H = 1080, 1920


def model_name(cfg=None):
    """The image model: the environment override, else the Settings choice, else the default."""
    env = os.environ.get("NAVAAN_OPENAI_IMAGE_MODEL")
    if env: return env
    try: return (cfg or media_cfg.load()).get("image_model") or DEFAULT_MODEL
    except Exception as _e: L.soft(LOG, "model_name_error"); return DEFAULT_MODEL


def estimate(quality, size="1152x2048", model=None, refs=0):
    """Approximate dollars for one picture. refs is the number of reference pictures sent with it (an edit)."""
    model = model or model_name()
    if model == "gpt-image-2":
        t = OLD_PRICE.get(size, OLD_PRICE["1152x2048"])
        return t.get(quality, t["high"])
    w, h = (int(x) for x in size.split("x"))
    tokens = (649 + 324 * (w * h / 1e6)) * QUALITY_X.get(quality, 1.0)
    return round(tokens * OUT_PER_M / 1e6 + refs * REF_TOKENS * IN_PER_M / 1e6, 4)


def check_cap(quality, cfg=None, size=None):
    """Raise ValueError when this picture would pass the one-run cap."""
    cfg = cfg or media_cfg.load()
    cost = estimate(quality, size or cfg["image_size"], model_name(cfg))
    if cost > float(cfg["max_run_usd"]):
        raise ValueError("One %s picture costs about $%.2f, over the run cap of $%.2f set in Settings." % (quality, cost, float(cfg["max_run_usd"])))
    return cost


def fit_portrait(raw, w=OUT_W, h=OUT_H):
    """Scale to cover w x h and crop the middle. Never stretches."""
    from PIL import Image
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    s = max(w / im.width, h / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    l, t = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((l, t, l + w, t + h))


def _send(req, key):
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        msg = ""
        try: msg = json.load(e).get("error", {}).get("message", "")
        except Exception as _e: L.soft(LOG, "send_error"); pass
        raise RuntimeError("OpenAI refused the picture (HTTP %s). %s" % (e.code, msg.replace(key, "<key>")[:200]))
    except Exception as e:
        raise RuntimeError("Could not reach OpenAI: " + str(e).replace(key, "<key>")[:160])
    item = (d.get("data") or [{}])[0]
    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"])
    if item.get("url"):
        with urllib.request.urlopen(item["url"], timeout=120) as r:
            return r.read()
    raise RuntimeError("OpenAI answered without a picture.")


def request_image(prompt, quality, key, size="1152x2048", model=None):
    """A new picture from words."""
    body = json.dumps({"model": model or model_name(), "prompt": prompt, "size": size, "quality": quality, "n": 1}).encode()
    req = urllib.request.Request("https://api.openai.com/v1/images/generations", data=body, method="POST",
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    return _send(req, key)


def request_edit(prompt, refs, quality, key, size="1152x2048", model=None):
    """A new picture from words plus 1 to 16 reference pictures (file paths or bytes). The people in the references are kept."""
    b = uuid.uuid4().hex; parts = []
    for k, v in (("model", model or model_name()), ("prompt", prompt), ("size", size), ("quality", quality)):
        parts.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n" % (b, k, v)).encode())
    for i, r in enumerate(refs):
        data = r if isinstance(r, (bytes, bytearray)) else open(r, "rb").read()
        parts.append(("--%s\r\nContent-Disposition: form-data; name=\"image[]\"; filename=\"ref_%d.png\"\r\nContent-Type: image/png\r\n\r\n" % (b, i)).encode() + bytes(data) + b"\r\n")
    parts.append(("--%s--\r\n" % b).encode())
    req = urllib.request.Request("https://api.openai.com/v1/images/edits", data=b"".join(parts), method="POST",
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "multipart/form-data; boundary=" + b})
    return _send(req, key)


def main(argv):
    if not argv or argv[0].startswith("-"):
        sys.exit("usage: image_openai.py <slug> [--estimate] [--force]")
    slug = argv[0]
    D = C.song_dir(slug)
    cfg = media_cfg.load()
    q = cfg["image_quality"]
    model = model_name(cfg)
    try:
        cost = check_cap(q, cfg)
    except ValueError as e:
        L.ignored(LOG, "main: ValueError (optional or expected)", e)
        sys.exit("navaan: " + str(e))
    if "--estimate" in argv:
        print(json.dumps({"model": model, "size": cfg["image_size"], "quality": q, "usd": cost}))
        return 0
    have = [p for e in ("jpg", "jpeg", "png", "webp") for p in glob.glob(os.path.join(D, "background." + e))]
    if have and "--force" not in argv:
        print("background already exists (%s). Use --force to make a new one." % os.path.basename(have[0]))
        return 0
    pf = os.path.join(D, "scenes", "background.txt")
    prompt = open(pf, encoding="utf-8").read().strip() if os.path.exists(pf) else ""
    if len(prompt) < 20:
        sys.exit("navaan: scenes/background.txt is missing or empty. Run the prompt step first.")
    key = media_cfg.get_key("openai")
    if not key:
        sys.exit("navaan: no OpenAI key. Paste it in Settings, Pictures and voice.")
    raw = request_image(prompt[:3500], q, key, cfg["image_size"], model)
    media_cfg.add_usage(openai_usd=cost)  # spent now, whatever happens to the file
    os.makedirs(os.path.join(D, "scenes"), exist_ok=True)
    with open(os.path.join(D, "scenes", "background_openai.png"), "wb") as f:
        f.write(raw)
    out = fit_portrait(raw)
    for p in have:  # keep the old one out of the way, not as background.*
        os.replace(p, os.path.join(D, "scenes", "background_prev" + os.path.splitext(p)[1]))
    out.save(os.path.join(D, "background.png"), optimize=True)
    print("background.png %dx%d from OpenAI %s %s, about $%.3f" % (OUT_W, OUT_H, model, q, cost))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

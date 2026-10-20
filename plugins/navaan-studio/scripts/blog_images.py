#!/usr/bin/env python3
"""Author: Navjyot Nishant
Created: 2026-10-20
Last updated: 2026-10-20
Description: the images of a blog post (NAV-139): a cover drawn with Remotion and a few images through the article, planned by Claude (images.json, no spend), made here, stored in the bucket and put into both drafts.

  blog_images.py check <slug>       say what is wrong with images.json, or that it can be made (the images skill runs this before it stops)
  blog_images.py render <slug>      draw the covers (dev.to 1000x420, LinkedIn 1200x627) and the planned figures as PNG stills with Remotion, free; a cover falls back to a Pillow drawing when Remotion is not installed
  blog_images.py pictures <slug>    make the planned `picture` images with the OpenAI image API (behind the credits approval; --estimate prints the cost)
  blog_images.py embed <slug>       put the cover and the images into devto.md and linkedin_article.md

images.json:  {"cover": {"title", "kicker", "chips": [..], "palette", "motif"},
               "inline": [{"id", "kind": "figure", "treatment", "data", "alt", "after"} | {"id", "kind": "picture", "prompt", "alt", "after"}], "look": "art direction for pictures"}
A figure is one of the shorts' scene treatments drawn as a still (a flow, a comparison, a checklist, a timeline, a chart ...); a figure with a number needs a verified source, exactly as in a short. A picture is
the only thing that costs money. `after` is the heading text the image goes under. Every image gets a permanent public address (the bucket, served at /img/blog/<slug>/<file>) because dev.to needs one.
"""
import os, sys, io, re, json, hashlib, shutil, subprocess, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C
import navaan_log as L
import visuals_plan as V
LOG = L.get("blog_images")

PALETTES = ("midnight", "indigo", "forest", "ember", "ocean", "slate", "paper", "mono")   # mirrored in remotion/src/BlogCover.tsx (a test keeps them equal)
MOTIFS = ("nodes", "grid", "waves", "rings", "blocks", "stripes", "none")
COVERS = {"devto": (1000, 420), "linkedin": (1200, 627)}
FIGURE_W = 1080
FIGURE_H = {"flow": 1500, "timeline": 1400, "chat": 1250, "chart": 1350, "ring": 1350, "compare": 1400, "checklist": 1100, "bars": 1250, "stat": 1100, "strike": 1200}   # the height of each treatment's content, so a figure has no empty foot
FIGURES = tuple(t for t in V.SCENES if t != "hook")   # a figure is a treatment that makes sense as a still
MANIFEST = "post_images.json"
DRAFTS = ("devto.md", "linkedin_article.md")
LIMITS = "Landscape 3:2. No words, letters, numbers, logos or readable screen text anywhere in the image; screens and cards show only soft abstract shapes."
DEFAULT_LOOK = ("Modern contemporary editorial illustration: one strong subject or abstract form, flat or soft-gradient colour with fine grain, a limited palette, generous negative space, crisp and minimal. "
                "Not painterly, not cinematic, no clip-art, no stock-photo look.")


def _p(D, n): return os.path.join(D, n)
def _mt(D, n): return os.path.getmtime(_p(D, n)) if os.path.exists(_p(D, n)) else 0.0


# ---------- the plan ----------
def plan_errors(plan):
    """What is wrong with an images.json document (a list of sentences; empty when it can be made)."""
    if not isinstance(plan, dict): return ["images.json must be an object"]
    errs, cv = [], plan.get("cover")
    if not isinstance(cv, dict): return ["images.json needs a \"cover\""]
    for k, hi in (("title", 90), ("kicker", 30)):
        v = cv.get(k)
        if not isinstance(v, str) or not v.strip() or len(v) > hi: errs.append(f"cover.{k} must be text of at most {hi} characters")
    ch = cv.get("chips", [])
    if not isinstance(ch, list) or len(ch) > 4 or any(not isinstance(c, str) or not c.strip() or len(c) > 18 for c in ch): errs.append("cover.chips: at most 4 words of at most 18 characters")
    if cv.get("palette") not in PALETTES: errs.append(f"cover.palette must be one of {', '.join(PALETTES)}")
    if cv.get("motif") not in MOTIFS: errs.append(f"cover.motif must be one of {', '.join(MOTIFS)}")
    inl = plan.get("inline", [])
    if not isinstance(inl, list) or len(inl) > 4: return errs + ["inline: at most 4 images"]
    seen = set()
    for i, x in enumerate(inl, 1):
        if not isinstance(x, dict): errs.append(f"inline {i} is not an object"); continue
        iid = x.get("id")
        if not isinstance(iid, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,15}", iid) or iid in seen: errs.append(f"inline {i}: id must be unique lowercase letters, digits and _"); continue
        seen.add(iid)
        if not isinstance(x.get("alt"), str) or not 5 <= len(x["alt"]) <= 160: errs.append(f"{iid}: alt text of 5 to 160 characters")
        if x.get("after") is not None and not isinstance(x["after"], str): errs.append(f"{iid}: after is the text of a heading")
        if x.get("title") is not None and (not isinstance(x["title"], str) or len(x["title"]) > 60): errs.append(f"{iid}: title is text of at most 60 characters")
        if x.get("kind") == "figure":
            if x.get("treatment") not in FIGURES: errs.append(f"{iid}: treatment must be one of {', '.join(FIGURES)}"); continue
            errs += [f"{iid}: {e}" for e in V.validate({"beats": [{"line": 0, "treatment": x["treatment"], "data": x.get("data") or {}}]}, "aha", 1, strict=True)]   # strict: a number needs a source, never the sample label
        elif x.get("kind") == "picture":
            if not isinstance(x.get("prompt"), str) or not 20 <= len(x["prompt"]) <= 600: errs.append(f"{iid}: a picture needs a prompt of 20 to 600 characters")
        else: errs.append(f"{iid}: kind must be figure or picture")
    if plan.get("look") is not None and (not isinstance(plan["look"], str) or len(plan["look"]) > 400): errs.append("look: text of at most 400 characters")
    return errs


def load_plan(D):
    p = C.load_json(_p(D, "images.json"), default=None)
    return p if isinstance(p, dict) and not plan_errors(p) else None


def plan_ok(D): return load_plan(D) is not None


def pictures(plan): return [x for x in (plan or {}).get("inline", []) if x.get("kind") == "picture"]
def figures(plan): return [x for x in (plan or {}).get("inline", []) if x.get("kind") == "figure"]


def post_title(D, plan):
    """The title on the cover: the dev.to title, else the one in the plan."""
    try:
        m = re.match(r"\A---\r?\n(.*?)\r?\n---", open(_p(D, "devto.md"), encoding="utf-8").read(), re.S)
        for line in (m.group(1).splitlines() if m else []):
            if line.startswith("title:"): return line.split(":", 1)[1].strip().strip("\"'") or plan["cover"]["title"]
    except OSError: L.ignored(LOG, "post_title: no draft yet, the plan's title is used")
    return plan["cover"]["title"]


# ---------- drawing ----------
def _remotion(comp, props, out):
    import inspire_render as R
    if not R.remotion_ready(): raise RuntimeError("remotion is not installed")
    chrome = os.environ.get("NAVAAN_CHROME") or next((c for c in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/usr/bin/google-chrome", "/usr/bin/chromium") if os.path.exists(c)), "")
    env = dict(os.environ); env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + env.get("PATH", "")
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f: json.dump(props, f, ensure_ascii=False); pf = f.name
    try:
        cmd = ["npx", "--no-install", "remotion", "still", "src/index.ts", comp, out, f"--props={pf}", "--frame=0", "--log=error", "--overwrite"]
        if chrome: cmd += [f"--browser-executable={chrome}", "--chrome-mode=chrome-for-testing"]
        subprocess.run(cmd, cwd=R.remotion_dir(), check=True, env=env)
    finally: os.unlink(pf)


def cover_fallback(plan, title, size, out):
    """A plain cover with Pillow when Remotion is not there: the palette as a gradient, the title, the chips. The step must not block on a missing renderer."""
    from PIL import Image, ImageDraw
    from make_cover import latin, GOLD
    w, h = size; cv = plan["cover"]
    pal = {"midnight": ((11, 16, 32), (27, 42, 74)), "indigo": ((26, 20, 70), (59, 47, 160)), "forest": ((14, 42, 34), (30, 91, 69)), "ember": ((42, 18, 16), (122, 46, 30)), "ocean": ((8, 36, 51), (14, 108, 138)),
           "slate": ((30, 35, 41), (58, 67, 77)), "paper": ((245, 241, 232), (231, 223, 206)), "mono": ((10, 10, 10), (38, 38, 38))}[cv["palette"]]
    im = Image.new("RGB", (w, h)); px = ImageDraw.Draw(im)
    for y in range(h):
        t = y / max(1, h - 1); px.line([(0, y), (w, y)], fill=tuple(round(pal[0][i] + (pal[1][i] - pal[0][i]) * t) for i in range(3)))
    ink = (31, 35, 40) if cv["palette"] == "paper" else (245, 247, 250); pad = round(h * 0.13); d = ImageDraw.Draw(im)
    d.text((pad, pad), cv["kicker"].upper(), font=latin(round(h * 0.05)), fill=GOLD)
    size_px = round(h * 0.15)
    while size_px > h * 0.07:   # the largest size at which the title wraps into the column
        f = latin(size_px); lines, cur = [], ""
        for wd in title.split():
            t = (cur + " " + wd).strip()
            if d.textlength(t, font=f) <= w * 0.54: cur = t
            else: lines.append(cur); cur = wd
        lines.append(cur)
        if len(lines) * size_px * 1.1 <= h * 0.5: break
        size_px = round(size_px * 0.94)
    y = pad + round(h * 0.16)
    for ln in lines[:4]: d.text((pad, y), ln, font=f, fill=ink); y += round(size_px * 1.1)
    x = pad; cf = latin(round(h * 0.045)); yb = h - pad - round(h * 0.07)
    for c in cv.get("chips", [])[:4]:
        tw = d.textlength(c, font=cf); d.rounded_rectangle((x, yb, x + tw + h * 0.07, yb + h * 0.075), radius=h, outline=ink, width=max(1, h // 200)); d.text((x + h * 0.035, yb + h * 0.012), c, font=cf, fill=ink); x += tw + h * 0.11
    im.save(out, optimize=True)


def render(slug):
    D = C.song_dir(slug); plan = load_plan(D)
    if not plan: print("navaan: images.json is missing or not usable: " + "; ".join(plan_errors(C.load_json(_p(D, "images.json"), default=None))) ); return 2
    title = post_title(D, plan); cv = plan["cover"]; made = {"cover": {}, "inline": []}; notes = []
    for dest, (w, h) in COVERS.items():
        name = f"post_cover_{dest}.png"; out = _p(D, name)
        props = {"width": w, "height": h, "title": title, "kicker": cv["kicker"], "chips": cv.get("chips", []), "palette": cv["palette"], "motif": cv["motif"], "seed": slug, "brand": (C.cfg("artist.name") or "NAVAAN")}
        try: _remotion("BlogCover", props, out)
        except (RuntimeError, subprocess.CalledProcessError, OSError) as e:
            L.event(LOG, "warning", "cover_fallback", slug=slug, dest=dest, reason=str(e)[:200]); notes.append(f"the {dest} cover was drawn without Remotion ({str(e)[:80]})"); cover_fallback(plan, title, (w, h), out)
        made["cover"][dest] = {"file": name}
        print(f"cover {dest}: {name}", flush=True)
    for x in figures(plan):
        name = f"post_fig_{x['id']}.png"
        props = {"width": FIGURE_W, "height": FIGURE_H.get(x["treatment"], 1400), "treatment": x["treatment"], "data": x.get("data") or {}, "text": x.get("title") or x["alt"][:60]}
        try: _remotion("BlogFigure", props, _p(D, name)); made["inline"].append({"id": x["id"], "kind": "figure", "file": name, "alt": x["alt"], "after": x.get("after")}); print(f"figure {x['id']}: {name}", flush=True)
        except (RuntimeError, subprocess.CalledProcessError, OSError) as e:
            L.event(LOG, "warning", "figure_skipped", slug=slug, id=x["id"], reason=str(e)[:200]); notes.append(f"figure {x['id']} was skipped: Remotion could not draw it ({str(e)[:80]})")
    keep = [i for i in _manifest(D).get("inline", []) if i.get("kind") == "picture"]   # pictures made earlier stay
    made["inline"] += [i for i in keep if i["id"] in {p["id"] for p in pictures(plan)}]
    _save_manifest(D, {**made, "notes": notes})
    for n in notes: print("note:", n)
    return 0


# ---------- the bucket and the public address ----------
def public_base():
    """Where the public host is: NAVAAN_PUBLIC_URL, else the first listener or public host, else '' (an address without a host)."""
    u = os.environ.get("NAVAAN_PUBLIC_URL", "").strip().rstrip("/")
    if u: return u
    for var in ("NAVAAN_LISTENER_HOSTS", "NAVAAN_PUBLIC_HOST"):
        h = next((x.strip() for x in os.environ.get(var, "").split(",") if x.strip()), "")
        if h: return "https://" + h
    return ""


def store(slug, path):
    """Put an image in the bucket under a name that carries its hash (so a replaced image has a new address and the year-long cache is right) and return its public address."""
    import objstore, catalog_store as K
    data = open(path, "rb").read(); stem, ext = os.path.splitext(os.path.basename(path))
    name = f"{stem}-{hashlib.sha256(data).hexdigest()[:8]}{ext.lower()}"
    objstore.put(f"{K.ARTIST}/blog/{slug}/{name}", data, "image/png" if ext.lower() == ".png" else "image/jpeg")
    return f"{public_base()}/img/blog/{slug}/{name}", name


def _manifest(D): return C.load_json(_p(D, MANIFEST), default={}) or {}
def _save_manifest(D, m):
    with open(_p(D, MANIFEST), "w", encoding="utf-8") as f: json.dump({**m, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, f, indent=1, ensure_ascii=False)


def rendered(D):
    """The covers and the figures of the current plan are drawn."""
    plan, m = load_plan(D), _manifest(D)
    return bool(plan and m.get("cover", {}).get("devto") and os.path.exists(_p(D, "post_cover_devto.png")) and _mt(D, MANIFEST) >= _mt(D, "images.json")
                and all(any(i["id"] == x["id"] and os.path.exists(_p(D, i["file"])) for i in m.get("inline", [])) for x in figures(plan)) or False)


def pictures_done(D):
    """True when the plan holds no picture, or every planned picture is made."""
    plan = load_plan(D); m = _manifest(D)
    return bool(plan) and all(any(i["id"] == x["id"] and i.get("kind") == "picture" and os.path.exists(_p(D, i["file"])) for i in m.get("inline", [])) for x in pictures(plan))


# ---------- pictures (the only spend) ----------
def make_pictures(slug, estimate_only=False):
    import media_cfg, image_openai as IO
    D = C.song_dir(slug); plan = load_plan(D)
    if not plan: print("navaan: images.json is missing or not usable"); return 2
    cfg = media_cfg.load(); q, size, model = cfg["image_quality"], cfg.get("image_size_landscape") or "1536x1024", IO.model_name(cfg)
    m = _manifest(D); have = {i["id"] for i in m.get("inline", []) if i.get("kind") == "picture" and os.path.exists(_p(D, i["file"]))}
    todo = [x for x in pictures(plan) if x["id"] not in have]; each = IO.estimate(q, size, model); total = round(each * len(todo), 3)
    if estimate_only: print(json.dumps({"model": model, "size": size, "quality": q, "pictures": len(todo), "usd": total})); return 0
    if not todo: print("no pictures to make"); return 0
    if total > float(cfg["max_run_usd"]): print("navaan: %d %s pictures cost about $%.2f, over the run cap of $%.2f set in Settings." % (len(todo), q, total, float(cfg["max_run_usd"]))); return 4
    key = media_cfg.get_key("openai")
    if not key: print("navaan: no OpenAI key. Paste it in Settings, Pictures and voice."); return 4
    look = (plan.get("look") or DEFAULT_LOOK)
    for x in todo:
        raw = IO.request_image((x["prompt"] + "\n\nArt direction: " + look + "\n\n" + LIMITS)[:3500], q, key, size, model)
        media_cfg.add_usage(openai_usd=each)   # spent now, whatever happens to the file
        from PIL import Image
        im = Image.open(io.BytesIO(raw)).convert("RGB"); s = max(1200 / im.width, 800 / im.height); im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
        l, t = (im.width - 1200) // 2, (im.height - 800) // 2; name = f"post_pic_{x['id']}.jpg"; im.crop((l, t, l + 1200, t + 800)).save(_p(D, name), quality=88, optimize=True)
        m.setdefault("inline", []); m["inline"] = [i for i in m["inline"] if i["id"] != x["id"]] + [{"id": x["id"], "kind": "picture", "file": name, "alt": x["alt"], "after": x.get("after")}]
        _save_manifest(D, m); print(f"picture {x['id']}: {name}", flush=True)
    print("%d pictures made, about $%.2f" % (len(todo), total)); return 0


# ---------- into the drafts ----------
def _is_ours(line, slug): return bool(re.match(r"^!\[[^\]]*\]\([^)]*/img/blog/" + re.escape(slug) + r"/[^)]+\)\s*$", line))


def insert_images(text, slug, items, cover_url=None):
    """The draft with our images in it: earlier ones removed first (so a run twice changes nothing), each new one after the first paragraph under the heading it is planned for, the dev.to cover in the front matter."""
    lines = [l for l in text.replace("\r\n", "\n").split("\n") if not _is_ours(l, slug)]
    fm_end = 0
    if lines and lines[0].strip() == "---":
        fm_end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), 0)
        if cover_url is not None:
            k = next((i for i in range(1, fm_end) if lines[i].startswith("cover_image:")), None)
            if k is None: lines.insert(fm_end, f"cover_image: {cover_url}"); fm_end += 1
            else: lines[k] = f"cover_image: {cover_url}"
    for x in items:
        target = (x.get("after") or "").strip().lower(); at = None
        if target:
            at = next((i for i, l in enumerate(lines) if re.match(r"^#{1,6}\s", l) and target in l.lower()), None)
        i = (at + 1) if at is not None else fm_end + 1
        while i < len(lines) and not lines[i].strip(): i += 1   # past blank lines after the heading
        if at is None:   # no heading named: after the first paragraph of the body, never inside the front matter
            while i < len(lines) and re.match(r"^#{1,6}\s", lines[i]): i += 1
            while i < len(lines) and not lines[i].strip(): i += 1
        while i < len(lines) and lines[i].strip() and not lines[i].startswith(("```", "- ", "* ", "1.")): i += 1   # to the end of that paragraph
        lines[i:i] = ["", f"![{x['alt']}]({x['url']})", ""]
    out = "\n".join(lines); return re.sub(r"\n{3,}", "\n\n", out).rstrip("\n") + "\n"


def embed(slug):
    D = C.song_dir(slug); plan = load_plan(D)
    if not plan: print("navaan: images.json is missing or not usable"); return 2
    m = _manifest(D)
    if not m.get("cover", {}).get("devto"): print("navaan: draw the images first"); return 2
    for dest in COVERS:   # every image gets its public address; the same file stored twice has the same name
        c = m["cover"][dest]; c["url"], c["name"] = store(slug, _p(D, c["file"]))
    items = []
    for x in plan.get("inline", []):
        i = next((i for i in m.get("inline", []) if i["id"] == x["id"] and os.path.exists(_p(D, i["file"]))), None)
        if not i: continue
        i["url"], i["name"] = store(slug, _p(D, i["file"])); items.append({**i, "after": x.get("after")})
    for n in DRAFTS:
        if not os.path.exists(_p(D, n)): continue
        text = open(_p(D, n), encoding="utf-8").read()
        new = insert_images(text, slug, items, cover_url=m["cover"]["devto"]["url"] if n == "devto.md" else None)
        if new != text:
            with open(_p(D, n), "w", encoding="utf-8") as f: f.write(new)
    m["embedded"] = [i["id"] for i in items]; _save_manifest(D, m)
    print(f"cover and {len(items)} image(s) are in both posts"); return 0


def embedded(D):
    """The covers and every made image are in the drafts at their public addresses."""
    m = _manifest(D)
    if not load_plan(D) or not m.get("cover", {}).get("devto", {}).get("url"): return False
    try: dv = open(_p(D, "devto.md"), encoding="utf-8").read(); la = open(_p(D, "linkedin_article.md"), encoding="utf-8").read()
    except OSError: return False   # expected: a draft is missing, so the images are not in it
    if m["cover"]["devto"]["url"] not in dv: return False
    made = sorted(i["id"] for i in m.get("inline", []) if os.path.exists(_p(D, i["file"])))
    return sorted(m.get("embedded", [])) == made and all(i["url"] in dv and i["url"] in la for i in m.get("inline", []) if i["id"] in made and i.get("url"))


def check(slug):
    D = C.song_dir(slug); plan = C.load_json(_p(D, "images.json"), default=None)
    errs = plan_errors(plan) if plan is not None else ["images.json is missing"]
    if errs: print("navaan: images.json cannot be made yet:\n" + "\n".join("- " + e for e in errs)); return 1
    print(f"images.json ok: a cover, {len(figures(plan))} figure(s), {len(pictures(plan))} picture(s) (only pictures cost money)"); return 0


def main(a):
    if len(a) < 2 or a[0] not in ("render", "pictures", "embed", "check"): sys.exit(__doc__)
    if a[0] == "check": sys.exit(check(a[1]))
    if a[0] == "render": sys.exit(render(a[1]))
    if a[0] == "pictures": sys.exit(make_pictures(a[1], "--estimate" in a))
    sys.exit(embed(a[1]))


if __name__ == "__main__":
    main(sys.argv[1:])

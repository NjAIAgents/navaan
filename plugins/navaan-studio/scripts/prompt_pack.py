#!/usr/bin/env python3
"""prompt_pack.py <slug> [--count N]

Writes songs/<slug>/prompt_pack.json: the director's picture plan for a song. One story idea, one recurring character, a shared
look, and one scene prompt per picture, each with a motion hint (what in the picture could softly move). The prompts can be pasted
into Gemini or ChatGPT by hand, or sent to the OpenAI image API by song_images_openai.py.

  {"concept": "...", "character": "...", "style_line": "...", "aspect": "16:9",
   "prompts": [{"n": 1, "section": "Verse 1", "lyric": "...", "prompt": "...", "motion": "..."}], "made_at": "..."}

Claude only writes the text (claude -p with no tools). Nothing is generated and nothing is spent here."""
import os, sys, json, re, math, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C
import shots_prep, visuals_cfg as V
import navaan_log as L
LOG = L.get("prompt_pack")

MIN_COUNT, MAX_COUNT, SECONDS_PER_PICTURE = 6, V.MAX_IMAGES, 10.0
ASPECT = "16:9"


def pack_path(D):
    return os.path.join(D, "prompt_pack.json")


def load(D):
    return C.load_json(pack_path(D), default=None)


def default_count(duration):
    """About one picture per 10 seconds, never fewer than 6 or more than the picture limit, and never shorter than a minimum shot."""
    n = int(round(duration / SECONDS_PER_PICTURE))
    n = min(n, int(duration // shots_prep.MIN_SHOT) or 1)
    return max(MIN_COUNT, min(MAX_COUNT, n))


def allocate(sections, count):
    """Spread count picture slots over the sections by their length. Every section gets at least one while slots last."""
    total = sum(max(0.1, s["end"] - s["start"]) for s in sections) or 1.0
    raw = [count * max(0.1, s["end"] - s["start"]) / total for s in sections]
    n = [int(math.floor(x)) for x in raw]
    left = count - sum(n)
    for i in sorted(range(len(raw)), key=lambda i: raw[i] - n[i], reverse=True)[:max(0, left)]:
        n[i] += 1
    for i in range(len(n)):
        if n[i] == 0:
            j = max(range(len(n)), key=lambda k: n[k])
            if n[j] > 1: n[j] -= 1; n[i] = 1
    slots = []
    for s, k in zip(sections, n):
        for j in range(k):
            slots.append({"section": s["label"], "part": j + 1, "of": k, "lines": s["lines"]})
    return slots


ROLES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "roles")
DIRECTOR_MODELS = ("gpt-5", "gpt-4.1")
runner_model = [""]


def role_text(name):
    """The prompt of one role (roles/<name>.md). The three roles: look (art director), story (story director), camera (camera operator)."""
    with open(os.path.join(ROLES_DIR, name + ".md"), encoding="utf-8") as f: return f.read()


def fill(text, **kw):
    for k, v in kw.items(): text = text.replace("<<%s>>" % k, str(v))
    return text


_FEMALE = re.compile(r"\b(female|woman|women|girl|soprano|mezzo|alto|her voice)\b", re.I)
_MALE = re.compile(r"\b(male|man|men|boy|baritone|tenor|bass|his voice)\b", re.I)


def singer(style):
    """The singer's gender as the song's style text states it: "male", "female", or "" when it does not say (or says both)."""
    f, m = bool(_FEMALE.search(style or "")), bool(_MALE.search(re.sub(r"\bfemale\b", "", style or "", flags=re.I)))
    return "female" if f and not m else "male" if m and not f else ""


def voice_note(ctx_or_style):
    """One sentence for the directors: who sings, so the film does not show someone else."""
    style = ctx_or_style.get("style") if isinstance(ctx_or_style, dict) else ctx_or_style
    g = singer(style)
    if g: return f"Voice note: the singer is {'a man' if g == 'male' else 'a woman'}. The main person in the film is {'a man' if g == 'male' else 'a woman'}; never make the main person {'a woman' if g == 'male' else 'a man'}."
    return "Voice note: the singer's gender is not stated, so do not assume it. Prefer silhouettes, backs, hands and places, or a person whose gender the lyrics make clear."


def lyrics_block(ctx):
    return "\n\n".join("[%s]\n%s" % (x["label"], "\n".join(x["lines"])) for x in (ctx.get("sections") or [])) or "(no lyrics)"


def slot_lines(slots):
    return "\n".join(f'{i}. section "{s["section"]}" (picture {s["part"]} of {s["of"]} in it), lyric: ' + " / ".join(s["lines"][:4]) for i, s in enumerate(slots, 1))


def build_look_prompt(ctx):
    return fill(role_text("look"), title=ctx.get("title") or "untitled", style=ctx.get("style") or "not given", look=ctx.get("scene_override") or "none",
                camera_note=ctx.get("camera_override") or "none", lyrics=lyrics_block(ctx))


def build_prompt(ctx, slots, extra="", look=None):
    """The story director's prompt."""
    lb = ("The art director has fixed the look of the film: " + str(look.get("style_line") or "") + "\nWrite scenes that suit it.") if look else ""
    return fill(role_text("story"), title=ctx.get("title") or "untitled", style=ctx.get("style") or "not given", voice_note=voice_note(ctx), look_block=lb, extra=extra,
                lyrics=lyrics_block(ctx), n=len(slots), slots=slot_lines(slots))


def build_camera_prompt(ctx, slots, items, look):
    spans = {x["label"]: (x["start"], x["end"]) for x in (ctx.get("sections") or [])}
    lines = []
    for i, (sl, it) in enumerate(zip(slots, items), 1):
        st, en = spans.get(sl["section"], (0, 0))
        secs = round((en - st) / max(1, sl["of"]), 1)
        lines.append(f'{i}. ({sl["section"]}, about {secs} s) lyric: ' + " / ".join(sl["lines"][:2]) + " | scene: " + it["prompt"])
    return fill(role_text("camera"), title=ctx.get("title") or "untitled", style=ctx.get("style") or "not given", camera_style=(look or {}).get("camera_style") or "slow and gentle",
                camera_note=ctx.get("camera_override") or "none", scenes="\n".join(lines), n=len(slots))


def _json(text, who):
    m = re.search(r"\{.*\}", text, re.S)
    if not m: raise ValueError(who + " did not return JSON")
    return json.loads(m.group(0))


def parse_look(text):
    j = _json(text, "the art director")
    style = str(j.get("style_line") or "").strip()
    if not style: raise ValueError("the art director gave no style line")
    return {"style_line": style, "palette": str(j.get("palette") or "").strip(), "camera_style": str(j.get("camera_style") or "").strip()}


def parse_full(text, count, style=None):
    """The story director's reply as {"concept", "character", "style_line", "items": [{"prompt", "motion"}]}. A prompt may be a plain string or {"scene", "motion"}."""
    j = _json(text, "the story director")
    style = str(style or j.get("style_line") or "").strip()
    items = []
    for p in (j.get("prompts") or []):
        if isinstance(p, dict):
            scene, motion = str(p.get("scene") or p.get("prompt") or "").strip(), str(p.get("motion") or "").strip()
        else:
            scene, motion = str(p).strip(), ""
        if scene: items.append({"prompt": scene, "motion": "" if motion.lower() in ("none", "n/a") else motion})
    if not style or len(items) != count: raise ValueError(f"expected a style line and {count} prompts, got {len(items)}")
    return {"concept": str(j.get("emotion") or j.get("concept") or "").strip(), "character": str(j.get("character") or "").strip(), "style_line": style, "items": items}


def parse(text, count):
    r = parse_full(text, count)
    return r["style_line"], [i["prompt"] for i in r["items"]]


def parse_camera(text, count):
    """The camera operator's reply as a list of {"camera", "focus"}, one per scene. An unknown move becomes blank (the shot list picks one)."""
    j = _json(text, "the camera operator")
    moves = j.get("moves") or []
    if len(moves) != count: raise ValueError(f"expected {count} camera moves, got {len(moves)}")
    out = []
    for m in moves:
        m = m if isinstance(m, dict) else {"camera": m}
        cam = str(m.get("camera") or "").strip().lower().replace(" ", "_")
        f = m.get("focus")
        try:
            f = [round(min(1.0, max(0.0, float(f[0]))), 2), round(min(1.0, max(0.0, float(f[1]))), 2)]
        except (TypeError, ValueError, IndexError, KeyError) as _e:
            L.ignored(LOG, "parse_camera: TypeError/ValueError/IndexError/KeyError (optional or expected)", _e)
            f = None
        out.append({"camera": cam if cam in shots_prep.CAMERAS else "", "focus": f})
    return out


def openai_runner(prompt, timeout=300):
    """Ask an OpenAI chat model. Tries each model in turn when one is not available to the key."""
    import media_cfg, urllib.request, urllib.error
    key = media_cfg.get_key("openai")
    if not key: raise RuntimeError("no OpenAI key. Paste it in Settings, Pictures and voice.")
    last = None
    for model in DIRECTOR_MODELS:
        body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}], "response_format": {"type": "json_object"}}).encode()
        req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=body, method="POST",
                                     headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                j = json.load(r)
            runner_model[0] = model
            return j["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            L.ignored(LOG, "openai_runner: HTTPError (optional or expected)", e)
            try: msg = e.read().decode("utf-8", "ignore")
            except Exception as _e: L.soft(LOG, "openai_runner_error"); msg = ""
            last = "OpenAI %s refused the request (HTTP %s). %s" % (model, e.code, msg.replace(key, "<key>")[:200])
            if e.code in (400, 404): continue
            break
        except (urllib.error.URLError, OSError, KeyError, ValueError) as e:
            L.ignored(LOG, "openai_runner: URLError/OSError/KeyError/ValueError (optional or expected)", e)
            last = "Could not use OpenAI %s: %s" % (model, str(e).replace(key, "<key>")[:160])
            break
    raise RuntimeError(last or "OpenAI did not answer")


def make(slug, count=None, runner=None):
    D = C.song_dir(slug)
    ctx = shots_prep.build_context(D)
    if not count:
        try:
            import media_cfg
            count = int(media_cfg.load()["song_pictures"])
        except Exception as _e:
            L.soft(LOG, "make_error")
            count = None
    count = int(count) if count else default_count(ctx["duration"])
    count = max(MIN_COUNT, min(MAX_COUNT, count))
    slots = allocate(ctx["sections"], count)
    who = "claude"
    if runner is None:
        try:
            import media_cfg
            use_oa = media_cfg.load().get("picture_director") == "openai" and bool(media_cfg.get_key("openai"))
        except Exception as _e:
            L.soft(LOG, "make_error")
            use_oa = False
        if use_oa:
            runner, who = openai_runner, "openai"
        else:
            import comment_reply
            runner = lambda p: comment_reply.run_claude(p, timeout=300)

    def ask(prompt, parse_fn):
        last = None
        for _ in range(2):
            try: return parse_fn(runner(prompt))
            except (ValueError, RuntimeError) as e: L.ignored(LOG, "ask: ValueError/RuntimeError (optional or expected)", e); last = e
        raise RuntimeError(f"Could not write the prompts: {last}")
    look = ask(build_look_prompt(ctx), parse_look)                                                                  # role 1: art director
    r = ask(build_prompt(ctx, slots, look=look), lambda t: parse_full(t, len(slots), look["style_line"]))            # role 2: story director
    try: moves = ask(build_camera_prompt(ctx, slots, r["items"], look), lambda t: parse_camera(t, len(slots)))      # role 3: camera operator
    except RuntimeError as _e: L.ignored(LOG, "make: RuntimeError (optional or expected)", _e); moves = [{"camera": "", "focus": None}] * len(slots)                                       # the shot list picks the moves
    pack = {"director": (who + " " + runner_model[0]).strip(), "concept": r["concept"], "character": r["character"], "style_line": look["style_line"],
            "look": look, "aspect": ASPECT,
            "prompts": [{"n": i, "section": s["section"], "lyric": " / ".join(s["lines"][:2]), "prompt": it["prompt"], "camera": mv["camera"], "focus": mv["focus"], "motion": it["motion"]}
                        for i, (s, it, mv) in enumerate(zip(slots, r["items"], moves), 1)],
            "made_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    json.dump(pack, open(pack_path(D), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    open(pack_path(D), "a").write("\n")
    return pack


def main(a):
    if not a or a[0] in ("-h", "--help"): sys.exit(__doc__)
    cnt = int(a[a.index("--count") + 1]) if "--count" in a else None
    p = make(a[0], cnt)
    print(f"{len(p['prompts'])} prompts written to prompt_pack.json. Concept: {p['concept']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

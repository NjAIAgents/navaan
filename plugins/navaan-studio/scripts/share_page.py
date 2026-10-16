"""share_page.py  the page a shared link opens: a branded card with the cover and the whole song to play (the site is free), and a way into the site, plus the Open Graph tags that make chats show it.

Author: Navjyot Nishant
Created: 2026-10-16
Last updated: 2026-10-16
Description: NAV-6 stage 2 (FR-025). Pure function, no I/O: every text from a song is escaped. The page has no scripts; the song is a plain audio element.
"""
import html

E = lambda s: html.escape(str(s), quote=True)


def render(track, token, base, colour=None, has_cover=True):
    """track {slug, title, start_ms}; base is the public origin without a trailing slash; colour the cover's dominant colour (shown while the picture loads)."""
    slug, title = track["slug"], track["title"]
    url = f"{base}/s/{E(token)}"
    img = f"{base}/img/{E(slug)}/1280.jpg"
    desc = f"{title}: listen free on NAVAAN."
    bg = E(colour) if colour and len(colour) == 7 and colour[0] == "#" else "#17243A"
    t = round(track.get("start_ms", 0) / 1000)
    site = f"/app/song/{E(slug)}"
    pic = (f'<picture><source type="image/avif" srcset="/img/{E(slug)}/320.avif 320w, /img/{E(slug)}/640.avif 640w, /img/{E(slug)}/1280.avif 1280w" sizes="(max-width: 520px) 100vw, 480px">'
           f'<source type="image/webp" srcset="/img/{E(slug)}/320.webp 320w, /img/{E(slug)}/640.webp 640w, /img/{E(slug)}/1280.webp 1280w" sizes="(max-width: 520px) 100vw, 480px">'
           f'<img src="/img/{E(slug)}/640.jpg" width="480" height="480" alt="Cover of {E(title)}" style="background:{bg}"></picture>') if has_cover else f'<div class="ph" style="background:{bg}"></div>'
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(title)} · NAVAAN</title>
<meta name="robots" content="noindex">
<meta property="og:type" content="music.song"><meta property="og:site_name" content="NAVAAN"><meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(desc)}">
<meta property="og:url" content="{url}">{f'<meta property="og:image" content="{img}">' if has_cover else ''}
<meta name="twitter:card" content="summary"><meta name="twitter:title" content="{E(title)}"><meta name="twitter:description" content="{E(desc)}">{f'<meta name="twitter:image" content="{img}">' if has_cover else ''}
<style>
:root{{color-scheme:dark}}*{{box-sizing:border-box}}
body{{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px;background:radial-gradient(900px 500px at 50% -10%,#17243A,#0B1020);color:#F2EEE7;font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{width:min(480px,100%);text-align:center}}
.brand{{letter-spacing:.2em;font-weight:700;color:#D6B477;font-size:13px;margin-bottom:20px}}
img,.ph{{width:100%;aspect-ratio:1/1;border-radius:22px;display:block;object-fit:cover;box-shadow:0 20px 60px rgba(0,0,0,.5)}}
h1{{font-family:"Cormorant Garamond",Georgia,serif;font-weight:600;font-size:34px;line-height:1.15;margin:22px 0 4px}}
p{{color:#B9B4AA;margin:0 0 18px}}audio{{width:100%;margin:6px 0 18px}}
a.go{{display:inline-flex;align-items:center;justify-content:center;min-height:48px;padding:0 24px;border-radius:14px;background:linear-gradient(135deg,#D6B477,#B58B4A);color:#0B1020;font-weight:700;text-decoration:none}}
a.go:focus-visible,audio:focus-visible{{outline:2px solid #F2EEE7;outline-offset:3px}}
</style></head>
<body><main>
<div class="brand"><img src="/app/brand/mark.png" alt="" width="63" height="42" style="width:63px;height:42px;aspect-ratio:auto;border-radius:0;box-shadow:none;display:block;margin:0 auto 6px">NAVAAN</div>
{pic}
<h1>{E(title)}</h1>
<p>Free to listen. No sign in.</p>
<audio controls preload="none" src="/s/{E(token)}/play.mp3{('#t=' + str(t)) if t else ''}">Your browser cannot play audio.</audio>
<a class="go" href="{site}">Open on NAVAAN</a>
</main></body></html>
"""

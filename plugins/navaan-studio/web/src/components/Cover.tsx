import { useState } from "react";
import type { AlbumRow } from "../lib/api";

// album: the picture is an album's own cover (/img/album/<slug>); src: show this one file instead of the sized public pictures (an album that is not published yet, for its owner).
// v: the picture's size in bytes, it changes when the cover is replaced; it goes in the address so a browser (or a cache in front) that kept the old picture for a year asks again.
export type Art = { colour: string | null; album?: boolean; src?: string; v?: number } | null | undefined;

// What to show for an album: its own cover when it has one, else the cover of its first song with a picture, else its initial.
export function albumFace(a: AlbumRow): { slug: string; art: Art } {
  if (a.art) return { slug: a.slug, art: { colour: a.art.colour, v: a.art.v, album: true, ...(a.status === "published" ? {} : { src: `/api/albums/cover/${a.slug}.png?v=${a.art.v}` }) } };
  const t = a.tracks.find((x) => x.art);
  return { slug: (t ?? a.tracks[0])?.slug ?? a.slug, art: t?.art };
}

// A cover tile. A published song with a cover in the bucket shows the picture in the right size (320/640/1280, AVIF or WebP, JPEG as the fallback) over its dominant
// colour, fading in when it has loaded (a blur-up without a layout shift: the tile has its size before the picture arrives). Anything else, or a picture that
// fails, shows the item's initial on one of four theme gradients chosen from its slug, so a list always has a face.
export function Cover({ slug, title, size = 56, art }: { slug: string; title: string; size?: number; art?: Art }) {
  const [ok, setOk] = useState(true);
  const [loaded, setLoaded] = useState(false);
  let h = 0;
  for (const ch of slug) h = (h * 31 + ch.charCodeAt(0)) % 997;
  const base = art?.album ? `/img/album/${slug}` : `/img/${slug}`;
  const q = art?.v ? `?v=${art.v}` : "";
  const set = (f: string) => [320, 640, 1280].map((w) => `${base}/${w}.${f}${q} ${w}w`).join(", ");
  return (
    <span className="cover" data-v={h % 4} style={{ width: size, fontSize: size / 2.4, ...(art?.colour ? { background: art.colour } : {}) }} aria-hidden="true">
      <b>{(title || slug).slice(0, 1).toUpperCase()}</b>
      {art && ok && (
        <picture>
          {!art.src && <><source type="image/avif" srcSet={set("avif")} sizes={`${size}px`} /><source type="image/webp" srcSet={set("webp")} sizes={`${size}px`} /></>}
          <img src={art.src ?? `${base}/640.jpg${q}`} alt="" loading="lazy" decoding="async" className={loaded ? "in" : ""} onLoad={() => setLoaded(true)} onError={() => setOk(false)} />
        </picture>
      )}
    </span>
  );
}

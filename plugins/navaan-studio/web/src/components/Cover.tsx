import { useState } from "react";

export type Art = { colour: string | null } | null | undefined;

// A cover tile. A published song with a cover in the bucket shows the picture in the right size (320/640/1280, AVIF or WebP, JPEG as the fallback) over its dominant
// colour, fading in when it has loaded (a blur-up without a layout shift: the tile has its size before the picture arrives). Anything else, or a picture that
// fails, shows the item's initial on one of four theme gradients chosen from its slug, so a list always has a face.
export function Cover({ slug, title, size = 56, art }: { slug: string; title: string; size?: number; art?: Art }) {
  const [ok, setOk] = useState(true);
  const [loaded, setLoaded] = useState(false);
  let h = 0;
  for (const ch of slug) h = (h * 31 + ch.charCodeAt(0)) % 997;
  const set = (f: string) => [320, 640, 1280].map((w) => `/img/${slug}/${w}.${f} ${w}w`).join(", ");
  return (
    <span className="cover" data-v={h % 4} style={{ width: size, fontSize: size / 2.4, ...(art?.colour ? { background: art.colour } : {}) }} aria-hidden="true">
      <b>{(title || slug).slice(0, 1).toUpperCase()}</b>
      {art && ok && (
        <picture>
          <source type="image/avif" srcSet={set("avif")} sizes={`${size}px`} />
          <source type="image/webp" srcSet={set("webp")} sizes={`${size}px`} />
          <img src={`/img/${slug}/640.jpg`} alt="" loading="lazy" decoding="async" className={loaded ? "in" : ""} onLoad={() => setLoaded(true)} onError={() => setOk(false)} />
        </picture>
      )}
    </span>
  );
}

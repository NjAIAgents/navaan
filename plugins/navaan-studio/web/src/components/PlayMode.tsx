import { useEffect, useRef, useState } from "react";
import { Cover } from "./Cover";
import { Icon } from "./Icon";
import { Lyrics } from "./Lyrics";
import { Transport } from "./Transport";
import { Volume } from "./Volume";
import { getJSON, type TrackView } from "../lib/api";
import { mmss } from "../lib/lyrics";
import { usePlayer, usePosition } from "../lib/player";

// Full screen play mode: the mini player grown to the whole screen and back. A fixed layout (the cover, the lyrics window and the controls have their sizes before anything loads), so opening it moves nothing.
export function PlayMode() {
  const p = usePlayer(); const { position, duration } = usePosition();
  const [t, setT] = useState<TrackView | null>(null);
  const close = useRef<HTMLButtonElement>(null);
  const open = p.expanded && !!p.slug;
  useEffect(() => { if (open && p.slug) getJSON<TrackView>(`/api/catalog/track/${p.slug}`).then(setT).catch(() => setT(null)); else setT(null); }, [open, p.slug]);
  useEffect(() => {
    if (!open) return;
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") p.setExpanded(false); };
    document.addEventListener("keydown", key); document.body.classList.add("lock"); close.current?.focus();
    return () => { document.removeEventListener("keydown", key); document.body.classList.remove("lock"); };
  }, [open, p]);
  if (!open || !p.slug) return null;
  return (
    <div className="pm" role="dialog" aria-modal="true" aria-label="Play mode" data-mood={t?.mood ?? "night"}>
      <button ref={close} className="btn g sq pm-x" onClick={() => p.setExpanded(false)} aria-label="Close play mode"><Icon name="close" /></button>
      <div className="pm-body">
        <div className="pm-top">
          <Cover slug={p.slug} title={p.title} size={240} art={t?.art} />
          <h2 className="disp">{p.title}</h2>
        </div>
        <div className="pm-lyrics"><Lyrics plain={t?.lyrics ?? ""} timed={t?.timed_lines ?? null} position={position} duration={duration} follow={p.playing} /></div>
        <div className="pm-ctl">
          <div className="pm-bar">
            <label className="sr" htmlFor="pm-seek">Seek</label>
            <input id="pm-seek" type="range" min={0} max={Math.max(1, Math.floor(duration))} step={1} value={Math.min(Math.floor(position), Math.max(1, Math.floor(duration)))} aria-valuetext={`${mmss(position)} of ${mmss(duration)}`} onChange={(e) => p.seek(Number(e.target.value))} />
            <div className="pm-times mu"><span>{mmss(position)}</span><span>{mmss(duration)}</span></div>
          </div>
          <Transport big />
          <Volume />
        </div>
      </div>
    </div>
  );
}

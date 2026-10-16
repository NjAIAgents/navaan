import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { getJSON, type TrackRow } from "./api";
import { errText } from "./songs";

export type QItem = { slug: string; title: string };
type Player = {
  slug: string | null; title: string; playing: boolean; error: string; expanded: boolean; hasNext: boolean; hasPrev: boolean;
  toggle: (slug: string, title: string, queue?: QItem[]) => Promise<void>; next: () => void; prev: () => void; seek: (seconds: number) => void; setExpanded: (on: boolean) => void;
};
const noop = async () => undefined;
const Ctx = createContext<Player>({ slug: null, title: "", playing: false, error: "", expanded: false, hasNext: false, hasPrev: false, toggle: noop, next: () => undefined, prev: () => undefined, seek: () => undefined, setExpanded: () => undefined });
const PosCtx = createContext<{ position: number; duration: number }>({ position: 0, duration: 0 });
export const usePlayer = () => useContext(Ctx);
/** The playing position, apart from the rest so that only what shows time re-renders four times a second. */
export const usePosition = () => useContext(PosCtx);

// One audio element for the whole app, so a song keeps playing while you move between screens. The link comes from /api/play and goes straight to the bucket;
// it lasts 5 minutes, so if the browser reports an error mid-song one fresh link is fetched and playback resumes where it was.
// A queue gives Next and Back: the list the song was started from (an album, a playlist), else every song in the catalogue. A finished song starts the next one.
export function PlayerProvider({ children }: { children: ReactNode }) {
  const audio = useRef<HTMLAudioElement>(null);
  const [cur, setCur] = useState<{ slug: string | null; title: string }>({ slug: null, title: "" });
  const [queue, setQueue] = useState<QItem[]>([]);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState(false);
  const [pos, setPos] = useState({ position: 0, duration: 0 });
  const retried = useRef(false);
  const start = useCallback(async (slug: string, at = 0) => {
    const a = audio.current!;
    const r = await getJSON<{ url: string }>(`/api/play?slug=${encodeURIComponent(slug)}`);
    a.src = r.url; if (at) a.currentTime = at;
    await a.play();
  }, []);
  const begin = useCallback(async (slug: string, title: string) => {
    setError(""); setCur({ slug, title }); setPos({ position: 0, duration: 0 }); retried.current = false;
    try { await start(slug); } catch (e) { setCur({ slug: null, title: "" }); setError(errText(e)); }
  }, [start]);
  const toggle = useCallback(async (slug: string, title: string, q?: QItem[]) => {
    const a = audio.current; if (!a) return;
    setError("");
    if (cur.slug === slug) { if (a.paused) await a.play().catch((e) => setError(errText(e))); else a.pause(); return; }
    if (q?.length) setQueue(q);
    else if (!queue.some((x) => x.slug === slug)) {
      setQueue([{ slug, title }]);   // at least this song, then the catalogue fills in so Next has somewhere to go
      getJSON<TrackRow[]>("/api/catalog/tracks").then((rows) => { if (Array.isArray(rows) && rows.some((r) => r.slug === slug)) setQueue(rows.map((r) => ({ slug: r.slug, title: r.title }))); }).catch(() => undefined);   // expected: no list means no Next
    }
    await begin(slug, title);
  }, [cur.slug, queue, begin]);
  const at = queue.findIndex((x) => x.slug === cur.slug);
  const hasNext = at >= 0 && at < queue.length - 1, hasPrev = at > 0;
  const next = useCallback(() => { if (at >= 0 && at < queue.length - 1) void begin(queue[at + 1].slug, queue[at + 1].title); }, [at, queue, begin]);
  const prev = useCallback(() => {
    const a = audio.current;
    if (a && (a.currentTime > 3 || at <= 0)) { a.currentTime = 0; return; }   // a few seconds in, Back restarts the song; at the start it goes to the one before
    if (at > 0) void begin(queue[at - 1].slug, queue[at - 1].title);
  }, [at, queue, begin]);
  const seek = useCallback((seconds: number) => { const a = audio.current; if (a && Number.isFinite(seconds)) { a.currentTime = Math.max(0, seconds); setPos((p) => ({ ...p, position: a.currentTime })); } }, []);
  const onError = () => {
    const a = audio.current; if (!a || !cur.slug || !a.src) return;
    if (retried.current) { setError("This song could not be played."); setPlaying(false); return; }
    retried.current = true; const t = a.currentTime;
    start(cur.slug, t).catch((e) => { setError(errText(e)); setPlaying(false); });
  };
  useEffect(() => { if (!cur.slug) setExpanded(false); }, [cur.slug]);
  // Lock screen and headset controls
  useEffect(() => {
    const ms = typeof navigator !== "undefined" ? navigator.mediaSession : undefined; if (!ms || !cur.slug) return;
    try {
      ms.metadata = new MediaMetadata({ title: cur.title, artist: "NAVAAN", artwork: [{ src: `/img/${cur.slug}/640.jpg`, sizes: "640x640", type: "image/jpeg" }] });
      ms.setActionHandler("play", () => void audio.current?.play()); ms.setActionHandler("pause", () => audio.current?.pause());
      ms.setActionHandler("nexttrack", hasNext ? next : null); ms.setActionHandler("previoustrack", prev);
    } catch (e) { void e; }   // expected: a browser without these controls
  }, [cur, hasNext, next, prev]);
  const value = useMemo(() => ({ ...cur, playing, error, expanded, hasNext, hasPrev, toggle, next, prev, seek, setExpanded }), [cur, playing, error, expanded, hasNext, hasPrev, toggle, next, prev, seek]);
  const tick = () => { const a = audio.current; if (a) setPos({ position: a.currentTime || 0, duration: Number.isFinite(a.duration) ? a.duration : 0 }); };
  const ended = () => { setPlaying(false); if (hasNext) next(); };
  return (
    <Ctx.Provider value={value}>
      <PosCtx.Provider value={pos}>{children}</PosCtx.Provider>
      <audio ref={audio} preload="none" onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={ended} onError={onError} onTimeUpdate={tick} onLoadedMetadata={tick} />
    </Ctx.Provider>
  );
}

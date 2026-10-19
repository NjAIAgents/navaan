import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { getJSON, type TrackRow } from "./api";
import { errText } from "./songs";
import { hit } from "./visits";

export type QItem = { slug: string; title: string };
type Player = {
  slug: string | null; title: string; playing: boolean; error: string; expanded: boolean; hasNext: boolean; hasPrev: boolean;
  toggle: (slug: string, title: string, queue?: QItem[]) => Promise<void>; playAt: (slug: string, title: string, seconds: number) => Promise<void>; next: () => void; prev: () => void; seek: (seconds: number) => void; setExpanded: (on: boolean) => void;
  volume: number; muted: boolean; setVolume: (v: number) => void; toggleMute: () => void;
  shuffle: boolean; setShuffle: (on: boolean) => void;
};
const noop = async () => undefined;
const Ctx = createContext<Player>({ slug: null, title: "", playing: false, error: "", expanded: false, hasNext: false, hasPrev: false, volume: 1, muted: false, setVolume: () => undefined, toggleMute: () => undefined, shuffle: false, setShuffle: () => undefined, toggle: noop, playAt: noop, next: () => undefined, prev: () => undefined, seek: () => undefined, setExpanded: () => undefined });
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
  const [volume, setVol] = useState(() => { try { const v = Number(localStorage.getItem("navaan-volume")); return Number.isFinite(v) && localStorage.getItem("navaan-volume") !== null ? Math.min(1, Math.max(0, v)) : 1; } catch { return 1; } });   // expected: storage can be blocked
  const [muted, setMuted] = useState(false);
  const setVolume = useCallback((v: number) => { const x = Math.min(1, Math.max(0, v)); setVol(x); if (x > 0) setMuted(false); try { localStorage.setItem("navaan-volume", String(x)); } catch { /* expected: storage can be blocked */ } }, []);
  const toggleMute = useCallback(() => setMuted((m) => !m), []);
  useEffect(() => { const a = audio.current; if (a) { a.volume = volume; a.muted = muted || volume === 0; } }, [volume, muted]);   // a phone's own buttons set the real loudness; this is the app's share of it
  const [shuffle, setShuf] = useState(() => { try { return localStorage.getItem("navaan-shuffle") === "1"; } catch { return false; } });   // expected: storage can be blocked
  const setShuffle = useCallback((on: boolean) => { setShuf(on); try { localStorage.setItem("navaan-shuffle", on ? "1" : "0"); } catch { /* expected: storage can be blocked */ } }, []);
  const played = useRef<string[]>([]);   // the songs played in this run, so Back goes where you were and shuffle does not repeat a song until every other one has played
  const retried = useRef(false);
  const heard = useRef({ slug: "", s: 0, at: -1 });   // seconds actually played of the current song, reported as one play when it changes, ends or the page closes
  const report = useCallback((closing = false) => { const h = heard.current; if (h.slug && h.s >= 1) hit("play", h.slug, h.s, closing); heard.current = { slug: "", s: 0, at: -1 }; }, []);
  useEffect(() => { const bye = () => report(true); window.addEventListener("pagehide", bye); return () => window.removeEventListener("pagehide", bye); }, [report]);
  const start = useCallback(async (slug: string, at = 0) => {
    const a = audio.current!;
    const r = await getJSON<{ url: string }>(`/api/play?slug=${encodeURIComponent(slug)}`);
    a.src = r.url; if (at) a.currentTime = at;
    await a.play();
  }, []);
  const begin = useCallback(async (slug: string, title: string, at = 0) => {
    report(); heard.current = { slug, s: 0, at: -1 };
    setError(""); setCur({ slug, title }); setPos({ position: at, duration: 0 }); retried.current = false;
    if (played.current[played.current.length - 1] !== slug) played.current.push(slug);
    try { await start(slug, at); } catch (e) { setCur({ slug: null, title: "" }); setError(errText(e)); }
  }, [start, report]);
  const toggle = useCallback(async (slug: string, title: string, q?: QItem[]) => {
    const a = audio.current; if (!a) return;
    setError("");
    if (cur.slug === slug) { if (a.paused) await a.play().catch((e) => setError(errText(e))); else a.pause(); return; }
    if (q?.length) { setQueue(q); played.current = []; }
    else if (!queue.some((x) => x.slug === slug)) {
      setQueue([{ slug, title }]);   // at least this song, then the catalogue fills in so Next has somewhere to go
      getJSON<TrackRow[]>("/api/catalog/tracks").then((rows) => { if (Array.isArray(rows) && rows.some((r) => r.slug === slug)) setQueue(rows.map((r) => ({ slug: r.slug, title: r.title }))); }).catch(() => undefined);   // expected: no list means no Next
    }
    await begin(slug, title);
  }, [cur.slug, queue, begin]);
  const at = queue.findIndex((x) => x.slug === cur.slug);
  const hasNext = at >= 0 && (shuffle ? queue.length > 1 : at < queue.length - 1), hasPrev = at > 0 || (shuffle && played.current.length > 1);
  const pickShuffled = useCallback(() => {   // a song nobody has played in this round; when all have, a new round without the one that just played
    const done = new Set(played.current); let pool = queue.filter((x) => !done.has(x.slug) && x.slug !== cur.slug);
    if (!pool.length) { played.current = cur.slug ? [cur.slug] : []; pool = queue.filter((x) => x.slug !== cur.slug); }
    return pool[Math.floor(Math.random() * pool.length)];
  }, [queue, cur.slug]);
  const next = useCallback(() => {
    if (shuffle) { const n = queue.length > 1 ? pickShuffled() : undefined; if (n) void begin(n.slug, n.title); return; }
    if (at >= 0 && at < queue.length - 1) void begin(queue[at + 1].slug, queue[at + 1].title);
  }, [shuffle, at, queue, begin, pickShuffled]);
  const prev = useCallback(() => {
    const a = audio.current;
    if (a && a.currentTime > 3) { a.currentTime = 0; return; }   // a few seconds in, Back restarts the song
    if (shuffle && played.current.length > 1) { played.current.pop(); const was = played.current.pop(); const item = queue.find((x) => x.slug === was); if (item) void begin(item.slug, item.title); return; }
    if (at > 0) void begin(queue[at - 1].slug, queue[at - 1].title); else if (a) a.currentTime = 0;
  }, [shuffle, at, queue, begin]);
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
  // Play this song from a given second: a lyric line was picked. The song already playing (or paused) just jumps; another song starts there.
  const playAt = useCallback(async (slug: string, title: string, seconds: number) => {
    const a = audio.current; if (!a) return; setError("");
    if (cur.slug === slug) { a.currentTime = Math.max(0, seconds); setPos((p) => ({ ...p, position: Math.max(0, seconds) })); if (a.paused) await a.play().catch((e) => setError(errText(e))); return; }
    if (!queue.some((x) => x.slug === slug)) setQueue([{ slug, title }]);
    await begin(slug, title, Math.max(0, seconds));
  }, [cur.slug, queue, begin]);
  const value = useMemo(() => ({ ...cur, playing, error, expanded, hasNext, hasPrev, toggle, playAt, next, prev, seek, setExpanded, volume, muted, setVolume, toggleMute, shuffle, setShuffle }), [cur, playing, error, expanded, hasNext, hasPrev, toggle, playAt, next, prev, seek, volume, muted, setVolume, toggleMute, shuffle, setShuffle]);
  const tick = () => {
    const a = audio.current; if (!a) return;
    if (!heard.current.slug && cur.slug && !a.paused) heard.current = { slug: cur.slug, s: 0, at: -1 };   // the same song played again after it ended: a new play
    const h = heard.current, t = a.currentTime || 0, d = t - h.at;
    if (!a.paused && h.at >= 0 && d > 0 && d < 2) h.s += d;   // a seek is a jump, not listening
    h.at = t; setPos({ position: t, duration: Number.isFinite(a.duration) ? a.duration : 0 });
  };
  const ended = () => { setPlaying(false); report(); if (hasNext) next(); };
  return (
    <Ctx.Provider value={value}>
      <PosCtx.Provider value={pos}>{children}</PosCtx.Provider>
      <audio ref={audio} preload="none" onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={ended} onError={onError} onTimeUpdate={tick} onLoadedMetadata={tick} />
    </Ctx.Provider>
  );
}

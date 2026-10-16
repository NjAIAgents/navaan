import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";
import { getJSON } from "./api";
import { errText } from "./songs";

type Player = { slug: string | null; title: string; playing: boolean; error: string; toggle: (slug: string, title: string) => Promise<void> };
const Ctx = createContext<Player>({ slug: null, title: "", playing: false, error: "", toggle: async () => undefined });
export const usePlayer = () => useContext(Ctx);

// One audio element for the whole app, so a song keeps playing while you move between screens. The link comes from /api/play and goes straight to the bucket;
// it lasts 5 minutes, so if the browser reports an error mid-song one fresh link is fetched and playback resumes where it was.
export function PlayerProvider({ children }: { children: ReactNode }) {
  const audio = useRef<HTMLAudioElement>(null);
  const [cur, setCur] = useState<{ slug: string | null; title: string }>({ slug: null, title: "" });
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState("");
  const retried = useRef(false);
  const start = useCallback(async (slug: string, at = 0) => {
    const a = audio.current!;
    const r = await getJSON<{ url: string }>(`/api/play?slug=${encodeURIComponent(slug)}`);
    a.src = r.url; if (at) a.currentTime = at;
    await a.play();
  }, []);
  const toggle = useCallback(async (slug: string, title: string) => {
    const a = audio.current; if (!a) return;
    setError("");
    if (cur.slug === slug) { if (a.paused) await a.play().catch((e) => setError(errText(e))); else a.pause(); return; }
    setCur({ slug, title }); retried.current = false;
    try { await start(slug); } catch (e) { setCur({ slug: null, title: "" }); setError(errText(e)); }
  }, [cur.slug, start]);
  const onError = () => {
    const a = audio.current; if (!a || !cur.slug || !a.src) return;
    if (retried.current) { setError("This song could not be played."); setPlaying(false); return; }
    retried.current = true; const at = a.currentTime;
    start(cur.slug, at).catch((e) => { setError(errText(e)); setPlaying(false); });
  };
  const value = useMemo(() => ({ ...cur, playing, error, toggle }), [cur, playing, error, toggle]);
  return (
    <Ctx.Provider value={value}>
      {children}
      <audio ref={audio} preload="none" onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)} onError={onError} />
    </Ctx.Provider>
  );
}

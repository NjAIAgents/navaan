import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getJSON, postJSON } from "../lib/api";
import { errText } from "../lib/songs";
import { Sheet } from "./Sheet";

export type ReleaseSong = { slug: string; title: string; ready: boolean; reason: string | null; youtube: "private" | "public" | "retrying" | "failed"; site: "listed" | "unlisted"; attempts: number; error: string };
export type ReleaseState = { album: string; title: string; status: "draft" | "scheduled" | "published" | "missed"; release_at: string | null; announced?: boolean; ready: boolean; blocked: string | null; songs: ReleaseSong[] };

const YT: Record<ReleaseSong["youtube"], string> = { private: "YouTube: waiting", public: "YouTube: public", retrying: "YouTube: trying again", failed: "YouTube: failed" };
const local = (iso: string) => new Date(iso).toLocaleString([], { weekday: "short", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });

// Release (spec 003): only an album is released, and every song in it goes public with it, on YouTube and navaan.online. One confirm for the album; the list shows what each song still needs.
// Owner only: for anyone else the server says no and the card stays hidden.
export function AlbumReleaseCard({ slug, onChange, onAnnounce }: { slug: string; onChange: () => void; onAnnounce?: (on: boolean) => Promise<unknown> }) {
  const [s, setS] = useState<ReleaseState | null>(null); const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  const [ask, setAsk] = useState(false); const [when, setWhen] = useState("");
  const load = useCallback(() => getJSON<ReleaseState>(`/api/albums/release?album=${encodeURIComponent(slug)}`).then((x) => { setS(Array.isArray(x?.songs) ? x : null); setErr(""); }).catch(() => setS(null)), [slug]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => { if (s?.status !== "published" || s.songs.every((x) => x.youtube === "public" || x.youtube === "failed")) return; const t = setInterval(() => void load(), 15000); return () => clearInterval(t); }, [s, load]);
  if (!s) return null;
  const post = async (path: string, body: Record<string, unknown>) => {
    setBusy(true); setErr("");
    try { setS(await postJSON<ReleaseState>(path, { album: slug, ...body })); setAsk(false); onChange(); }
    catch (e) { setErr(errText(e)); await load(); }
    finally { setBusy(false); }
  };
  const at = when ? new Date(when).toISOString().replace(/\.\d{3}Z$/, "Z") : null;
  const released = s.status === "published";
  return (
    <section className="card stack" aria-labelledby="rl-h">
      <h2 id="rl-h">Release</h2>
      <p className="mu">{released ? `Released${s.release_at ? " " + local(s.release_at) : ""}. Every song is public with the album.`
        : s.status === "scheduled" && s.release_at ? `Scheduled for ${local(s.release_at)}.`
        : s.status === "missed" ? "The scheduled release was missed: a song was not ready in time. Release it again."
        : "A song goes public only with its album: releasing makes every song below public on YouTube and navaan.online at once."}</p>
      {s.blocked && <p className="mu" role="status">{s.blocked}</p>}
      {s.songs.length > 0 && <ul className="stack" style={{ listStyle: "none", padding: 0, margin: 0 }}>{s.songs.map((x) => (
        <li key={x.slug} className="row" style={{ minHeight: 44 }}>
          <Link className="tx" to={`/studio/songs/${x.slug}`} style={{ flex: 1 }}><b>{x.title}</b></Link>
          {released ? <>
            <span className={"chip " + (x.youtube === "public" ? "ok" : x.youtube === "failed" ? "wn" : "")} title={x.error || undefined}>{YT[x.youtube]}</span>
            <span className={"chip " + (x.site === "listed" ? "ok" : "")}>{x.site === "listed" ? "Site: listed" : "Site: not yet"}</span>
            {x.youtube === "failed" && <button className="btn" disabled={busy} onClick={() => void post("/api/albums/release/retry", { song: x.slug })}>Try again</button>}
          </> : <span className={"chip " + (x.ready ? "ok" : "wn")}>{x.ready ? "Ready" : x.reason}</span>}
        </li>))}</ul>}
      {!released && (
        <div className="row">
          <button className="btn p" disabled={busy || !s.ready} onClick={() => { setWhen(""); setAsk(true); }}>{s.status === "scheduled" ? "Change the time…" : "Release…"}</button>
          {(s.status === "scheduled" || s.status === "missed") && <button className="btn" disabled={busy} onClick={() => void post("/api/albums/release/cancel", {})}>Cancel the release</button>}
        </div>
      )}
      {!released && onAnnounce && (
        <label className="row" style={{ minHeight: 44 }}><input type="checkbox" checked={!!s.announced} disabled={busy} onChange={(e) => { const on = e.target.checked; setBusy(true); void onAnnounce(on).then(load).catch((x) => setErr(errText(x))).finally(() => setBusy(false)); }} />
          Show a coming-soon page now (cover, date, teasers; no songs)</label>
      )}
      {err && <p role="alert" className="mu">{err}</p>}
      {ask && (
        <Sheet title={`Release ${s.title}`} onClose={() => setAsk(false)}>
          <p>These songs go public on YouTube and navaan.online{at ? ` on ${local(at)}` : " now"}:</p>
          <ol>{s.songs.map((x) => <li key={x.slug}>{x.title}</li>)}</ol>
          <p className="mu">This is hard to undo: a public video and a listed song stay public until you take them down by hand.</p>
          <label htmlFor="rl-when">Release at (leave empty to release now)</label>
          <input id="rl-when" type="datetime-local" className="field" value={when} onChange={(e) => setWhen(e.target.value)} />
          <div className="row">
            <button className="btn p" disabled={busy} aria-busy={busy} onClick={() => void post("/api/albums/release", { songs: s.songs.map((x) => x.slug), at })}>{at ? "Schedule the release" : "Release now"}</button>
            <button className="btn g" onClick={() => setAsk(false)}>Not yet</button>
          </div>
        </Sheet>
      )}
    </section>
  );
}

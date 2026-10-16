import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Icon } from "../components/Icon";
import { ApiError, getJSON, postJSON, type LibraryData, type PlaylistRow } from "../lib/api";
import { errText } from "../lib/songs";

type Limit = { error: string; upgrade?: string };

// A person's playlists and saved songs. The playlist limit comes from the plan (the server decides); when it is reached the message says what the limit is and where to see the plans.
export default function Library() {
  const [lists, setLists] = useState<PlaylistRow[] | null>(null);
  const [lib, setLib] = useState<LibraryData | null>(null);
  const [name, setName] = useState("");
  const [err, setErr] = useState("");
  const [limit, setLimit] = useState<Limit | null>(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => Promise.all([getJSON<PlaylistRow[]>("/api/playlists"), getJSON<LibraryData>("/api/library")]).then(([p, l]) => { setLists(p); setLib(l); setErr(""); }).catch((e) => setErr(errText(e))), []);
  useEffect(() => { void load(); }, [load]);
  const create = async (e: React.FormEvent) => {
    e.preventDefault(); if (!name.trim()) return;
    setBusy(true); setLimit(null); setErr("");
    try { await postJSON("/api/playlists/create", { name }); setName(""); await load(); }
    catch (x) { if (x instanceof ApiError && x.status === 403) setLimit({ error: x.message, upgrade: "/plans" }); else setErr(errText(x)); }
    finally { setBusy(false); }
  };
  return (
    <>
      <div className="ph"><h1 className="disp">Library</h1><p>Your playlists and saved songs.</p></div>
      {err && <div className="card" role="alert"><h2>Something went wrong</h2><p className="mu">{err}</p></div>}
      <section className="sec" aria-labelledby="pl-h">
        <div className="sh"><h2 id="pl-h">Playlists</h2><span className="n">{lists?.length ?? 0}</span></div>
        <form className="row" onSubmit={(e) => void create(e)}>
          <label className="sr" htmlFor="new-pl">New playlist name</label>
          <input id="new-pl" className="field" style={{ flex: 1, minWidth: 0 }} value={name} onChange={(e) => setName(e.target.value)} placeholder="New playlist" maxLength={100} autoComplete="off" />
          <button className="btn p" type="submit" disabled={busy || !name.trim()}>Create</button>
        </form>
        {limit && <div className="card" role="alert"><h2>Playlist limit reached</h2><p>{limit.error}</p><Link className="btn p" to={limit.upgrade ?? "/plans"}><Icon name="star" />See the plans</Link></div>}
        {!lists && !err && <p className="mu" role="status">Loading…</p>}
        {lists && (
          <div className="card" style={{ padding: 8 }}>
            {lists.length ? lists.map((p) => (
              <Link key={p.id} className="q" to={`/library/playlists/${p.id}`}>
                <span className="tx"><b>{p.name}</b><span className="s">{p.tracks} song{p.tracks === 1 ? "" : "s"} · {p.visibility}</span></span><Icon name="chevron" />
              </Link>
            )) : <p className="empty">No playlists yet.</p>}
          </div>
        )}
      </section>
      <section className="sec" aria-labelledby="sv-h">
        <div className="sh"><h2 id="sv-h">Saved songs</h2><span className="n">{lib?.tracks.length ?? 0}</span></div>
        <div className="card" style={{ padding: 8 }}>
          {lib?.tracks.length ? lib.tracks.map((t) => <Link key={t.slug} className="q" to={`/studio/songs/${t.slug}`}><span className="tx"><b>{t.title}</b><span className="s">{t.slug}</span></span><Icon name="chevron" /></Link>) : <p className="empty">Nothing saved yet. Save a song from its page.</p>}
        </div>
      </section>
    </>
  );
}

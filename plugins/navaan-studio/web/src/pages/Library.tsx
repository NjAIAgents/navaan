import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Icon } from "../components/Icon";
import { Cover } from "../components/Cover";
import { ApiError, getJSON, postJSON, type Filters, type LibraryData, type PlaylistRow, type TrackRow } from "../lib/api";
import { useMe } from "../lib/me";
import { errText } from "../lib/songs";

type Limit = { error: string; upgrade?: string };

// The Songs tab: every song out, narrowed by album, language and genre (the server filters, so a listener never sees an unconfirmed song).
function Songs() {
  const me = useMe();
  const [f, setF] = useState<Filters | null>(null);
  const [sel, setSel] = useState({ album: "", language: "", genre: "" });
  const [rows, setRows] = useState<TrackRow[] | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { getJSON<Filters>("/api/catalog/filters").then(setF).catch((e) => setErr(errText(e))); }, []);
  useEffect(() => {
    const q = new URLSearchParams(Object.entries(sel).filter(([, v]) => v)).toString();
    setRows(null); getJSON<TrackRow[]>(`/api/catalog/tracks${q ? "?" + q : ""}`).then(setRows).catch((e) => setErr(errText(e)));
  }, [sel]);
  const pick = (k: keyof typeof sel, label: string, opts: { value: string; label: string }[]) => (
    <><label className="sr" htmlFor={`f-${k}`}>{label}</label>
      <select id={`f-${k}`} className="field sel" value={sel[k]} onChange={(e) => setSel({ ...sel, [k]: e.target.value })}><option value="">{label}: all</option>{opts.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></>
  );
  return (
    <section className="sec" aria-label="Songs">
      <div className="row">
        {pick("album", "Album", (f?.albums ?? []).map((a) => ({ value: a.slug, label: a.title })))}
        {pick("language", "Language", (f?.languages ?? []).map((x) => ({ value: x, label: x })))}
        {pick("genre", "Genre", (f?.genres ?? []).map((x) => ({ value: x, label: x })))}
      </div>
      {err && <div className="card" role="alert"><p className="mu">{err}</p></div>}
      {!rows && !err && <p className="mu" role="status">Loading…</p>}
      {rows && (
        <div className="card" style={{ padding: 8 }} aria-live="polite">
          {rows.length ? rows.map((t) => (
            <Link key={t.slug} className="q" to={`/song/${t.slug}`}>
              <Cover slug={t.slug} title={t.title} art={t.art} />
              <span className="tx"><b>{t.title}</b><span className="s">{[t.language, t.genre, ...t.albums.map((a) => a.title)].filter(Boolean).join(" · ")}</span></span>
              {me.studio && t.licence !== "confirmed" && <span className="chip wn">Licence {t.licence}</span>}<Icon name="chevron" />
            </Link>
          )) : <p className="empty">No songs match.</p>}
        </div>
      )}
    </section>
  );
}

// A person's playlists and saved songs. The playlist limit comes from the plan (the server decides); when it is reached the message says what the limit is and where to see the plans.
export default function Library() {
  const [tab, setTab] = useState<"playlists" | "songs">("playlists");
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
      <div className="seg" role="tablist" aria-label="Library sections" style={{ alignSelf: "flex-start" }}>
        {([["playlists", "Playlists"], ["songs", "Songs"]] as const).map(([k, label]) => <button key={k} role="tab" id={`lib-${k}`} aria-selected={tab === k} aria-controls="lib-panel" tabIndex={tab === k ? 0 : -1} onClick={() => setTab(k)}>{label}</button>)}
      </div>
      {err && <div className="card" role="alert"><h2>Something went wrong</h2><p className="mu">{err}</p></div>}
      <div id="lib-panel" role="tabpanel" aria-labelledby={`lib-${tab}`} className="stack" style={{ gap: 28 }}>
      {tab === "songs" ? <Songs /> : <>
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
          {lib?.tracks.length ? lib.tracks.map((t) => <Link key={t.slug} className="q" to={`/song/${t.slug}`}><span className="tx"><b>{t.title}</b><span className="s">{t.slug}</span></span><Icon name="chevron" /></Link>) : <p className="empty">Nothing saved yet. Save a song from its page.</p>}
        </div>
      </section>
      </>}
      </div>
    </>
  );
}

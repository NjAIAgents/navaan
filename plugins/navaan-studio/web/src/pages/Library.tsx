import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Icon } from "../components/Icon";
import { Cover } from "../components/Cover";
import { getJSON, type Filters, type LibraryData, type PlaylistRow, type TrackRow } from "../lib/api";
import { useMe } from "../lib/me";
import { PITCH } from "../components/GuestPitch";
import { errText } from "../lib/songs";
import { Loading } from "../components/Loading";
import { LoadMore } from "../components/LoadMore";
import { AddToPlaylist } from "../components/AddToPlaylist";
import { NewPlaylist } from "../components/NewPlaylist";
import { Tile } from "../components/Tile";
import { usePaged } from "../lib/paged";
import { useView, ViewToggle } from "../lib/view";


// The Songs tab: every song out, narrowed by album, language and genre (the server filters, so a listener never sees an unconfirmed song).
function Songs() {
  const me = useMe();
  const [f, setF] = useState<Filters | null>(null);
  const [sel, setSel] = useState({ album: "", language: "", genre: "" });
  const [ferr, setFerr] = useState("");
  useEffect(() => { getJSON<Filters>("/api/catalog/filters").then(setF).catch((e) => setFerr(errText(e))); }, []);
  const q = new URLSearchParams(Object.entries(sel).filter(([, v]) => v)).toString();
  const { items: rows, busy, done, err: perr, more } = usePaged<TrackRow>(`/api/catalog/tracks${q ? "?" + q : ""}`, 24);   // 24 songs, then more as you scroll; a slower answer for an earlier choice is ignored
  const err = ferr || perr; const [view, setView] = useView("songs");
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
        <span className="sp" /><ViewToggle view={view} onChange={setView} />
      </div>
      {err && <div className="card" role="alert"><p className="mu">{err}</p></div>}
      {!rows && !err && <Loading />}
      {rows && (
        <div className={view === "grid" ? undefined : "card"} style={view === "grid" ? undefined : { padding: 8 }} aria-live="polite">
          {view === "grid" ? (rows.length ? <div className="grid tiles">{rows.map((t) => (
            <Tile key={t.slug} to={`/song/${t.slug}`} slug={t.slug} title={t.title} art={t.art} sub={[t.language, t.genre].filter(Boolean).join(" · ") || undefined} action={<AddToPlaylist slug={t.slug} title={t.title} />} />
          ))}</div> : <p className="empty card">No songs match.</p>)
          : rows.length ? rows.map((t) => (
            <div key={t.slug} className="qwrap">
              <Link className="q" to={`/song/${t.slug}`}>
                <Cover slug={t.slug} title={t.title} art={t.art} />
                <span className="tx"><b>{t.title}</b><span className="s">{[t.language, t.genre, ...t.albums.map((a) => a.title)].filter(Boolean).join(" · ")}</span></span>
                {me.studio && t.licence !== "confirmed" && <span className="chip wn">Licence {t.licence}</span>}<Icon name="chevron" />
              </Link>
              <AddToPlaylist slug={t.slug} title={t.title} />
            </div>
          )) : <p className="empty">No songs match.</p>}
          <LoadMore done={done} busy={busy} more={more} />
        </div>
      )}
    </section>
  );
}

// A person's playlists and saved songs. The playlist limit comes from the plan (the server decides); when it is reached the message says what the limit is and where to see the plans.
export default function Library() {
  const { guest } = useMe();
  const [tab, setTab] = useState<"playlists" | "songs">("playlists");
  const [lists, setLists] = useState<PlaylistRow[] | null>(null);
  const [lib, setLib] = useState<LibraryData | null>(null);
  const [creating, setCreating] = useState(false);
  const [err, setErr] = useState(""); const [view, setView] = useView("library");
  const load = useCallback(() => Promise.all([getJSON<PlaylistRow[]>("/api/playlists"), getJSON<LibraryData>("/api/library")]).then(([p, l]) => { setLists(p); setLib(l); setErr(""); }).catch((e) => setErr(errText(e))), []);
  useEffect(() => { if (!guest) void load(); }, [load, guest]);   // a visitor has no playlists to load
  return (
    <>
      <div className="ph"><h1 className="disp">Library</h1><p>{guest ? "Every NAVAAN song, free to play." : "Your playlists and saved songs."}</p></div>
      <div className="seg" role="tablist" aria-label="Library sections" style={{ alignSelf: "flex-start" }}>
        {([["playlists", "Playlists"], ["songs", "Songs"]] as const).map(([k, label]) => <button key={k} role="tab" id={`lib-${k}`} aria-selected={tab === k} aria-controls="lib-panel" tabIndex={tab === k ? 0 : -1} onClick={() => setTab(k)}>{label}</button>)}
      </div>
      {err && <div className="card" role="alert"><h2>Something went wrong</h2><p className="mu">{err}</p></div>}
      <div id="lib-panel" role="tabpanel" aria-labelledby={`lib-${tab}`} className="stack" style={{ gap: 28 }}>
      {tab === "songs" ? <Songs /> : guest ? (
        <section className="sec" aria-labelledby="pl-h">
          <div className="sh"><h2 id="pl-h">Playlists</h2></div>
          <div className="card stack" style={{ maxWidth: 560 }}>
            <h3>Create your first playlist</h3>
            <p>It's easy, we'll help you. {PITCH}</p>
            <div className="row"><Link className="btn p" to="/join"><Icon name="plus" /> Create playlist</Link></div>
          </div>
        </section>
      ) : <>
      <section className="sec" aria-labelledby="pl-h">
        <div className="sh"><h2 id="pl-h">Playlists</h2><span className="n">{lists?.length ?? 0}</span></div>
        {creating ? <div className="card"><NewPlaylist onCreated={() => { setCreating(false); void load(); }} /></div> : <div className="row"><button className="btn p" onClick={() => setCreating(true)}><Icon name="plus" /> New playlist</button><span className="sp" /><ViewToggle view={view} onChange={setView} /></div>}
        {!lists && !err && <Loading />}
        {lists && (view === "grid" ? (lists.length ? <div className="grid tiles">{lists.map((p) => (
          <Tile key={p.id} to={`/library/playlists/${p.id}`} slug={p.cover || p.id} title={p.name} art={p.cover ? { colour: p.colour ?? null } : null} sub={`${p.tracks} song${p.tracks === 1 ? "" : "s"} · ${p.visibility}`} />
        ))}</div> : <p className="empty card">No playlists yet.</p>) : (
          <div className="card" style={{ padding: 8 }}>
            {lists.length ? lists.map((p) => (
              <Link key={p.id} className="q" to={`/library/playlists/${p.id}`}>
                <Cover slug={p.cover || p.id} title={p.name} art={p.cover ? { colour: p.colour ?? null } : null} />
                <span className="tx"><b>{p.name}</b><span className="s">{p.tracks} song{p.tracks === 1 ? "" : "s"} · {p.visibility}</span></span><Icon name="chevron" />
              </Link>
            )) : <p className="empty">No playlists yet.</p>}
          </div>
        ))}
      </section>
      <section className="sec" aria-labelledby="sv-h">
        <div className="sh"><h2 id="sv-h">Saved songs</h2><span className="n">{lib?.tracks.length ?? 0}</span></div>
        {view === "grid" && lib?.tracks.length ? <div className="grid tiles">{lib.tracks.map((t) => <Tile key={t.slug} to={`/song/${t.slug}`} slug={t.slug} title={t.title} art={t.art} />)}</div> : (
          <div className="card" style={{ padding: 8 }}>
            {lib?.tracks.length ? lib.tracks.map((t) => <Link key={t.slug} className="q" to={`/song/${t.slug}`}><Cover slug={t.slug} title={t.title} art={t.art} /><span className="tx"><b>{t.title}</b></span><Icon name="chevron" /></Link>) : <p className="empty">Nothing saved yet. Save a song from its page.</p>}
          </div>
        )}
      </section>
      </>}
      </div>
    </>
  );
}

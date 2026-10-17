import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getJSON, postJSON, type SongRow } from "../lib/api";
import { errText } from "../lib/songs";

type Name = { name: string; why: string };

// The album pipeline: pick two or more songs, get five name ideas from them (or type your own), create the album with the songs in the order you picked them; the cover is made on the album's page.
export function NewAlbum({ onClose }: { onClose: () => void }) {
  const go = useNavigate();
  const [songs, setSongs] = useState<SongRow[] | null>(null); const [picked, setPicked] = useState<string[]>([]);
  const [title, setTitle] = useState(""); const [kind, setKind] = useState("album"); const [names, setNames] = useState<Name[]>([]);
  const [busy, setBusy] = useState(""); const [err, setErr] = useState("");
  useEffect(() => { getJSON<SongRow[]>("/api/songs").then((r) => setSongs(r.filter((s) => s.type === "music"))).catch((e) => setErr(errText(e))); }, []);
  const toggle = (slug: string) => setPicked((p) => (p.includes(slug) ? p.filter((x) => x !== slug) : [...p, slug]));
  const suggest = async () => { setBusy("Thinking…"); setErr(""); try { setNames((await postJSON<{ names: Name[] }>("/api/albums/suggest", { tracks: picked })).names); } catch (e) { setErr(errText(e)); } finally { setBusy(""); } };
  const create = async () => {
    setBusy("Creating…"); setErr("");
    try { const r = await postJSON<{ slug: string }>("/api/albums/save", { title, kind }); await postJSON("/api/albums/reorder", { album: r.slug, tracks: picked }); go(`/albums/${r.slug}`); }
    catch (e) { setErr(errText(e)); setBusy(""); }
  };
  const title_of = (slug: string) => songs?.find((s) => s.slug === slug)?.title ?? slug;
  return (
    <section className="card stack" aria-labelledby="na-h">
      <div className="row"><h2 id="na-h" style={{ flex: 1 }}>New album</h2><button className="btn g" onClick={onClose}>Cancel</button></div>
      <fieldset className="stack" style={{ border: 0, padding: 0, margin: 0 }}>
        <legend><b>1. Pick two or more songs</b> <span className="mu">(the order you pick is the track order; you can change it later)</span></legend>
        {!songs && !err && <p className="mu">Loading songs…</p>}
        {songs?.map((s) => (
          <label key={s.slug} className="row" style={{ gap: 10, minHeight: "var(--tap)" }}>
            <input type="checkbox" checked={picked.includes(s.slug)} onChange={() => toggle(s.slug)} />
            <span className="tx">{picked.includes(s.slug) ? `${picked.indexOf(s.slug) + 1}. ` : ""}{s.title}</span>{s.published && <span className="chip ok">published</span>}
          </label>
        ))}
        {songs && !songs.length && <p className="empty">No songs yet.</p>}
      </fieldset>
      <div className="stack">
        <b>2. Name it</b>
        <div className="row"><button className="btn" disabled={picked.length < 2 || !!busy} onClick={() => void suggest()}>{busy === "Thinking…" ? busy : "Suggest names (a few cents)"}</button></div>
        {names.length > 0 && <ul className="stack" aria-label="Name ideas" style={{ listStyle: "none", padding: 0, margin: 0 }}>{names.map((n) => <li key={n.name}><button className="btn g" onClick={() => setTitle(n.name)} aria-label={`Use the name ${n.name}`}>{n.name}</button> <span className="mu">{n.why}</span></li>)}</ul>}
        <label htmlFor="na-title">Album name</label>
        <input id="na-title" className="field" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={120} autoComplete="off" />
        <label htmlFor="na-kind">Kind</label>
        <select id="na-kind" className="field sel" value={kind} onChange={(e) => setKind(e.target.value)}><option value="album">Album</option><option value="ep">EP</option><option value="single">Single</option></select>
      </div>
      <div className="stack">
        <b>3. Create it</b>
        {picked.length > 0 && <p className="mu">{picked.map(title_of).join(", ")}</p>}
        <div className="row"><button className="btn p" disabled={picked.length < 2 || !title.trim() || !!busy} onClick={() => void create()}>{busy === "Creating…" ? busy : "Create album"}</button></div>
        <p className="mu">Then open the album to make its cover.</p>
      </div>
      {err && <p role="alert" style={{ color: "var(--bad)" }}>{err}</p>}
    </section>
  );
}

import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Cover } from "../components/Cover";
import { Icon } from "../components/Icon";
import { PlayButton } from "../components/PlayButton";
import { AddToPlaylist } from "../components/AddToPlaylist";
import { getJSON, postJSON, type AlbumRow, type TrackRow } from "../lib/api";
import { errText } from "../lib/songs";
import { coverOf } from "./Albums";
import { Loading } from "../components/Loading";

// One album: the hero with its cover, title, kind and status; the details; the songs in order (up, down, remove) and a way to add more. A published album may only hold published songs: the server says so.
export default function Album() {
  const { slug = "" } = useParams();
  const go = useNavigate();
  const [a, setA] = useState<AlbumRow | null>(null);
  const [all, setAll] = useState<TrackRow[]>([]);
  const [form, setForm] = useState({ title: "", kind: "album", status: "draft", release_date: "", description: "" });
  const [pick, setPick] = useState("");
  const [err, setErr] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const load = useCallback(async () => {
    try {
      const [rows, tracks] = await Promise.all([getJSON<AlbumRow[]>("/api/albums"), getJSON<TrackRow[]>("/api/catalog/tracks")]);
      const x = rows.find((r) => r.slug === slug); if (!x) throw new Error("No such album");
      setA(x); setAll(tracks); setForm({ title: x.title, kind: x.kind, status: x.status, release_date: x.release_date ?? "", description: x.description }); setErr("");
    } catch (e) { setErr(errText(e)); }
  }, [slug]);
  useEffect(() => { void load(); }, [load]);
  const run = async (fn: () => Promise<unknown>, ok = "") => { setBusy(true); setNote(""); try { await fn(); await load(); setNote(ok); } catch (e) { setNote(errText(e)); } finally { setBusy(false); } };
  if (!a) return err ? <div className="card" role="alert"><h2>Could not open this album</h2><p className="mu">{err}</p><Link className="btn" to="/albums">Back to Albums</Link></div> : <Loading />;
  const order = a.tracks.map((t) => t.slug);
  const reorder = (next: string[]) => run(() => postJSON("/api/albums/reorder", { album: slug, tracks: next }));
  const move = (i: number, d: number) => { const n = [...order]; [n[i], n[i + d]] = [n[i + d], n[i]]; return reorder(n); };
  const free = all.filter((t) => !order.includes(t.slug));
  const c = coverOf(a);
  const playable = a.tracks.filter((t) => t.status === "published").map((t) => ({ slug: t.slug, title: t.title }));
  return (
    <>
      <section className="hero" style={c?.art?.colour ? { background: `linear-gradient(180deg, ${c.art.colour}66, transparent 75%)` } : undefined} aria-labelledby="al-h">
        <Cover slug={c?.slug ?? a.slug} title={a.title} size={200} art={c?.art} />
        <div className="hero-tx">
          <Link className="back" to="/albums"><Icon name="chevron" />Albums</Link>
          <h1 id="al-h" className="disp">{a.title}</h1>
          {playable.length > 0 && <div className="row"><PlayButton queue={playable} label={a.title} size="big" /></div>}
          <div className="row chips"><span className="chip">{a.kind}</span><span className={"chip " + (a.status === "published" ? "ok" : "")}>{a.status}</span>{a.release_date && <span className="chip">{a.release_date}</span>}<span className="chip">{a.tracks.length} song{a.tracks.length === 1 ? "" : "s"}</span></div>
        </div>
      </section>
      {note && <div className="card" role="status"><p className="mu">{note}</p></div>}
      <form className="card stack" onSubmit={(e) => { e.preventDefault(); void run(() => postJSON("/api/albums/save", { slug, ...form, release_date: form.release_date || null }), "Saved."); }} aria-label="Album details">
        <label htmlFor="a-title">Title</label><input id="a-title" className="field" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} maxLength={120} />
        <div className="row">
          <div><label htmlFor="a-kind">Kind</label><br /><select id="a-kind" className="field sel" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}><option value="album">Album</option><option value="ep">EP</option><option value="single">Single</option></select></div>
          <div><label htmlFor="a-status">Status</label><br /><select id="a-status" className="field sel" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}><option value="draft">Draft</option><option value="scheduled">Scheduled</option><option value="published">Published</option></select></div>
          <div><label htmlFor="a-date">Release date</label><br /><input id="a-date" type="date" className="field sel" value={form.release_date} onChange={(e) => setForm({ ...form, release_date: e.target.value })} /></div>
        </div>
        <label htmlFor="a-desc">Description</label><textarea id="a-desc" className="field" rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
        <div className="row"><button className="btn p" type="submit" disabled={busy || !form.title.trim()}>Save details</button></div>
      </form>
      <section className="sec" aria-labelledby="tl-h">
        <div className="sh"><h2 id="tl-h">Songs</h2><span className="n">{a.tracks.length}</span></div>
        <div className="card" style={{ padding: 8 }}>
          {a.tracks.length ? <ol className="steps">{a.tracks.map((t, i) => (
            <li key={t.slug} className="stp">
              {t.status === "published" && <PlayButton slug={t.slug} title={t.title} queue={playable} label={t.title} />}
              <Link className="tx" to={`/song/${t.slug}`}><b>{i + 1}. {t.title}</b>{t.status !== "published" && <span className="mu"> · {t.status}</span>}</Link>
              {t.status === "published" && <AddToPlaylist slug={t.slug} title={t.title} />}
              <button className="btn g sq" disabled={busy || i === 0} onClick={() => void move(i, -1)} aria-label={`Move ${t.title} up`}><span style={{ transform: "rotate(-90deg)", display: "flex" }}><Icon name="chevron" /></span></button>
              <button className="btn g sq" disabled={busy || i === a.tracks.length - 1} onClick={() => void move(i, 1)} aria-label={`Move ${t.title} down`}><span style={{ transform: "rotate(90deg)", display: "flex" }}><Icon name="chevron" /></span></button>
              <button className="btn g" disabled={busy} onClick={() => void reorder(order.filter((x) => x !== t.slug))} aria-label={`Remove ${t.title}`}>Remove</button>
            </li>
          ))}</ol> : <p className="empty">No songs yet. Add one below.</p>}
        </div>
        {free.length > 0 && (
          <div className="row">
            <label className="sr" htmlFor="a-add">Song to add</label>
            <select id="a-add" className="field sel" value={pick || free[0].slug} onChange={(e) => setPick(e.target.value)}>{free.map((t) => <option key={t.slug} value={t.slug}>{t.title}</option>)}</select>
            <button className="btn" disabled={busy} onClick={() => void reorder([...order, pick || free[0].slug])}>Add song</button>
          </div>
        )}
      </section>
      {confirm ? (
        <div className="card stack" role="group" aria-label="Confirm delete"><p>Delete "{a.title}"? Its songs stay in the catalogue.</p><div className="row"><button className="btn p" disabled={busy} onClick={() => void run(async () => { await postJSON("/api/albums/delete", { slug }); go("/albums"); })}>Yes, delete</button><button className="btn g" onClick={() => setConfirm(false)}>Keep it</button></div></div>
      ) : <div className="row"><button className="btn" onClick={() => setConfirm(true)}>Delete album</button></div>}
    </>
  );
}

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Cover } from "../components/Cover";
import { Icon } from "../components/Icon";
import { getJSON, postJSON, type AlbumRow } from "../lib/api";
import { errText } from "../lib/songs";

export const coverOf = (a: AlbumRow) => a.tracks.find((t) => t.art);

// Albums as real releases: a name, a kind, an order, a cover from their first song. Create one here, then open it to add songs and put them in order.
export default function Albums() {
  const [rows, setRows] = useState<AlbumRow[] | null>(null);
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState("album");
  const [err, setErr] = useState("");
  const load = useCallback(() => getJSON<AlbumRow[]>("/api/albums").then((r) => { setRows(r); setErr(""); }).catch((e) => setErr(errText(e))), []);
  useEffect(() => { void load(); }, [load]);
  const create = async (e: React.FormEvent) => { e.preventDefault(); try { await postJSON("/api/albums/save", { title, kind }); setTitle(""); await load(); } catch (x) { setErr(errText(x)); } };
  return (
    <>
      <div className="ph"><h1 className="disp">Albums</h1><p>Releases with an order, a cover and a date.</p></div>
      {err && <div className="card" role="alert"><p className="mu">{err}</p></div>}
      <form className="row" onSubmit={(e) => void create(e)}>
        <label className="sr" htmlFor="al-title">New album title</label>
        <input id="al-title" className="field" style={{ flex: 1, minWidth: 0 }} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="New album" maxLength={120} autoComplete="off" />
        <label className="sr" htmlFor="al-kind">Kind</label>
        <select id="al-kind" className="field sel" value={kind} onChange={(e) => setKind(e.target.value)}><option value="album">Album</option><option value="ep">EP</option><option value="single">Single</option></select>
        <button className="btn p" type="submit" disabled={!title.trim()}>Create</button>
      </form>
      {!rows && !err && <p className="mu" role="status">Loading…</p>}
      {rows && (
        <div className="card" style={{ padding: 8 }}>
          {rows.length ? rows.map((a) => {
            const c = coverOf(a);
            return (
              <Link key={a.slug} className="q" to={`/albums/${a.slug}`}>
                <Cover slug={c?.slug ?? a.slug} title={a.title} art={c?.art} />
                <span className="tx"><b>{a.title}</b><span className="s">{a.kind} · {a.tracks.length} song{a.tracks.length === 1 ? "" : "s"}{a.release_date ? ` · ${a.release_date}` : ""}</span></span>
                <span className={"chip " + (a.status === "published" ? "ok" : "")}>{a.status}</span><Icon name="chevron" />
              </Link>
            );
          }) : <p className="empty">No albums yet.</p>}
        </div>
      )}
    </>
  );
}

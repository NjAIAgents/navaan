import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Icon } from "../components/Icon";
import { getJSON, type Hit } from "../lib/api";
import { errText } from "../lib/songs";

const KIND: Record<string, string> = { track: "Song", album: "Album", playlist: "Playlist", short: "Short" };
const to = (h: Hit) => (h.kind === "track" && h.slug ? `/studio/songs/${h.slug}` : h.kind === "album" ? "/albums" : null);

// One search for songs and albums: type Devanagari or the same words in Roman letters.
export default function Search() {
  const [sp, setSp] = useSearchParams();
  const q = sp.get("q") ?? "";
  const [text, setText] = useState(q);
  const [hits, setHits] = useState<Hit[] | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { setText(q); }, [q]);
  useEffect(() => {
    if (q.trim().length < 2) { setHits(null); return; }
    let live = true; setHits(null); setErr("");
    getJSON<{ hits: Hit[] }>(`/api/search?q=${encodeURIComponent(q)}`).then((r) => { if (live) setHits(r.hits); }).catch((e) => { if (live) setErr(errText(e)); });
    return () => { live = false; };
  }, [q]);
  return (
    <>
      <div className="ph"><h1 className="disp">Search</h1><p>Songs and albums, in Devanagari or Roman letters.</p></div>
      <form role="search" className="row" onSubmit={(e) => { e.preventDefault(); setSp(text.trim() ? { q: text.trim() } : {}); }}>
        <label className="sr" htmlFor="q">Search</label>
        <input id="q" type="search" className="field" style={{ flex: 1, minWidth: 0 }} value={text} onChange={(e) => setText(e.target.value)} placeholder="tere hone se" autoComplete="off" />
        <button className="btn p" type="submit"><Icon name="search" />Search</button>
      </form>
      {err && <div className="card" role="alert"><h2>Search failed</h2><p className="mu">{err}</p></div>}
      {q.trim().length >= 2 && !hits && !err && <p className="mu" role="status">Searching…</p>}
      {hits && (
        <div className="card" style={{ padding: 8 }} aria-live="polite">
          {hits.length ? hits.map((h) => {
            const body = <><span className="tx"><b>{h.title}</b>{h.title_roman && h.title_roman !== h.title && <span className="s">{h.title_roman}</span>}</span><span className="chip">{KIND[h.kind] ?? h.kind}</span></>;
            const p = to(h);
            return p ? <Link key={h.kind + h.id} className="q" to={p}>{body}</Link> : <div key={h.kind + h.id} className="q">{body}</div>;
          }) : <p className="empty">Nothing found for "{q}".</p>}
        </div>
      )}
    </>
  );
}

import { useEffect, useState } from "react";
import { Cover } from "./Cover";
import { LoadMore } from "./LoadMore";
import { getJSON, type Hit, type TrackRow } from "../lib/api";
import { usePaged } from "../lib/paged";
import { errText } from "../lib/songs";

// Pick songs to put in a playlist without leaving it: type to search (Devanagari or Roman letters), or scroll through every song. A song already in the list says so.
export function AddSongs({ have, onAdd }: { have: Set<string>; onAdd: (slug: string) => Promise<void> }) {
  const [q, setQ] = useState(""); const [hits, setHits] = useState<{ slug: string; title: string }[] | null>(null); const [err, setErr] = useState(""); const [busy, setBusy] = useState("");
  const all = usePaged<TrackRow>("/api/catalog/tracks", 24);
  const searching = q.trim().length >= 2;
  useEffect(() => {
    if (!searching) { setHits(null); return; }
    let live = true; const t = setTimeout(() => {
      getJSON<{ hits: Hit[] }>(`/api/search?q=${encodeURIComponent(q.trim())}&kind=track&limit=30`).then((r) => { if (live) setHits(r.hits.filter((h) => h.slug).map((h) => ({ slug: h.slug!, title: h.title }))); }).catch((e) => { if (live) setErr(errText(e)); });
    }, 250);   // wait for a pause in typing
    return () => { live = false; clearTimeout(t); };
  }, [q, searching]);
  const list = searching ? hits : (all.items ?? []).map((t) => ({ slug: t.slug, title: t.title }));
  const add = async (slug: string) => { setBusy(slug); setErr(""); try { await onAdd(slug); } catch (e) { setErr(errText(e)); } finally { setBusy(""); } };
  return (
    <section className="card stack" aria-labelledby="as-h">
      <h2 id="as-h">Add songs</h2>
      <label className="sr" htmlFor="as-q">Search songs</label>
      <input id="as-q" className="field" type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search songs" autoComplete="off" />
      {(err || all.err) && <p role="alert" className="mu">{err || all.err}</p>}
      {list === null || (!searching && all.items === null) ? <p className="mu" role="status">Loading…</p> : !list.length ? <p className="empty">{searching ? "No song matches." : "No songs yet."}</p> : (
        <ul className="hist" aria-label="Songs to add">
          {list.map((s) => (
            <li key={s.slug} className="stp">
              <Cover slug={s.slug} title={s.title} size={40} /><span className="tx"><b>{s.title}</b></span>
              {have.has(s.slug) ? <span className="chip ok">In the playlist</span> : <button className="btn" disabled={busy === s.slug} onClick={() => void add(s.slug)} aria-label={`Add ${s.title}`}>Add</button>}
            </li>
          ))}
        </ul>
      )}
      {!searching && <LoadMore done={all.done} busy={all.busy} more={all.more} />}
    </section>
  );
}

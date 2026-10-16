import { useEffect, useState } from "react";
import { Tile } from "../components/Tile";
import { getJSON, type AlbumRow, type TrackRow } from "../lib/api";
import { errText } from "../lib/songs";
import { Loading } from "../components/Loading";

function Row({ title, rows }: { title: string; rows: TrackRow[] }) {
  const id = "row-" + title.replace(/\W+/g, "-").toLowerCase();
  return (
    <section className="sec" aria-labelledby={id}>
      <div className="sh"><h2 id={id}>{title}</h2><span className="n">{rows.length}</span></div>
      <div className="grid tiles">
        {rows.map((t) => (
          <Tile key={t.slug} to={`/song/${t.slug}`} slug={t.slug} title={t.title} art={t.art} sub={[t.language, t.genre].filter(Boolean).join(" · ") || "NAVAAN"} play={{ slug: t.slug, title: t.title, queue: rows.map((r) => ({ slug: r.slug, title: r.title })), label: t.title }} />
        ))}
      </div>
    </section>
  );
}

// Browse: what is out, newest first, then by language. Covers fade in over their colour; only songs that are published (and, for a listener, licence-confirmed) are here.
export default function Browse() {
  const [rows, setRows] = useState<TrackRow[] | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { getJSON<TrackRow[]>("/api/catalog/tracks").then(setRows).catch((e) => setErr(errText(e))); }, []);
  const [albums, setAlbums] = useState<AlbumRow[]>([]);
  useEffect(() => { getJSON<AlbumRow[]>("/api/catalog/albums").then((r) => setAlbums(Array.isArray(r) ? r : [])).catch(() => setAlbums([])); }, []);   // expected: no albums is not an error
  const langs = rows ? [...new Set(rows.map((r) => r.language).filter(Boolean))].sort() : [];
  return (
    <>
      <div className="ph"><h1 className="disp">Browse</h1><p>Songs by NAVAAN.</p></div>
      {err && <div className="card" role="alert"><h2>Could not load the songs</h2><p className="mu">{err}</p></div>}
      {!rows && !err && <Loading />}
      {rows && !rows.length && <div className="card"><p className="empty">No songs are out yet.</p></div>}
      {rows && rows.length > 0 && <Row title="Newest" rows={rows.slice(0, 8)} />}
      {albums.length > 0 && (
        <section className="sec" aria-labelledby="row-albums">
          <div className="sh"><h2 id="row-albums">Albums</h2><span className="n">{albums.length}</span></div>
          <div className="grid tiles">{albums.map((al) => { const c = al.tracks.find((t) => t.art) ?? al.tracks[0]; return (
            <Tile key={al.slug} to={`/album/${al.slug}`} slug={c.slug} title={al.title} art={c.art} sub={`${al.kind} · ${al.tracks.length} song${al.tracks.length === 1 ? "" : "s"}`} play={{ queue: al.tracks.map((t) => ({ slug: t.slug, title: t.title })), label: al.title }} />
          ); })}</div>
        </section>
      )}
      {rows && langs.map((l) => <Row key={l} title={l} rows={rows.filter((r) => r.language === l)} />)}
    </>
  );
}

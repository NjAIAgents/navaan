import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Cover } from "../components/Cover";
import { getJSON, type TrackRow } from "../lib/api";
import { errText } from "../lib/songs";

function Row({ title, rows }: { title: string; rows: TrackRow[] }) {
  const id = "row-" + title.replace(/\W+/g, "-").toLowerCase();
  return (
    <section className="sec" aria-labelledby={id}>
      <div className="sh"><h2 id={id}>{title}</h2><span className="n">{rows.length}</span></div>
      <div className="grid tiles">
        {rows.map((t) => (
          <Link key={t.slug} className="tile" to={`/song/${t.slug}`}>
            <Cover slug={t.slug} title={t.title} size={160} art={t.art} />
            <b>{t.title}</b><span className="s">{[t.language, t.genre].filter(Boolean).join(" · ") || "NAVAAN"}</span>
          </Link>
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
  const langs = rows ? [...new Set(rows.map((r) => r.language).filter(Boolean))].sort() : [];
  return (
    <>
      <div className="ph"><h1 className="disp">Browse</h1><p>Songs by NAVAAN.</p></div>
      {err && <div className="card" role="alert"><h2>Could not load the songs</h2><p className="mu">{err}</p></div>}
      {!rows && !err && <p className="mu" role="status">Loading…</p>}
      {rows && !rows.length && <div className="card"><p className="empty">No songs are out yet.</p></div>}
      {rows && rows.length > 0 && <Row title="Newest" rows={rows.slice(0, 8)} />}
      {rows && langs.map((l) => <Row key={l} title={l} rows={rows.filter((r) => r.language === l)} />)}
    </>
  );
}

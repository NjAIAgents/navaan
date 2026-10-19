import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Cover } from "../components/Cover";
import { getJSON, type SongRow } from "../lib/api";
import { GATE_TITLE, gateTitle } from "../lib/gates";
import { classic, errText, itemPath } from "../lib/songs";
import { Loading } from "../components/Loading";

const KIND: Record<string, string> = { music: "Song", inspiration: "Inspiration", aha: "Aha-lorithm", blog: "Blog" };

// Everything waiting for a yes, across songs and inspiration, grouped by what is being asked. One action per row: open it and decide there, where the text is.
export default function Approvals() {
  const [rows, setRows] = useState<SongRow[] | null>(null); const [thumbs, setThumbs] = useState<SongRow[]>([]);
  const [err, setErr] = useState("");
  useEffect(() => { getJSON<SongRow[]>("/api/songs").then((r) => { setRows(r.filter((s) => s.status === "approval")); setThumbs(r.filter((s) => s.thumb_pending)); }).catch((e) => setErr(errText(e))); }, []);   // a thumbnail YouTube refused is something only you can fix too
  const order = Object.keys(GATE_TITLE);
  const gates = rows ? [...new Set(rows.map((r) => r.next.gate ?? ""))].sort((a, b) => order.indexOf(a) - order.indexOf(b)) : [];
  return (
    <>
      <div className="ph"><h1 className="disp">Approvals</h1><p>Everything waiting for your yes, in one list.</p></div>
      {err && <div className="card" role="alert"><h2>Could not load approvals</h2><p className="mu">{err}</p></div>}
      {!rows && !err && <Loading />}
      {rows && !rows.length && !thumbs.length && <div className="card"><p className="empty">Nothing is waiting for you.</p></div>}
      {thumbs.length > 0 && (
        <section className="sec" aria-labelledby="g-thumb">
          <div className="sh"><h2 id="g-thumb">Set the YouTube thumbnail</h2><span className="n">{thumbs.length}</span></div>
          <div className="card" style={{ padding: 8 }}>
            <p className="mu" style={{ padding: "4px 8px" }}>YouTube refused the custom thumbnail because the channel is not phone verified. Verify it at <a href="https://www.youtube.com/verify" target="_blank" rel="noreferrer">youtube.com/verify</a>; each item's page has the command that sets it.</p>
            {thumbs.map((s) => { const to = itemPath(s.type, s.slug); return (
              <div className="q" key={s.slug}><Cover slug={s.slug} title={s.title} art={s.art} /><span className="tx"><b>{s.title || s.slug}</b><span className="s">{KIND[s.type] ?? s.type} · {s.slug}</span></span>{to && <Link className="btn" to={to}>Open{" "}<span className="sr">{s.title || s.slug}</span></Link>}</div>); })}
          </div>
        </section>
      )}
      {gates.map((g) => {
        const items = rows!.filter((r) => (r.next.gate ?? "") === g);
        return (
          <section className="sec" key={g} aria-labelledby={`g-${g}`}>
            <div className="sh"><h2 id={`g-${g}`}>{g ? gateTitle(g) : "Other"}</h2><span className="n">{items.length}</span></div>
            <div className="card" style={{ padding: 8 }}>
              {items.map((s) => {
                const to = itemPath(s.type, s.slug);
                return (
                  <div className="q" key={s.slug}>
                    <Cover slug={s.slug} title={s.title} art={s.art} />
                    <span className="tx"><b>{s.title || s.slug}</b><span className="s">{KIND[s.type] ?? s.type} · {s.slug}</span></span>
                    {to ? <Link className="btn p" to={to}>Review<span className="sr"> {s.title || s.slug}</span></Link> : <a className="btn p" href={classic(s.slug)}>Review<span className="sr"> {s.title || s.slug}</span></a>}
                  </div>
                );
              })}
            </div>
          </section>
        );
      })}
    </>
  );
}

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Cover } from "../components/Cover";
import { Icon } from "../components/Icon";
import { getJSON, type SongRow } from "../lib/api";
import { errText, nextAction } from "../lib/songs";

const FILTERS = [["all", "All"], ["approval", "Needs you"], ["production", "In production"], ["done", "Done"]] as const;
type Filter = (typeof FILTERS)[number][0];

export default function Songs() {
  const [rows, setRows] = useState<SongRow[] | null>(null);
  const [err, setErr] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  useEffect(() => { getJSON<SongRow[]>("/api/songs").then((r) => setRows(r.filter((s) => s.type === "music"))).catch((e) => setErr(errText(e))); }, []);
  const shown = rows?.filter((s) => filter === "all" || s.status === filter) ?? [];
  return (
    <>
      <div className="ph"><h1 className="disp">Songs</h1><p>Every song, its steps and its approvals.</p></div>
      <div className="seg" role="group" aria-label="Filter songs" style={{ alignSelf: "flex-start", flexWrap: "wrap" }}>
        {FILTERS.map(([k, label]) => <button key={k} aria-pressed={filter === k} onClick={() => setFilter(k)}>{label}{rows && k !== "all" ? <span className="mu"> {rows.filter((s) => s.status === k).length}</span> : null}</button>)}
      </div>
      {err && <div className="card" role="alert"><h2>Could not load your songs</h2><p className="mu">{err}</p></div>}
      {!rows && !err && <p className="mu" role="status">Loading…</p>}
      {rows && (
        <div className="card" style={{ padding: 8 }}>
          {shown.length ? shown.map((s) => (
            <Link key={s.slug} className="q" to={`/studio/songs/${s.slug}`}>
              <Cover slug={s.slug} title={s.title} />
              <span className="tx"><b>{s.title || s.slug}</b><span className="s">{s.state ?? "new"} · {nextAction(s)}</span></span>
              <span className={"chip " + (s.status === "approval" ? "wn" : s.published ? "ok" : "")} title="steps done">{s.steps_done}/{s.steps_total}</span>
              <Icon name="chevron" />
            </Link>
          )) : <p className="empty">{rows.length ? "No songs in this view." : "No songs yet."}</p>}
        </div>
      )}
    </>
  );
}

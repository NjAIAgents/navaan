import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Cover } from "../components/Cover";
import { Equaliser } from "../components/Equaliser";
import { Icon } from "../components/Icon";
import { NewItem } from "../components/NewItem";
import { useMe } from "../lib/me";
import { usePlayer } from "../lib/player";
import { getJSON, type SongRow } from "../lib/api";
import { errText, itemPath, nextAction } from "../lib/songs";
import { fmtCentral } from "../lib/datetime";
import { Loading } from "../components/Loading";

const FILTERS = [["all", "All"], ["approval", "Needs you"], ["production", "In production"], ["done", "Done"]] as const;
type Filter = (typeof FILTERS)[number][0];

export function ItemList({ type, title, blurb, noun }: { type: string; title: string; blurb: string; noun: string }) {
  const [rows, setRows] = useState<SongRow[] | null>(null);
  const [err, setErr] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const pl = usePlayer(); const me = useMe();
  useEffect(() => { getJSON<SongRow[]>("/api/songs").then((r) => setRows(r.filter((s) => s.type === type))).catch((e) => setErr(errText(e))); }, []);
  const shown = rows?.filter((s) => filter === "all" || s.status === filter) ?? [];
  return (
    <>
      <div className="ph"><h1 className="disp">{title}</h1><p>{blurb}</p></div>
      {me.studio && (type === "music" || type === "inspiration" || type === "aha") && <NewItem type={type} />}
      <div className="seg" role="group" aria-label={`Filter ${noun}s`} style={{ alignSelf: "flex-start", flexWrap: "wrap" }}>
        {FILTERS.map(([k, label]) => <button key={k} aria-pressed={filter === k} onClick={() => setFilter(k)}>{label}{rows && k !== "all" ? <span className="mu"> {rows.filter((s) => s.status === k).length}</span> : null}</button>)}
      </div>
      {err && <div className="card" role="alert"><h2>Could not load your {noun}s</h2><p className="mu">{err}</p></div>}
      {!rows && !err && <Loading />}
      {rows && (
        <div className="card" style={{ padding: 8 }}>
          {shown.length ? shown.map((s) => (
            <Link key={s.slug} className="q" to={itemPath(type, s.slug) ?? "/studio"}>
              <Cover slug={s.slug} title={s.title} art={s.art} />
              <span className="tx"><b>{s.title || s.slug}</b><span className="s">{nextAction(s)}</span></span>
              {pl.slug === s.slug && pl.playing && <Equaliser />}
              <span className={"chip " + (s.status === "approval" ? "wn" : s.published || s.schedule_at ? "ok" : "")} title={`${s.steps_done} of ${s.steps_total} steps done`}>{s.status === "approval" ? "Needs you" : s.published ? "Published" : s.schedule_at ? `Scheduled · ${fmtCentral(s.schedule_at)}` : `${s.steps_done}/${s.steps_total}`}</span>
              <Icon name="chevron" />
            </Link>
          )) : <p className="empty">{rows.length ? `No ${noun}s in this view.` : `No ${noun}s yet.`}</p>}
        </div>
      )}
    </>
  );
}

export default function Songs() { return <ItemList type="music" title="Songs" blurb="Every song, its steps and its approvals." noun="song" />; }

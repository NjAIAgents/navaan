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

const FILTERS = [["all", "All"], ["approval", "Needs you"], ["production", "In production"], ["done", "Done"], ["published", "Published"], ["cloud", "In the cloud"]] as const;
type Filter = (typeof FILTERS)[number][0];
type Views = Record<string, { views: number | null; yt_views?: number | null }>;
const match = (s: SongRow, f: Filter) => f === "all" || (f === "published" ? s.published : f === "cloud" ? !!s.archived : s.status === f);
const STATUS: Record<string, string> = { approval: "Needs you", production: "In production", done: "Done" };
// Where the files are: only here, in the bucket (and checked), the bucket older than the local copy, or the local copy cleaned after a checked archive.
const cloud = (s: SongRow): [string, string] => (s.cleaned ? ["Local cleaned", ""] : s.archived ? (s.verified === false ? ["Bucket stale", "wn"] : ["In the cloud", "ok"]) : ["Local only", ""]);
const views = (v?: Views[string]) => { if (!v) return ""; const p = [v.views != null ? `${v.views.toLocaleString()} on Instagram` : "", v.yt_views != null ? `${v.yt_views.toLocaleString()} on YouTube` : ""].filter(Boolean); return p.length ? `${p.join(" · ")} views` : ""; };
const pref = (k: string, d: string) => { try { return localStorage.getItem(k) || d; } catch { return d; } };   // expected: storage can be blocked
const keep = (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* expected: storage can be blocked */ } };

export function ItemList({ type, title, blurb, noun }: { type: string; title: string; blurb: string; noun: string }) {
  const [rows, setRows] = useState<SongRow[] | null>(null);
  const [err, setErr] = useState("");
  const [filter, setFilter] = useState<Filter>("all"); const [q, setQ] = useState("");
  const [group, setGroup] = useState(() => pref("navaan.list.group", "none")); const [grid, setGrid] = useState(() => pref("navaan.list.view", "list") === "grid");
  const [vw, setVw] = useState<Views>({});
  const pl = usePlayer(); const me = useMe();
  useEffect(() => { getJSON<SongRow[]>("/api/songs").then((r) => setRows(r.filter((s) => s.type === type))).catch((e) => setErr(errText(e))); }, []);
  useEffect(() => { if (me.studio) getJSON<Views>("/api/analytics/by-song").then((x) => setVw(x && typeof x === "object" ? x : {})).catch(() => setVw({})); }, [me.studio]);   // expected: no analytics, no view counts
  const needle = q.trim().toLowerCase();
  const shown = rows?.filter((s) => match(s, filter) && (!needle || `${s.title} ${s.slug} ${s.album}`.toLowerCase().includes(needle))) ?? [];
  const groups: [string, SongRow[]][] = group === "none" ? [["", shown]] : Object.entries(shown.reduce<Record<string, SongRow[]>>((a, s) => { const k = group === "album" ? s.album || "No album" : STATUS[s.status] ?? s.status; (a[k] ??= []).push(s); return a; }, {}));
  const item = (s: SongRow) => { const [cl, clk] = cloud(s); const v = views(vw[s.slug]); return (
    <Link key={s.slug} className={grid ? "q tile" : "q"} to={itemPath(type, s.slug) ?? "/studio"}>
      <Cover slug={s.slug} title={s.title} art={s.art} />
      <span className="tx"><b>{s.title || s.slug}</b><span className="s">{nextAction(s)}</span>
        <span className="s row" style={{ gap: 6, flexWrap: "wrap" }}><meter min={0} max={s.steps_total || 1} value={s.steps_done} aria-label={`${s.steps_done} of ${s.steps_total} steps done`} style={{ width: 80 }} />
          <span className={"chip " + clk}>{cl}</span>{s.thumb_pending && <span className="chip wn">Thumbnail not set</span>}{v && <span>{v}</span>}</span></span>
      {pl.slug === s.slug && pl.playing && <Equaliser />}
      <span className={"chip " + (s.status === "approval" ? "wn" : s.published || s.schedule_at ? "ok" : "")} title={`${s.steps_done} of ${s.steps_total} steps done`}>{s.status === "approval" ? "Needs you" : s.published ? "Published" : s.schedule_at ? `Scheduled · ${fmtCentral(s.schedule_at)}` : `${s.steps_done}/${s.steps_total}`}</span>
      {!grid && <Icon name="chevron" />}
    </Link>); };
  return (
    <>
      <div className="ph"><h1 className="disp">{title}</h1><p>{blurb}</p></div>
      {me.studio && (type === "music" || type === "inspiration" || type === "aha" || type === "blog" || type === "reel") && <NewItem type={type} />}
      <div className="seg" role="group" aria-label={`Filter ${noun}s`} style={{ alignSelf: "flex-start", flexWrap: "wrap" }}>
        {FILTERS.map(([k, label]) => <button key={k} aria-pressed={filter === k} onClick={() => setFilter(k)}>{label}{rows && k !== "all" ? <span className="mu"> {rows.filter((s) => match(s, k)).length}</span> : null}</button>)}
      </div>
      <div className="row" style={{ flexWrap: "wrap" }}>
        <label className="sr" htmlFor="il-q">Find a {noun}</label><input id="il-q" className="field" type="search" placeholder={`Find a ${noun}`} value={q} onChange={(e) => setQ(e.target.value)} style={{ flex: 1, minWidth: 180 }} />
        <label className="sr" htmlFor="il-g">Group by</label><select id="il-g" className="field sel" value={group} onChange={(e) => { setGroup(e.target.value); keep("navaan.list.group", e.target.value); }}><option value="none">No grouping</option><option value="album">By album</option><option value="status">By status</option></select>
        <div className="seg" role="group" aria-label="Show as">{([["list", "List"], ["grid", "Grid"]] as const).map(([k, l]) => <button key={k} aria-pressed={(k === "grid") === grid} onClick={() => { setGrid(k === "grid"); keep("navaan.list.view", k); }}>{l}</button>)}</div>
      </div>
      {err && <div className="card" role="alert"><h2>Could not load your {noun}s</h2><p className="mu">{err}</p></div>}
      {!rows && !err && <Loading />}
      {rows && (shown.length ? groups.map(([g, list]) => (
        <section key={g || "all"} className="stack" aria-label={g || undefined}>
          {g && <h2 className="sh">{g} <span className="n">{list.length}</span></h2>}
          <div className={grid ? "card tiles" : "card"} style={{ padding: 8 }}>{list.map(item)}</div>
        </section>
      )) : <div className="card"><p className="empty">{rows.length ? `No ${noun}s in this view.` : `No ${noun}s yet.`}</p></div>)}
    </>
  );
}

export default function Songs() { return <ItemList type="music" title="Songs" blurb="Every song, its steps and its approvals." noun="song" />; }

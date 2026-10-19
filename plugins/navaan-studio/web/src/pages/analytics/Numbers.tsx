import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getJSON, postJSON, type Overview, type SongRow } from "../../lib/api";
import { errText } from "../../lib/songs";
import { Spark } from "./Charts";

const KPI: Record<"instagram" | "youtube", [string, string, string?][]> = {
  instagram: [["followers", "Followers", "followers_change"], ["views", "Views"], ["interactions", "Interactions"], ["accounts_engaged", "Accounts engaged"], ["waiting", "Comments waiting"]],
  youtube: [["subscribers", "Subscribers", "subscribers_change"], ["views", "Views"], ["watch_hours", "Watch hours"], ["subs_gained", "Subscribers gained"], ["waiting", "Comments waiting"]],
};
const n = (v: number | null | undefined) => (v == null ? "n/a" : Number.isInteger(v) ? v.toLocaleString() : v.toLocaleString(undefined, { maximumFractionDigits: 1 }));
const day = (s: string) => (s ? new Date(s).toLocaleDateString([], { day: "numeric", month: "short" }) : "");

// A post or video the studio could not match to a song: pick the song and it counts for it.
function LinkTo({ id, kind, reload }: { id: string; kind: "post" | "video"; reload?: () => Promise<unknown> | void }) {
  const [songs, setSongs] = useState<SongRow[] | null>(null); const [pick, setPick] = useState(""); const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  useEffect(() => { void getJSON<SongRow[]>("/api/songs").then(setSongs).catch((e) => setErr(errText(e))); }, []);
  const save = async () => { setBusy(true); setErr(""); try { await postJSON(kind === "post" ? "/api/analytics/link" : "/api/analytics/link-video", kind === "post" ? { media_id: id, slug: pick } : { video_id: id, slug: pick }); await reload?.(); } catch (e) { setErr(errText(e)); } finally { setBusy(false); } };
  return (
    <span className="row">
      <label className="sr" htmlFor={`ln-${id}`}>Link {id} to a song</label>
      <select id={`ln-${id}`} className="field sel" value={pick} onChange={(e) => setPick(e.target.value)}><option value="">Link to a song…</option>{(songs ?? []).map((s) => <option key={s.slug} value={s.slug}>{s.slug} {s.title}</option>)}</select>
      <button className="btn g" disabled={!pick || busy} onClick={() => void save()} aria-label={`Link ${id}`}>Link</button>
      {err && <span role="alert" className="mu">{err}</span>}
    </span>
  );
}

// A small line of how views grew between collects (the classic "Views over time" column).
function Trend({ v, label }: { v?: number[]; label: string }) {
  if (!v || v.length < 2) return <span className="mu">needs 2 collects</span>;
  const lo = Math.min(...v), hi = Math.max(...v), span = hi - lo || 1;
  const path = v.map((x, i) => `${i ? "L" : "M"}${((i / (v.length - 1)) * 96).toFixed(1)},${(24 - ((x - lo) / span) * 20).toFixed(1)}`).join(" ");
  return <svg role="img" aria-label={`${label}: views from ${v[0].toLocaleString()} to ${v[v.length - 1].toLocaleString()}`} viewBox="0 0 96 26" width={96} height={26}><path d={path} fill="none" stroke="var(--ac)" strokeWidth={2} /></svg>;
}

type Col<T> = [keyof T & string, string, ((r: T) => string)?];
// A table whose numbers sort by a button in their header; empty values go last either way.
function Sortable<T extends Record<string, unknown>>({ rows, cols, first, sub, label, trend, rowKey }: { rows: T[]; cols: Col<T>[]; first: string; sub: (r: T) => React.ReactNode; label: (r: T) => React.ReactNode; trend: (r: T) => number[] | undefined; rowKey: (r: T) => string }) {
  const [by, setBy] = useState<string>("views"); const [dir, setDir] = useState(-1);
  const sorted = [...rows].sort((a, b) => { const x = a[by] as number | null | undefined, y = b[by] as number | null | undefined; if (x == null && y == null) return 0; if (x == null) return 1; if (y == null) return -1; return (x > y ? 1 : x < y ? -1 : 0) * dir; });
  const sortOn = (k: string) => { if (k === by) setDir(-dir); else { setBy(k); setDir(-1); } };
  return (
    <table className="rt"><thead><tr><th>{first}</th>{cols.map(([k, l]) => <th key={k} aria-sort={by === k ? (dir < 0 ? "descending" : "ascending") : "none"}><button className="th-sort" onClick={() => sortOn(k)}>{l}{by === k ? (dir < 0 ? " ▼" : " ▲") : ""}</button></th>)}<th>Views over time</th></tr></thead>
      <tbody>{sorted.map((r) => (
        <tr key={rowKey(r)}><td data-label={first}>{label(r)}<div className="mu" style={{ fontSize: 13 }}>{sub(r)}</div></td>
          {cols.map(([k, l, f]) => <td key={k} data-label={l}>{f ? f(r) : n(r[k] as number | null)}</td>)}
          <td data-label="Views over time"><Trend v={trend(r)} label={String(r.title ?? r.name ?? "")} /></td></tr>
      ))}</tbody></table>
  );
}

const pct = (v: number | null | undefined) => (v == null ? "n/a" : `${n(v)}%`);
const meta = (r: { account?: string; language?: string; genre?: string }, when: string) => [r.account, day(when), r.language, r.genre].filter(Boolean).join(" · ");
type Post = NonNullable<Overview["posts"]>[number]; type Video = NonNullable<Overview["videos"]>[number];

function PostsTable({ d, reload }: { d: Overview; reload?: () => Promise<unknown> | void }) {
  const P = d.posts ?? [];
  const cols: Col<Post>[] = [["views", "Views"], ["reach", "Reach"], ["saved", "Saves"], ["shares", "Shares"], ["like_count", "Likes"], ["comments_count", "Comments"], ["avg_watch_s", "Avg watch (s)"], ["save_rate", "Save rate", (r) => pct(r.save_rate)], ["engagement_rate", "Engagement", (r) => pct(r.engagement_rate)]];
  return (
    <section className="sec" aria-labelledby="top-h">
      <div className="sh"><h2 id="top-h">Posts</h2><span className="n">{P.length}</span></div>
      <div className="card" style={{ padding: 8, overflowX: "auto" }}>
        {P.length ? <Sortable<Post> rows={P} cols={cols} first="Post" rowKey={(p) => p.media_id} trend={(p) => p.trend} sub={(p) => meta(p, p.posted_at)}
          label={(p) => <>{p.slug ? <Link to={`/studio/songs/${p.slug}`}>{p.title || p.slug}</Link> : <a href={p.permalink} target="_blank" rel="noreferrer">{p.title || p.media_id}</a>}{!p.slug && <LinkTo id={p.media_id} kind="post" reload={reload} />}</>} />
          : <p className="empty">Nothing collected for this period.</p>}
        <p className="mu" style={{ padding: "4px 8px" }}>Latest numbers per post. Sort by any column.</p>
      </div>
    </section>
  );
}

function VideosTable({ d, reload }: { d: Overview; reload?: () => Promise<unknown> | void }) {
  const [kind, setKind] = useState<"all" | "video" | "short">("all");
  const V = (d.videos ?? []).filter((v) => kind === "all" || v.kind === kind);
  const cols: Col<Video>[] = [["views", "Views"], ["likes", "Likes"], ["comments", "Comments"], ["minutes_watched", "Watch (min)"], ["avg_view_pct", "Avg viewed", (r) => pct(r.avg_view_pct)], ["avg_view_s", "Avg view (s)", (r) => (r.avg_view_s == null ? "n/a" : String(Math.round(r.avg_view_s)))], ["subs_gained", "Subs gained"], ["subs_per_1000", "Subs / 1k views"]];
  return (
    <section className="sec" aria-labelledby="top-h">
      <div className="sh"><h2 id="top-h">Videos</h2><span className="n">{V.length}</span>
        <div className="seg" role="group" aria-label="Show" style={{ marginLeft: "auto" }}>{([["all", "All"], ["video", "Videos"], ["short", "Shorts"]] as const).map(([k, l]) => <button key={k} aria-pressed={kind === k} onClick={() => setKind(k)}>{l}</button>)}</div></div>
      <div className="card" style={{ padding: 8, overflowX: "auto" }}>
        {V.length ? <Sortable<Video> rows={V} cols={cols} first="Video" rowKey={(v) => v.video_id} trend={(v) => v.trend} sub={(v) => <><span className="chip">{v.kind === "short" ? "Short" : "video"}</span>{v.privacy && v.privacy !== "public" && <span className="chip wn"> {v.privacy}</span>} {meta(v, v.published_at)}</>}
          label={(v) => <>{v.slug ? <Link to={`/studio/songs/${v.slug}`}>{v.name || v.title}</Link> : <a href={v.url} target="_blank" rel="noreferrer">{v.name || v.title || v.video_id}</a>}{!v.slug && <LinkTo id={v.video_id} kind="video" reload={reload} />}</>} />
          : <p className="empty">Nothing collected for this period.</p>}
        <p className="mu" style={{ padding: "4px 8px" }}>Latest numbers per video. YouTube does not share impressions or click-through rate with any API, so those stay in YouTube Studio.</p>
      </div>
    </section>
  );
}

// Every collect: when, which account, how it went, what it brought in (the classic "Collector runs" table).
function Runs({ d }: { d: Overview }) {
  const got = (st?: Record<string, unknown>) => Object.entries(st ?? {}).filter(([, v]) => typeof v === "number" && v > 0).slice(0, 4).map(([k, v]) => `${v} ${k.replace(/_/g, " ")}`).join(", ") || "nothing new";
  return (
    <section className="sec" aria-labelledby="runs-h">
      <div className="sh"><h2 id="runs-h">Collector runs</h2><span className="n">{d.runs.length}</span></div>
      <div className="card" style={{ padding: 8, overflowX: "auto" }}>
        <table className="rt"><thead><tr><th>When</th><th>Account</th><th>Status</th><th>Collected</th><th>Notes</th></tr></thead>
          <tbody>{d.runs.map((r, i) => (
            <tr key={i}><td data-label="When">{new Date(r.finished_at || r.started_at).toLocaleString([], { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" })}</td><td data-label="Account">{r.label ?? ""}</td>
              <td data-label="Status"><span className={"chip " + (r.status === "ok" ? "ok" : r.status === "running" ? "" : "wn")}>{r.status}</span></td><td data-label="Collected">{got(r.stats)}</td>
              <td data-label="Notes" title={r.first_error}>{r.errors ? `${r.errors} note${r.errors === 1 ? "" : "s"}: ${r.first_error.slice(0, 80)}` : "none"}</td></tr>
          ))}</tbody></table>
        {d.db && <p className="mu" style={{ padding: "4px 8px" }}>Database: <code>{d.db}</code></p>}
      </div>
    </section>
  );
}

export default function Numbers({ d, platform, reload }: { d: Overview; platform: "instagram" | "youtube"; reload?: () => Promise<unknown> | void }) {
  const run = d.runs.length > 0;
  return (
    <>
      <div className="kpis">
        {KPI[platform].map(([k, label, ch]) => (
          <div className="card kpi" key={k}><span className="mu">{label}</span><b>{n(d.kpis[k])}</b>{ch && d.kpis[ch] != null && <span className={"chip " + ((d.kpis[ch] as number) >= 0 ? "ok" : "bad")}>{(d.kpis[ch] as number) >= 0 ? "+" : ""}{n(d.kpis[ch])}</span>}</div>
        ))}
      </div>
      <div className="grid">{Object.entries(d.series).map(([k, pts]) => <Spark key={k} label={k.replace(/_/g, " ")} points={pts} />)}</div>
      {platform === "instagram" ? <PostsTable d={d} reload={reload} /> : <VideosTable d={d} reload={reload} />}
      {run && <Runs d={d} />}
    </>
  );
}

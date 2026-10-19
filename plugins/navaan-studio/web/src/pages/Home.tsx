import { useEffect, useState, type ReactNode } from "react";
import { Cover } from "../components/Cover";
import { Icon } from "../components/Icon";
import { Link } from "react-router-dom";
import { itemPath } from "../lib/songs";
import { getJSON, type SongRow } from "../lib/api";
import { Loading } from "../components/Loading";

const classic = (slug: string) => `/legacy#/song/${slug}`;

// Songs and inspiration open in the new Studio screens; anything else still opens in the classic view.
const Wrap = ({ s, children }: { s: SongRow; children: ReactNode }) =>
  itemPath(s.type, s.slug) ? <Link className="q" to={itemPath(s.type, s.slug)!}>{children}</Link> : <a className="q" href={classic(s.slug)}>{children}</a>;

function Row({ s }: { s: SongRow }) {
  const label = s.next?.gate ? `Waiting for you: ${s.next.gate.replace(/_/g, " ")}` : s.status === "done" ? (s.published ? "Published" : "Done") : s.next?.label || s.next?.step?.replace(/_/g, " ") || "In production";
  return (
    <Wrap s={s}>
      <Cover slug={s.slug} title={s.title} art={s.art} />
      <span className="tx"><b>{s.title || s.slug}</b><span className="s">{s.slug} · {label}</span></span>
      <span className={"chip " + (s.status === "approval" ? "wn" : s.published ? "ok" : "")}>{s.steps_done}/{s.steps_total}</span>
      <Icon name="chevron" />
    </Wrap>
  );
}

function Group({ title, rows, empty }: { title: string; rows: SongRow[]; empty: string }) {
  return (
    <section className="sec" aria-labelledby={"h-" + title}>
      <div className="sh"><h2 id={"h-" + title}>{title}</h2><span className="n">{rows.length}</span></div>
      <div className="card" style={{ padding: 8 }}>{rows.length ? rows.map((s) => <Row key={s.slug} s={s} />) : <p className="empty">{empty}</p>}</div>
    </section>
  );
}

// The classic dashboard's tiles, its by-stage bar and the latest covers (NAV-29): how much is out, how much is safe in the bucket, where the rest stands.
function Overview({ rows }: { rows: SongRow[] }) {
  const n = (f: (r: SongRow) => boolean) => rows.filter(f).length;
  const stage = [["Needs you", n((r) => r.status === "approval"), "var(--wn)"], ["In production", n((r) => r.status === "production"), "var(--ac)"], ["Done", n((r) => r.status === "done"), "var(--ok)"]] as const;
  const recent = [...rows].filter((r) => r.cover).sort((a, b) => (b.mtime ?? 0) - (a.mtime ?? 0)).slice(0, 6);
  return (<>
    <div className="kpis">
      <div className="card kpi"><span className="mu">Items</span><b>{rows.length}</b></div>
      <div className="card kpi"><span className="mu">Published</span><b>{n((r) => r.published)}</b><span className="mu">{n((r) => !!r.instagram)} on Instagram</span></div>
      <div className="card kpi"><span className="mu">In the cloud</span><b>{n((r) => !!r.archived)}</b><span className="mu">{n((r) => !!r.archived && r.verified !== false)} checked · {n((r) => !!r.cleaned)} cleaned here</span></div>
    </div>
    {rows.length > 0 && <div className="card stack" style={{ gap: 6 }}>
      <div role="img" aria-label={`By stage: ${stage.map(([l, c]) => `${c} ${l.toLowerCase()}`).join(", ")}`} style={{ display: "flex", height: 12, borderRadius: 6, overflow: "hidden", background: "var(--s2)" }}>{stage.map(([l, c, col]) => <span key={l} style={{ width: `${(100 * c) / rows.length}%`, background: col }} />)}</div>
      <p className="mu">{stage.map(([l, c]) => `${l} ${c}`).join(" · ")}</p>
    </div>}
    {recent.length > 0 && <section className="sec" aria-labelledby="h-recent"><div className="sh"><h2 id="h-recent">Recent covers</h2></div>
      <div className="tiles card" style={{ padding: 8 }}>{recent.map((s) => <Link key={s.slug} className="q tile" to={itemPath(s.type, s.slug) ?? "/studio"}><Cover slug={s.slug} title={s.title} art={s.art} /><span className="tx"><b>{s.title || s.slug}</b></span></Link>)}</div></section>}
  </>);
}

// Foundation story: the one real screen is the dashboard, on the existing API, so the shell is proven against live data.
// The rich Studio screens follow in NAV-13 to NAV-15.
export default function Home() {
  const [rows, setRows] = useState<SongRow[] | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { getJSON<SongRow[]>("/api/songs").then(setRows).catch((e: Error & { requestId?: string }) => setErr(`${e.message}${e.requestId ? ` (ref ${e.requestId})` : ""}`)); }, []);
  return (
    <>
      <div className="ph"><h1 className="disp">Welcome back</h1><p>What needs you, what is being made, and what is out.</p></div>
      {err && <div className="card" role="alert"><h2>Could not load your songs</h2><p className="mu">{err}</p></div>}
      {!rows && !err && <Loading />}
      {rows && (
        <>
          <Overview rows={rows} />
          <Group title="Needs you" rows={rows.filter((r) => r.status === "approval" || !!r.thumb_pending)} empty="Nothing is waiting for you." />
          <Group title="In production" rows={rows.filter((r) => r.status === "production")} empty="Nothing is being made right now." />
          <Group title="Done" rows={rows.filter((r) => r.status === "done")} empty="Nothing finished yet." />
        </>
      )}
    </>
  );
}

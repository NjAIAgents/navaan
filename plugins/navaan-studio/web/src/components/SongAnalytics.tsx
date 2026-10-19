import { useEffect, useState } from "react";
import { getJSON, postJSON } from "../lib/api";
import { errText } from "../lib/songs";

// One song's numbers on Instagram and YouTube, post by post and video by video (NAV-29 parity with the classic Performance tab):
// how it ranks against the account's others, the numbers, how views grew, retention, what the analysis says, comments waiting, link and unlink.
type Finding = { finding_id?: string; severity: string; title: string; detail?: string };
type RecLite = { rec_id: string; title: string; action: string; why?: string };
type Comment = { username: string; text: string; posted_at: string };
type Hist = { captured_at: string; views: number | null }[];
type Post = { media_id: string; permalink: string; caption: string; posted_at: string; product_type: string; account: string; username?: string; captured_at?: string;
  views: number | null; reach: number | null; saved: number | null; shares: number | null; like_count: number | null; comments_count: number | null; save_rate: number | null; avg_watch_s: number | null;
  history?: Hist; compare?: { account_posts: number; views_rank: number | null; median_views: number | null; views_vs_median: number | null; median_save_rate: number | null; median_avg_watch_s: number | null };
  findings?: Finding[]; recommendations?: RecLite[]; comments_waiting: Comment[]; comments_total: number };
type Video = { video_id: string; title: string; url: string; kind?: string; privacy?: string; channel?: string; account?: string; published_at?: string; captured_at?: string;
  views: number | null; likes?: number | null; comments?: number | null; minutes_watched?: number | null; avg_view_pct?: number | null; avg_view_s?: number | null; subs_gained?: number | null; subs_per_1000?: number | null;
  history?: Hist; retention?: [number, number | null][]; compare?: { same_kind_videos: number; views_rank: number | null; median_views: number | null; views_vs_median: number | null; median_avg_view_pct: number | null };
  findings?: Finding[]; recommendations?: RecLite[]; comments_waiting?: Comment[]; comments_total?: number };
type Data = { empty: boolean; posts?: Post[]; totals?: Record<string, number>; unlinked?: { media_id: string; caption: string; account: string }[];
  youtube?: { videos?: Video[]; unlinked?: { video_id: string; title: string; published_at?: string }[]; totals?: Record<string, number> } };

const n = (v: number | null | undefined) => (v == null ? "n/a" : v.toLocaleString(undefined, { maximumFractionDigits: 1 }));
const pc = (v: number | null | undefined) => (v == null ? "n/a" : `${n(v)}%`);
const day = (s?: string) => (s ? s.slice(0, 10) : "");
const mins = (m: number | null | undefined) => (m == null ? "n/a" : m >= 600 ? `${(m / 60).toFixed(1)} h` : `${Math.round(m)} min`);
const vsChip = (v: number | null | undefined) => (v == null ? "" : v >= 1.2 ? "ok" : v < 0.8 ? "bad" : "wn");

function Line({ pts, label }: { pts: [number, number][]; label: string }) {
  const W = 520, H = 90, xs = pts.map((p) => p[0]), x0 = Math.min(...xs), span = Math.max(...xs) - x0 || 1, lo = Math.min(...pts.map((p) => p[1])), hi = Math.max(...pts.map((p) => p[1])), h = hi - lo || 1;
  const d = pts.map((p, i) => `${i ? "L" : "M"}${(((p[0] - x0) / span) * W).toFixed(1)},${(H - 4 - ((p[1] - lo) / h) * (H - 8)).toFixed(1)}`).join(" ");
  return <svg role="img" aria-label={label} viewBox={`0 0 ${W} ${H}`} width="100%" height={H} preserveAspectRatio="none" style={{ maxWidth: W }}><path d={d} fill="none" stroke="var(--ac)" strokeWidth={2} /></svg>;
}
const Tile = ({ k, v, sub }: { k: string; v: string; sub?: string }) => <div className="card kpi"><span className="mu">{k}</span><b>{v}</b>{sub && <span className="mu">{sub}</span>}</div>;

function Analysis({ f, r, what }: { f?: Finding[]; r?: RecLite[]; what: string }) {
  if (!f?.length && !r?.length) return null;
  return (<div className="stack" style={{ gap: 6 }}><h4>What the analysis says about this {what}</h4>
    {(f ?? []).map((x, i) => <p key={i}><span className={"chip " + (x.severity === "high" ? "bad" : x.severity === "medium" ? "wn" : "")}>{x.severity}</span> {x.title}{x.detail && <span className="mu"> {x.detail}</span>}</p>)}
    {(r ?? []).map((x) => <p key={x.rec_id}><b>{x.title}</b> <span className="mu">{x.action}</span></p>)}</div>);
}
function Comments({ w, total }: { w: Comment[]; total: number }) {
  if (!w.length) return <p className="mu">{total ? `${total} comment${total === 1 ? "" : "s"}, all answered.` : "No comments yet."}</p>;
  return (<div className="stack" style={{ gap: 4 }}><h4>Comments waiting for a reply ({total} in all)</h4>
    {w.map((c, i) => <p key={i}><b>@{c.username.replace(/^@/, "")}</b> <span className="mu">{day(c.posted_at)}</span><br />{c.text.slice(0, 200)}</p>)}</div>);
}

function PostCard({ p, unlink, busy }: { p: Post; unlink: () => void; busy: boolean }) {
  const c = p.compare; const pts = (p.history ?? []).filter((h) => h.views != null).map((h, i) => [i, h.views as number] as [number, number]);
  return (
    <article className="card stack" aria-label={`Instagram ${(p.product_type || "post").toLowerCase()} on @${p.username || p.account}`}>
      <div className="row" style={{ flexWrap: "wrap" }}><span className="chip">{(p.product_type || "post").toLowerCase()}</span><b>@{p.username || p.account}</b><span className="mu">posted {day(p.posted_at)}{p.captured_at ? ` · numbers from ${day(p.captured_at)}` : ""}</span>
        <span style={{ flex: 1 }} />{p.permalink && <a className="btn g" href={p.permalink} target="_blank" rel="noreferrer">Open on Instagram</a>}<button className="btn g" disabled={busy} onClick={unlink}>Unlink{" "}<span className="sr">this post</span></button></div>
      <p className="mu">{c && c.account_posts > 1 && p.views != null ? <>Ranked <b>#{c.views_rank}</b> of {c.account_posts} posts on this account by views{c.views_vs_median != null && <>, <span className={"chip " + vsChip(c.views_vs_median)}>{c.views_vs_median}×</span> the median of {n(c.median_views)}</>}{c.median_save_rate != null && p.save_rate != null ? `. Save rate ${pc(p.save_rate)} against a median of ${pc(c.median_save_rate)}` : ""}{c.median_avg_watch_s != null && p.avg_watch_s != null ? `. Average watch ${p.avg_watch_s}s against ${c.median_avg_watch_s}s` : ""}.</>
        : p.views == null ? "No numbers yet. Instagram reports with up to 2 days delay, then Collect now on Analytics." : "The only post with numbers on this account, so there is nothing to compare with yet."}</p>
      <div className="kpis"><Tile k="Views" v={n(p.views)} sub={p.avg_watch_s != null ? `${p.avg_watch_s}s average watch` : undefined} /><Tile k="Reach" v={n(p.reach)} /><Tile k="Saves" v={n(p.saved)} sub={p.save_rate != null ? `${pc(p.save_rate)} of reach` : undefined} /><Tile k="Shares" v={n(p.shares)} /><Tile k="Likes" v={n(p.like_count)} /><Tile k="Comments" v={n(p.comments_count)} sub={p.comments_waiting?.length ? `${p.comments_waiting.length} waiting` : undefined} /></div>
      {pts.length > 1 ? <><h4>Views over time ({pts.length} collects)</h4><Line pts={pts} label={`Views of this post over ${pts.length} collects, from ${n(pts[0][1])} to ${n(pts[pts.length - 1][1])}`} /></> : <p className="mu">The trend line appears after two collects.</p>}
      <Analysis f={p.findings} r={p.recommendations} what="post" />
      <Comments w={p.comments_waiting ?? []} total={p.comments_total ?? 0} />
    </article>
  );
}

function VideoCard({ v, unlink, busy }: { v: Video; unlink: () => void; busy: boolean }) {
  const c = v.compare; const kd = v.kind === "short" ? "Short" : "video";
  const pts = (v.history ?? []).filter((h) => h.views != null).map((h, i) => [i, h.views as number] as [number, number]);
  const rp = (v.retention ?? []).filter((r): r is [number, number] => r[1] != null);
  const at10 = rp.length ? rp.reduce((a, b) => (Math.abs(b[0] - 0.1) < Math.abs(a[0] - 0.1) ? b : a)) : null;
  return (
    <article className="card stack" aria-label={`YouTube ${kd}: ${v.title}`}>
      <div className="row" style={{ flexWrap: "wrap" }}><span className="chip">{kd}</span>{v.privacy && v.privacy !== "public" && <span className="chip wn">{v.privacy}</span>}<b>{v.title || v.channel || v.account}</b><span className="mu">published {day(v.published_at)}{v.captured_at ? ` · numbers from ${day(v.captured_at)}` : ""}</span>
        <span style={{ flex: 1 }} /><a className="btn g" href={v.url} target="_blank" rel="noreferrer">Open on YouTube</a>{v.privacy === "private" && <a className="btn g" href={`https://studio.youtube.com/video/${v.video_id}/edit`} target="_blank" rel="noreferrer">Open in YouTube Studio</a>}<button className="btn g" disabled={busy} onClick={unlink}>Unlink{" "}<span className="sr">this video</span></button></div>
      <p className="mu">{c && c.same_kind_videos > 1 && v.views != null ? <>Ranked <b>#{c.views_rank}</b> of {c.same_kind_videos} {kd}s on this channel by views{c.views_vs_median != null && <>, <span className={"chip " + vsChip(c.views_vs_median)}>{c.views_vs_median}×</span> the median of {n(c.median_views)}</>}{c.median_avg_view_pct != null && v.avg_view_pct != null ? `. Viewers watched ${pc(v.avg_view_pct)} on average against a median of ${pc(c.median_avg_view_pct)}` : ""}.</>
        : v.views == null ? "No numbers yet. On Analytics, switch to YouTube and press Collect now." : `The only ${kd} with numbers on this channel, so there is nothing to compare with yet.`}</p>
      <div className="kpis"><Tile k="Views" v={n(v.views)} sub={v.avg_view_s != null ? `${Math.round(v.avg_view_s)}s average view` : undefined} /><Tile k="Watch time" v={mins(v.minutes_watched)} sub={v.avg_view_pct != null ? `${pc(v.avg_view_pct)} of the ${kd}` : undefined} /><Tile k="Likes" v={n(v.likes)} /><Tile k="Comments" v={n(v.comments)} sub={v.comments_waiting?.length ? `${v.comments_waiting.length} waiting` : undefined} /><Tile k="Subscribers" v={n(v.subs_gained)} sub={v.subs_per_1000 != null ? `${v.subs_per_1000} per 1,000 views` : undefined} /></div>
      {pts.length > 1 ? <><h4>Views over time ({pts.length} collects)</h4><Line pts={pts} label={`Views of this ${kd} over ${pts.length} collects, from ${n(pts[0][1])} to ${n(pts[pts.length - 1][1])}`} /></> : <p className="mu">The trend line appears after two collects.</p>}
      {rp.length > 2 ? <><h4>Audience retention{at10 ? `: ${Math.round(at10[1] * 100)}% still watching at the 10% mark` : ""}</h4><Line pts={rp} label={`Share of viewers still watching, start to end${at10 ? `; ${Math.round(at10[1] * 100)}% at the 10% mark` : ""}`} /></> : <p className="mu">Retention shows once the analytics sign-in is set up and the {kd} has enough views.</p>}
      <Analysis f={v.findings} r={v.recommendations} what={kd} />
      <Comments w={v.comments_waiting ?? []} total={v.comments_total ?? 0} />
    </article>
  );
}

export function SongAnalytics({ slug }: { slug: string }) {
  const [a, setA] = useState<Data | null>(null); const [err, setErr] = useState(""); const [pick, setPick] = useState(""); const [vpick, setVpick] = useState(""); const [busy, setBusy] = useState(false);
  const load = () => getJSON<Data>(`/api/analytics/song?slug=${encodeURIComponent(slug)}`).then(setA).catch((e) => setErr(errText(e)));
  useEffect(() => { void load(); }, [slug]);   // eslint-disable-line react-hooks/exhaustive-deps
  const post = async (path: string, body: Record<string, string>) => { setBusy(true); setErr(""); try { await postJSON(path, body); setPick(""); setVpick(""); await load(); } catch (e) { setErr(errText(e)); } finally { setBusy(false); } };
  if (!a) return err ? <p role="alert" className="mu">{err}</p> : null;
  if (a.empty) return null;   // no analytics database: the Analytics screen says so
  const posts = a.posts ?? []; const vids = a.youtube?.videos ?? []; const un = a.unlinked ?? []; const vun = a.youtube?.unlinked ?? [];
  if (!posts.length && !vids.length && !un.length && !vun.length) return null;
  const T = a.totals ?? {}, YT = a.youtube?.totals ?? {};
  return (
    <section className="sec" aria-labelledby="sa-h">
      <div className="sh"><h2 id="sa-h">How it is doing</h2></div>
      <div className="stack">
        {posts.length > 1 && <p>Instagram, {posts.length} posts together: <b>{n(T.views)}</b> views, <b>{n(T.reach)}</b> reach, <b>{n(T.saved)}</b> saves, <b>{n(T.shares)}</b> shares.</p>}
        {posts.map((p) => <PostCard key={p.media_id} p={p} busy={busy} unlink={() => void post("/api/analytics/link", { media_id: p.media_id, slug: "" })} />)}
        {vids.length > 1 && <p>YouTube, {vids.length} videos together: <b>{n(YT.views)}</b> views{YT.minutes_watched != null ? <>, <b>{mins(YT.minutes_watched)}</b> watched</> : null}.</p>}
        {vids.map((v) => <VideoCard key={v.video_id} v={v} busy={busy} unlink={() => void post("/api/analytics/link-video", { video_id: v.video_id, slug: "" })} />)}
        {!posts.length && un.length > 0 && (
          <div className="card stack">
            <p className="mu">No Instagram post is linked to this item yet. Pick yours:</p>
            <label htmlFor="sa-pick" className="sr">Post to link</label>
            <select id="sa-pick" className="field" value={pick} onChange={(e) => setPick(e.target.value)}><option value="">Choose a post…</option>{un.map((u) => <option key={u.media_id} value={u.media_id}>{u.caption || u.media_id} · {u.account}</option>)}</select>
            <button className="btn" disabled={!pick || busy} onClick={() => void post("/api/analytics/link", { media_id: pick, slug })}>Link this post</button>
          </div>
        )}
        {!vids.length && vun.length > 0 && (
          <div className="card stack">
            <p className="mu">No YouTube video is linked to this item yet. Pick yours:</p>
            <label htmlFor="sa-vpick" className="sr">Video to link</label>
            <select id="sa-vpick" className="field" value={vpick} onChange={(e) => setVpick(e.target.value)}><option value="">Choose a video…</option>{vun.map((u) => <option key={u.video_id} value={u.video_id}>{u.title || u.video_id}{u.published_at ? ` · ${day(u.published_at)}` : ""}</option>)}</select>
            <button className="btn" disabled={!vpick || busy} onClick={() => void post("/api/analytics/link-video", { video_id: vpick, slug })}>Link this video</button>
          </div>
        )}
        {err && <p role="alert" className="mu">{err}</p>}
      </div>
    </section>
  );
}

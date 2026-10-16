import { useEffect, useState } from "react";
import { getJSON, postJSON, type SongAnalytics as SA } from "../lib/api";
import { errText } from "../lib/songs";

const n = (v: number | null | undefined) => (v == null ? "n/a" : v.toLocaleString());

// One song's numbers across Instagram and YouTube, from the same data as the Analytics screen.
export function SongAnalytics({ slug }: { slug: string }) {
  const [a, setA] = useState<SA | null>(null); const [err, setErr] = useState(""); const [pick, setPick] = useState("");
  const load = () => getJSON<SA>(`/api/analytics/song?slug=${encodeURIComponent(slug)}`).then(setA).catch((e) => setErr(errText(e)));
  useEffect(() => { void load(); }, [slug]);   // eslint-disable-line react-hooks/exhaustive-deps
  const link = async () => { setErr(""); try { await postJSON("/api/analytics/link", { media_id: pick, slug }); setPick(""); await load(); } catch (e) { setErr(errText(e)); } };
  if (!a) return err ? <p role="alert" className="mu">{err}</p> : null;
  if (a.empty) return null;   // no analytics database: the Analytics screen says so
  const posts = a.posts ?? []; const yt = a.youtube?.videos ?? []; const un = a.unlinked ?? [];
  if (!posts.length && !yt.length && !un.length) return null;
  return (
    <section className="sec" aria-labelledby="sa-h">
      <div className="sh"><h2 id="sa-h">How it is doing</h2></div>
      <div className="card stack">
        {posts.length > 0 && <p>Instagram: <b>{n(a.totals?.views)}</b> views, <b>{n(a.totals?.reach)}</b> reach, <b>{n(a.totals?.saved)}</b> saves, <b>{n(a.totals?.shares)}</b> shares across {posts.length} post{posts.length === 1 ? "" : "s"}.</p>}
        {posts.map((p) => <p key={p.media_id} className="mu"><a href={p.permalink} target="_blank" rel="noreferrer">{p.product_type || "post"} on {p.account}</a>: {n(p.views)} views{p.compare?.views_vs_median != null ? `, ${p.compare.views_vs_median}× the account's median (rank ${p.compare.views_rank} of ${p.compare.account_posts})` : ""}, {p.comments_total} comments.</p>)}
        {yt.length > 0 && <p>YouTube: {yt.map((v) => <span key={v.video_id}><a href={v.url} target="_blank" rel="noreferrer">{v.title || v.video_id}</a> {n(v.views)} views. </span>)}</p>}
        {!posts.length && un.length > 0 && (
          <div className="stack">
            <p className="mu">No Instagram post is linked to this song yet. Pick yours:</p>
            <label htmlFor="sa-pick" className="sr">Post to link</label>
            <select id="sa-pick" className="field" value={pick} onChange={(e) => setPick(e.target.value)}><option value="">Choose a post…</option>{un.map((u) => <option key={u.media_id} value={u.media_id}>{u.caption || u.media_id} · {u.account}</option>)}</select>
            <button className="btn" disabled={!pick} onClick={() => void link()}>Link this post</button>
          </div>
        )}
        {err && <p role="alert" className="mu">{err}</p>}
      </div>
    </section>
  );
}

import type { Overview } from "../../lib/api";
import { Spark } from "./Charts";

const KPI: Record<"instagram" | "youtube", [string, string, string?][]> = {
  instagram: [["followers", "Followers", "followers_change"], ["views", "Views"], ["interactions", "Interactions"], ["accounts_engaged", "Accounts engaged"], ["waiting", "Comments waiting"]],
  youtube: [["subscribers", "Subscribers", "subscribers_change"], ["views", "Views"], ["watch_hours", "Watch hours"], ["subs_gained", "Subscribers gained"], ["waiting", "Comments waiting"]],
};
const n = (v: number | null | undefined) => (v == null ? "n/a" : Number.isInteger(v) ? v.toLocaleString() : v.toLocaleString(undefined, { maximumFractionDigits: 1 }));
const day = (s: string) => (s ? new Date(s).toLocaleDateString([], { day: "numeric", month: "short" }) : "");

export default function Numbers({ d, platform }: { d: Overview; platform: "instagram" | "youtube" }) {
  const run = d.runs[0];
  return (
    <>
      <div className="kpis">
        {KPI[platform].map(([k, label, ch]) => (
          <div className="card kpi" key={k}><span className="mu">{label}</span><b>{n(d.kpis[k])}</b>{ch && d.kpis[ch] != null && <span className={"chip " + ((d.kpis[ch] as number) >= 0 ? "ok" : "bad")}>{(d.kpis[ch] as number) >= 0 ? "+" : ""}{n(d.kpis[ch])}</span>}</div>
        ))}
      </div>
      <div className="grid">{Object.entries(d.series).map(([k, pts]) => <Spark key={k} label={k.replace(/_/g, " ")} points={pts} />)}</div>
      <section className="sec" aria-labelledby="top-h">
        <div className="sh"><h2 id="top-h">{platform === "youtube" ? "Videos" : "Posts"}</h2><span className="n">{(d.posts ?? d.videos ?? []).length}</span></div>
        <div className="card" style={{ padding: 8 }}>
          {platform === "instagram" ? (
            <table className="rt"><thead><tr><th>Post</th><th>Posted</th><th>Views</th><th>Reach</th><th>Saves</th><th>Shares</th><th>Engagement</th></tr></thead>
              <tbody>{(d.posts ?? []).map((p) => (
                <tr key={p.media_id}><td data-label="Post"><a href={p.permalink} target="_blank" rel="noreferrer">{p.title || p.slug || p.media_id}</a></td><td data-label="Posted">{day(p.posted_at)}</td><td data-label="Views">{n(p.views)}</td><td data-label="Reach">{n(p.reach)}</td><td data-label="Saves">{n(p.saved)}</td><td data-label="Shares">{n(p.shares)}</td><td data-label="Engagement">{p.engagement_rate == null ? "n/a" : `${n(p.engagement_rate)}%`}</td></tr>
              ))}</tbody></table>
          ) : (
            <table className="rt"><thead><tr><th>Video</th><th>Kind</th><th>Published</th><th>Views</th><th>Likes</th><th>Comments</th><th>Avg view</th></tr></thead>
              <tbody>{(d.videos ?? []).map((v) => (
                <tr key={v.video_id}><td data-label="Video"><a href={v.url} target="_blank" rel="noreferrer">{v.title || v.video_id}</a></td><td data-label="Kind">{v.kind}</td><td data-label="Published">{day(v.published_at)}</td><td data-label="Views">{n(v.views)}</td><td data-label="Likes">{n(v.likes)}</td><td data-label="Comments">{n(v.comments)}</td><td data-label="Avg view">{v.avg_view_s == null ? "n/a" : `${n(v.avg_view_s)} s`}</td></tr>
              ))}</tbody></table>
          )}
          {!(d.posts ?? d.videos ?? []).length && <p className="empty">Nothing collected for this period.</p>}
        </div>
      </section>
      {run && <p className="mu">Last collection {day(run.started_at)}: {run.status}{run.errors ? `, ${run.errors} error${run.errors === 1 ? "" : "s"}${run.first_error ? ` (${run.first_error})` : ""}` : ""}.</p>}
    </>
  );
}

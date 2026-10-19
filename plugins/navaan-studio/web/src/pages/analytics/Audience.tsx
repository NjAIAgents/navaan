import type { Overview } from "../../lib/api";

// Who the audience is and what works (NAV-29 parity with the classic Analytics page): bar lists, the Instagram online hours, YouTube retention.
const nf = (v: number | null | undefined) => (v == null ? "-" : v.toLocaleString(undefined, { maximumFractionDigits: 1 }));

export function BarList({ rows, fmt, label }: { rows: [string, number][]; fmt?: (r: [string, number]) => string; label: string }) {
  if (!rows.length) return <p className="mu">No data yet.</p>;
  const mx = Math.max(...rows.map((r) => r[1])) || 1;
  return (
    <ul className="barlist" aria-label={label}>
      {rows.map((r) => (
        <li key={r[0]}><span className="bl-k">{r[0]}</span><span className="bl-t" aria-hidden="true"><i style={{ width: `${Math.max(3, (100 * r[1]) / mx)}%` }} /></span><b>{fmt ? fmt(r) : nf(r[1])}</b></li>
      ))}
    </ul>
  );
}

const Col = ({ title, children }: { title: string; children: React.ReactNode }) => <div className="stack" style={{ gap: 6 }}><h3 className="mu" style={{ fontSize: 13 }}>{title}</h3>{children}</div>;

export function IgAudience({ d }: { d: Overview }) {
  const A = d.audience ?? {}; const hrs = d.hours ?? []; const mx = Math.max(1, ...hrs.map((h) => h[1]));
  return (
    <section className="sec" aria-labelledby="au-h">
      <div className="sh"><h2 id="au-h">Audience</h2></div>
      <div className="card stack">
        {Object.keys(A).length ? (
          <div className="grid">
            <Col title="Top cities"><BarList label="Top cities" rows={(A.city ?? []).slice(0, 6)} /></Col>
            <Col title="Top countries"><BarList label="Top countries" rows={(A.country ?? []).slice(0, 6)} /></Col>
            <Col title="Age"><BarList label="Age" rows={(A.age ?? []).slice(0, 6)} /><h3 className="mu" style={{ fontSize: 13 }}>Gender</h3><BarList label="Gender" rows={(A.gender ?? []).slice(0, 4)} /></Col>
          </div>
        ) : <p className="mu">Instagram shares audience data once the account has 100 followers.</p>}
        {hrs.length > 0 && <>
          <h3 className="mu" style={{ fontSize: 13 }}>When followers are online (hour of the day, UTC)</h3>
          <div role="img" aria-label={`Followers online by hour, UTC. Most at ${[...hrs].sort((a, b) => b[1] - a[1]).slice(0, 3).map((h) => `${h[0]}:00`).join(", ")}`} style={{ display: "flex", gap: 2, alignItems: "flex-end", height: 60 }}>
            {hrs.map((h) => <div key={h[0]} title={`${h[0]}:00 UTC, ${h[1]} followers`} style={{ flex: 1, height: `${Math.max(4, (100 * h[1]) / mx)}%`, background: "var(--ac)", opacity: 0.8, borderRadius: 2 }} />)}
          </div>
          <div className="mu row" aria-hidden="true" style={{ justifyContent: "space-between", fontSize: 12 }}><span>0</span><span>12</span><span>23</span></div>
        </>}
      </div>
    </section>
  );
}

const SRC = (s: string) => String(s || "").replace(/^YT_/, "").replace(/_/g, " ").toLowerCase();

export function YtViewers({ d }: { d: Overview }) {
  const tr = d.traffic ?? []; const tot = tr.reduce((a, r) => a + (r.views || 0), 0); const A = d.audience ?? {};
  return (
    <section className="sec" aria-labelledby="vw-h">
      <div className="sh"><h2 id="vw-h">Where viewers come from and who they are</h2></div>
      <div className="card">
        {tr.length || Object.keys(A).length ? (
          <div className="grid">
            <Col title="Traffic sources (views)"><BarList label="Traffic sources" rows={tr.slice(0, 8).map((r) => [SRC(r.source), r.views || 0])} fmt={(r) => `${nf(r[1])}${tot ? ` · ${Math.round((100 * r[1]) / tot)}%` : ""}`} /></Col>
            <Col title="Top countries (views)"><BarList label="Top countries" rows={(A.country ?? []).slice(0, 6)} /></Col>
            <Col title="Age (% of viewers)"><BarList label="Age" rows={(A.age ?? []).slice(0, 6).map((r) => [String(r[0]).replace(/^age/, ""), r[1]])} fmt={(r) => `${Number(r[1]).toFixed(1)}%`} />
              <h3 className="mu" style={{ fontSize: 13 }}>Gender</h3><BarList label="Gender" rows={(A.gender ?? []).slice(0, 3)} fmt={(r) => `${Number(r[1]).toFixed(1)}%`} /></Col>
          </div>
        ) : <p className="mu">Traffic sources and audience come from the YouTube Analytics API. They appear after the analytics sign-in and the next collect.</p>}
      </div>
    </section>
  );
}

function Line({ pts, label }: { pts: [number, number][]; label: string }) {
  if (pts.length < 2) return <p className="mu">Not enough points yet.</p>;
  const W = 260, H = 80, xs = pts.map((p) => p[0]), x0 = Math.min(...xs), x1 = Math.max(...xs) || 1, top = Math.max(1, ...pts.map((p) => p[1]));
  const path = pts.map((p, i) => `${i ? "L" : "M"}${(((p[0] - x0) / (x1 - x0 || 1)) * W).toFixed(1)},${(H - (p[1] / top) * (H - 4)).toFixed(1)}`).join(" ");
  return <svg role="img" aria-label={label} viewBox={`0 0 ${W} ${H}`} width="100%" height={H} preserveAspectRatio="none"><path d={path} fill="none" stroke="var(--ok)" strokeWidth={2} /></svg>;
}

export function Retention({ d }: { d: Overview }) {
  const R = d.retention ?? [];
  return (
    <section className="sec" aria-labelledby="rt-h">
      <div className="sh"><h2 id="rt-h">Audience retention</h2></div>
      <div className="card stack">
        {R.length ? <>
          <div className="grid">{R.map((r) => {
            const pts = r.points.filter((p): p is [number, number] => p[1] != null);
            const end = pts.length ? pts[pts.length - 1][1] : null;
            return <div key={r.name} className="stack" style={{ gap: 4 }}><b>{r.name} <span className="chip">{r.kind === "short" ? "Short" : "video"}</span></b><Line pts={pts} label={`${r.name}: share still watching from start to end${end != null ? `, ${Math.round(end * 100)}% at the end` : ""}`} /><div className="mu row" aria-hidden="true" style={{ justifyContent: "space-between", fontSize: 12 }}><span>start</span><span>end</span></div></div>;
          })}</div>
          <p className="mu">Share of viewers still watching at each point. A steep fall at the very start means the opening loses people.</p>
        </> : <p className="mu">Retention curves appear for your top videos once the analytics sign-in is set up and a video has enough views.</p>}
      </div>
    </section>
  );
}

export function Patterns({ d, platform }: { d: Overview; platform: string }) {
  const P = d.patterns ?? {}; const yt = platform === "youtube";
  const n = yt ? (d.videos ?? []).filter((v) => v.views != null).length : (d.posts ?? []).filter((p) => p.views != null).length;
  const rows = (k: string) => (P[k] ?? []).map((r) => [`${k === "kind" ? (r.name === "short" ? "Shorts" : "videos") : r.name} (${(yt ? r.videos : r.posts) ?? 0})`, r.avg_views ?? 0] as [string, number]);
  const pct = (P.kind ?? []).filter((r) => r.avg_view_pct != null).map((r) => `${r.name === "short" ? "Shorts" : "videos"} ${Math.round(Number(r.avg_view_pct))}%`).join(", ");
  return (
    <section className="sec" aria-labelledby="pt-h">
      <div className="sh"><h2 id="pt-h">What seems to work</h2></div>
      <div className="card stack">
        {n < 3 ? <p className="mu">Patterns appear once at least 3 {yt ? "videos" : "posts"} have numbers. Right now {n} {n === 1 ? "does" : "do"}. Each collect adds a snapshot, so the picture builds over time.</p> : <>
          <div className="grid">
            {yt && <Col title="By kind: average views"><BarList label="Average views by kind" rows={rows("kind")} /></Col>}
            <Col title="By language: average views"><BarList label="Average views by language" rows={rows("language")} /></Col>
            <Col title="By genre: average views"><BarList label="Average views by genre" rows={rows("genre")} /></Col>
          </div>
          {pct && <p className="mu">Average share of the video watched: {pct}.</p>}
          <p className="mu">Early signal from {n} {yt ? "videos" : "posts"}. Treat it as a hint until each group has several.</p>
        </>}
      </div>
    </section>
  );
}

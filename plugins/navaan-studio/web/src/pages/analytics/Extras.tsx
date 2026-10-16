import { useEffect, useState } from "react";
import { getJSON, postJSON, type AutoSettings, type Overview, type Peer } from "../../lib/api";
import { errText } from "../../lib/songs";

const nf = (v: number | null | undefined) => (v == null ? "-" : v.toLocaleString(undefined, { maximumFractionDigits: 1 }));

// Collect, analyse and ask only run when pressed: they use the platform APIs and the agent's usage.
export function Actions({ d, platform, account, reload }: { d: Overview; platform: string; account: string; reload: () => Promise<unknown> | void }) {
  const [err, setErr] = useState(""); const [msg, setMsg] = useState(""); const [busy, setBusy] = useState(false);
  const running = !!d.collect?.running;
  useEffect(() => { if (!running) return; const t = setInterval(() => void reload(), 4000); return () => clearInterval(t); }, [running, reload]);
  const run = async (what: string, path: string, body: Record<string, unknown>, done: string) => {
    setBusy(true); setErr(""); setMsg("");
    try { await postJSON(path, { account, platform, ...body }); setMsg(done); await reload(); } catch (e) { setErr(`${what}: ${errText(e)}`); } finally { setBusy(false); }
  };
  return (
    <section className="card stack" aria-labelledby="an-act">
      <h2 id="an-act">Refresh</h2>
      <p className="mu">Nothing here runs by itself unless Auto refresh is on. Collect reads the platform; analysis and Ask use the agent's usage.</p>
      <div className="row" style={{ flexWrap: "wrap" }}>
        <button className="btn p" disabled={busy || running} onClick={() => void run("Collect", "/api/analytics/collect", {}, "Collecting started. It takes a few minutes.")}>{running ? "Collecting…" : "Collect now"}</button>
        <button className="btn" disabled={busy || running} onClick={() => void run("Analysis", "/api/analytics/analyze", {}, "Analysis finished.")}>Re-run analysis</button>
        <button className="btn" disabled={busy || running} onClick={() => void run("Ask", "/api/analytics/ask", {}, "Asked. The answer appears in Recommendations.")}>Ask for advice</button>
      </div>
      {running && <p className="mu" role="status">Collecting {d.collect.account ?? ""}…</p>}
      {!running && d.collect?.rc != null && d.collect.rc !== 0 && <p role="alert" className="mu">The last collection failed ({d.collect.tail?.split("\n").pop()}).</p>}
      {msg && <p className="mu" role="status">{msg}</p>}
      {err && <p role="alert" className="mu">{err}</p>}
    </section>
  );
}

export function Auto() {
  const [a, setA] = useState<AutoSettings | null>(null); const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  const [v, setV] = useState<{ enabled: boolean; every_days: number; hour: number; ask: boolean } | null>(null);
  const load = () => getJSON<AutoSettings>("/api/analytics/auto").then((x) => { setA(x); setV({ enabled: x.enabled, every_days: x.every_days, hour: x.hour, ask: x.ask }); }).catch((e) => setErr(errText(e)));
  useEffect(() => { void load(); }, []);
  useEffect(() => { if (!a?.running) return; const t = setInterval(() => void load(), 4000); return () => clearInterval(t); }, [a?.running]);
  const act = async (f: () => Promise<unknown>) => { setBusy(true); setErr(""); try { await f(); await load(); } catch (e) { setErr(errText(e)); } finally { setBusy(false); } };
  if (!a || !v || !Array.isArray(a.choices)) return err ? <p role="alert" className="mu">{err}</p> : null;
  return (
    <section className="card stack" aria-labelledby="au-h">
      <h2 id="au-h">Auto refresh</h2>
      <label className="row"><input type="checkbox" role="switch" checked={v.enabled} onChange={(e) => setV({ ...v, enabled: e.target.checked })} /> Collect and analyse on a schedule</label>
      <div className="row" style={{ flexWrap: "wrap" }}>
        <label htmlFor="au-days">Every</label>
        <select id="au-days" className="field sel" value={v.every_days} onChange={(e) => setV({ ...v, every_days: Number(e.target.value) })}>{a.choices.map((c) => <option key={c} value={c}>{c} day{c === 1 ? "" : "s"}</option>)}</select>
        <label htmlFor="au-hour">At hour (0 to 23)</label>
        <input id="au-hour" className="field sel" type="number" min={0} max={23} value={v.hour} onChange={(e) => setV({ ...v, hour: Number(e.target.value) })} />
      </div>
      <label className="row"><input type="checkbox" checked={v.ask} onChange={(e) => setV({ ...v, ask: e.target.checked })} /> Also ask the agent for advice (uses agent usage)</label>
      <p className="mu">{a.last_run ? `Last run ${new Date(a.last_run).toLocaleString()}${a.last_note ? `: ${a.last_note}` : ""}. ` : "Never run. "}{a.next_run ? `Next ${new Date(a.next_run).toLocaleString()}.` : ""}{a.running ? ` Running: ${a.step ?? ""}` : ""}</p>
      <div className="row"><button className="btn p" disabled={busy} onClick={() => void act(() => postJSON("/api/analytics/auto", v))}>Save</button><button className="btn" disabled={busy || a.running} onClick={() => void act(() => postJSON("/api/analytics/auto/run", {}))}>Refresh now</button></div>
      {err && <p role="alert" className="mu">{err}</p>}
    </section>
  );
}

const PeerRow = ({ r, me }: { r: Peer; me: boolean }) => (
  <tr>
    <td data-label="Account"><a href={`https://www.instagram.com/${r.username}/`} target="_blank" rel="noreferrer">@{r.username}</a>{me && <span className="chip"> you</span>}<div className="mu">{me ? r.label : r.note}{r.error ? ` · ${r.error.slice(0, 60)}` : ""}</div></td>
    <td data-label="Followers">{nf(r.followers)}</td><td data-label="Posts / wk">{nf(r.posts_per_week)}</td><td data-label="Median likes">{nf(r.median_likes)}</td><td data-label="Median comments">{nf(r.median_comments)}</td><td data-label="Eng / 1k"><b>{nf(r.eng_per_1k)}</b></td><td data-label="Reels">{r.reel_share == null ? "-" : `${r.reel_share}%`}</td>
    <td data-label="Tags">{(r.top_tags ?? []).slice(0, 4).map((t) => <span key={t} className="chip">#{t}</span>)}</td><td data-label="Best post">{r.best?.permalink ? <a href={r.best.permalink} target="_blank" rel="noreferrer">{nf(r.best.likes)} likes</a> : "-"}</td>
  </tr>
);

export function Peers({ d }: { d: Overview }) {
  const rows = d.peers?.rows ?? []; const own = d.peers?.own ?? [];
  return (
    <section className="sec" aria-labelledby="pe-h">
      <div className="sh"><h2 id="pe-h">Peers</h2><span className="n">{rows.length}</span></div>
      <div className="card" style={{ padding: 8 }}>
        {rows.length ? (
          <table className="rt"><thead><tr><th>Account</th><th>Followers</th><th>Posts / wk</th><th>Median likes</th><th>Median comments</th><th>Eng / 1k</th><th>Reels</th><th>Tags they use</th><th>Best post</th></tr></thead>
            <tbody>{own.map((r) => <PeerRow key={`o${r.username}`} r={r} me />)}{rows.map((r) => <PeerRow key={r.username} r={r} me={false} />)}</tbody></table>
        ) : <p className="empty">No peers yet. Add some with <code>ig_collect.py peers add @name</code>, then Collect now.</p>}
        <p className="mu" style={{ padding: "8px 12px" }}>Engagement is median likes plus comments per 1,000 followers, the one number that is fair across sizes.</p>
      </div>
    </section>
  );
}

export function Hashtags({ d }: { d: Overview }) {
  const h = d.hashtags; if (!h) return null;
  const groups = Object.keys(h.suggested ?? {});
  return (
    <section className="card stack" aria-labelledby="ht-h">
      <h2 id="ht-h">Hashtags to test</h2>
      <p className="mu">Tags on the strongest 40% of each peer's posts ({h.peer_posts_with_tags ?? 0} peer posts carry tags). The number is how many peers use it. Marked "in use" means already in your captions.</p>
      {groups.map((g) => (
        <div key={g} className="stack">
          <h3>{g === "music" ? "For NAVAAN songs" : g === "inspiration" ? "For inspiration" : g}</h3>
          <div className="row" style={{ flexWrap: "wrap" }}>{(h.suggested?.[g] ?? []).map((x) => <span key={x.tag} className={"chip" + (x.in_use ? " ok" : "")} title={x.peers.map((p) => `@${p}`).join(", ")}>#{x.tag} {x.peers.length}{x.in_use ? " (in use)" : ""}</span>)}{!(h.suggested?.[g] ?? []).length && <span className="mu">nothing yet</span>}</div>
          {(h.own?.[g] ?? []).length > 0 && <p className="mu">Your own tags by average views: {(h.own?.[g] ?? []).slice(0, 10).map((x) => `#${x.tag} ${nf(x.avg_views)}`).join(", ")}</p>}
        </div>
      ))}
    </section>
  );
}

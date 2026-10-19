import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getJSON, postJSON } from "../../lib/api";
import { errText } from "../../lib/songs";
import { Loading } from "../../components/Loading";

type K = "positive" | "neutral" | "negative";
type Counts = Record<K, number>;
type Quote = { src: string; text: string; slug: string | null; link: string | null; conf: number | null; at: string };
type Data = { days: number; totals: Counts & { total: number }; daily: (Counts & { day: string })[]; songs: (Counts & { slug: string; total: number })[]; themes: (Counts & { theme: string; n: number })[];
  best: Quote[]; worst: Quote[]; waiting: number; running: boolean; last_run: { started_at: string; finished_at: string | null; scored: number; usd: number; error: string | null } | null };

const KINDS: K[] = ["positive", "neutral", "negative"];
const COLOR: Record<K, string> = { positive: "var(--ok)", neutral: "var(--mu)", negative: "var(--bad)" };
const SRC: Record<string, string> = { instagram: "Instagram", youtube: "YouTube", site: "the site" };
const pct = (n: number, t: number) => (t ? Math.round((100 * n) / t) : 0);

function Bar({ c, total, label }: { c: Counts; total: number; label: string }) {
  return (
    <div role="img" aria-label={`${label}: ${KINDS.map((k) => `${pct(c[k], total)}% ${k}`).join(", ")}`} style={{ display: "flex", height: 14, borderRadius: 7, overflow: "hidden", background: "var(--s2)" }}>
      {KINDS.map((k) => <span key={k} style={{ width: `${pct(c[k], total)}%`, background: COLOR[k] }} />)}
    </div>
  );
}

// How the audience feels (NAV-68): comments on YouTube and Instagram and messages from the public site, scored by Claude, each once.
export default function Sentiment({ days }: { days: string }) {
  const [d, setD] = useState<Data | null>(null); const [err, setErr] = useState(""); const [msg, setMsg] = useState("");
  const load = useCallback(() => getJSON<Data>(`/api/analytics/sentiment?days=${days}`).then((x) => { setD(x); setErr(""); }).catch((e) => setErr(errText(e))), [days]);
  useEffect(() => { setD(null); void load(); }, [load]);
  useEffect(() => { if (!d?.running) return; const t = setInterval(() => void load(), 5000); return () => clearInterval(t); }, [d?.running, load]);
  const score = async () => { setMsg(""); try { await postJSON("/api/analytics/sentiment/run", {}); setMsg("Scoring started. It runs in the background; this page updates when it is done."); void load(); } catch (e) { setErr(errText(e)); } };
  if (err) return <div className="card" role="alert"><h2>Could not load sentiment</h2><p className="mu">{err}</p></div>;
  if (!d) return <Loading />;
  const t = d.totals;
  const quotes = (q: Quote[], title: string, id: string) => (
    <section className="sec" aria-labelledby={id}>
      <div className="sh"><h2 id={id}>{title}</h2></div>
      <div className="card stack">{q.length ? q.map((x, i) => (
        <blockquote key={i} style={{ margin: 0 }}><p>“{x.text}”</p>
          <p className="mu">on {SRC[x.src] ?? x.src}{x.slug ? <> · <Link to={`/studio/songs/${x.slug}`}>{x.slug}</Link></> : null}{x.link ? <> · <a href={x.link} target="_blank" rel="noreferrer">open the post</a></> : null}</p></blockquote>
      )) : <p className="empty">None yet.</p>}</div>
    </section>
  );
  return (
    <>
      <section className="sec" aria-labelledby="se-h">
        <div className="sh"><h2 id="se-h">How the audience feels, last {d.days} days</h2></div>
        <div className="card stack">
          {t.total ? <><Bar c={t} total={t.total} label="All comments" />
            <p>{t.total} comment{t.total === 1 ? "" : "s"}: <strong>{pct(t.positive, t.total)}% positive</strong>, {pct(t.neutral, t.total)}% neutral, {pct(t.negative, t.total)}% negative.</p></> : <p className="empty">No comments scored yet.</p>}
          <div className="row" style={{ flexWrap: "wrap" }}>
            <button className="btn p" disabled={d.running || !d.waiting} aria-busy={d.running} onClick={() => void score()}>{d.running ? "Scoring…" : `Score new comments (${d.waiting} waiting)`}</button>
            {d.last_run && <span className="mu">Last run {new Date(d.last_run.started_at).toLocaleString()}: {d.last_run.scored} scored, about ${d.last_run.usd.toFixed(2)} of Claude use{d.last_run.error ? `. It stopped: ${d.last_run.error}` : ""}.</span>}
          </div>
          {msg && <p role="status" className="mu">{msg}</p>}
          <p className="mu">Claude reads each comment once (up to 200 a run) and the automatic refresh does the same. Your own replies are not scored.</p>
        </div>
      </section>
      {d.daily.length > 1 && (
        <section className="sec" aria-labelledby="sd-h">
          <div className="sh"><h2 id="sd-h">Over time</h2></div>
          <div className="card stack" style={{ gap: 6 }}>{d.daily.map((x) => { const n = x.positive + x.neutral + x.negative; return (
            <div key={x.day} className="row" style={{ gap: 10 }}><span className="mu" style={{ width: 90 }}>{x.day}</span><div style={{ flex: 1 }}><Bar c={x} total={n} label={x.day} /></div><span className="mu" style={{ width: 40, textAlign: "right" }}>{n}</span></div>); })}</div>
        </section>
      )}
      <section className="sec" aria-labelledby="ss-h">
        <div className="sh"><h2 id="ss-h">Per song or short</h2></div>
        <div className="card" style={{ padding: 8 }}>{d.songs.length
          ? <table className="rt"><thead><tr><th>Song</th><th>Positive</th><th>Neutral</th><th>Negative</th><th>Comments</th></tr></thead>
              <tbody>{d.songs.map((r) => <tr key={r.slug}><td data-label="Song"><Link to={`/studio/songs/${r.slug}`}>{r.slug}</Link></td><td data-label="Positive">{r.positive}</td><td data-label="Neutral">{r.neutral}</td><td data-label="Negative">{r.negative}</td><td data-label="Comments">{r.total}</td></tr>)}</tbody></table>
          : <p className="empty">No scored comments on a song yet.</p>}</div>
      </section>
      <section className="sec" aria-labelledby="st-h">
        <div className="sh"><h2 id="st-h">What they keep saying</h2></div>
        <div className="card row" style={{ flexWrap: "wrap", gap: 8 }}>{d.themes.length ? d.themes.map((x) => <span key={x.theme} className="chip" title={`${x.positive} positive, ${x.neutral} neutral, ${x.negative} negative`}>{x.theme} {x.n}</span>) : <p className="empty">No themes yet.</p>}</div>
      </section>
      {quotes(d.best, "Most positive", "sb-h")}
      {quotes(d.worst, "Most negative", "sw-h")}
    </>
  );
}

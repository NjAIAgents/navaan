import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { postJSON, type Overview, type Rec } from "../../lib/api";
import { errText } from "../../lib/songs";

type Which = "open" | "done" | "dismissed";
const LABEL: Record<Which, string> = { open: "Open", done: "Done", dismissed: "Dismissed" };
const SEV: Record<string, string> = { high: "bad", medium: "wn", low: "", info: "" };

const CONF: Record<string, number> = { high: 0, medium: 1, low: 2 };
const chg = (l: string, v?: number | null) => (v == null ? "" : `${l} ${v > 0 ? "+" : ""}${v}%`);

// What happened after a recommendation was marked done: better, worse or flat, measured on the posts since.
function Outcome({ r }: { r: Rec }) {
  const o = r.outcome; const when = r.done_at ? new Date(r.done_at).toLocaleDateString([], { day: "numeric", month: "short" }) : "";
  if (!o) return <p className="mu">Marked done{when ? ` ${when}` : ""}. Results show after the next collect.</p>;
  const parts = [chg("median views", o.change_pct?.median_views), chg("median share watched", o.change_pct?.median_avg_view_pct)].filter(Boolean).join(", ");
  return <p className="mu">Marked done{when ? ` ${when}` : ""}. <span className={"chip " + ({ improved: "ok", worse: "bad", flat: "wn" }[o.verdict] ?? "")}>{o.verdict}</span> {parts}{parts ? ". " : ""}{o.posts_after} post{o.posts_after === 1 ? "" : "s"} since.{o.note ? ` ${o.note}` : ""}</p>;
}

function Card({ r, set, busy, put }: { r: Rec; set: (id: string, status: Which) => void; busy: boolean; put: (id: string) => void }) {
  return (
    <article className="card rec" aria-labelledby={`r-${r.rec_id}`}>
      <div className="row"><span className="chip ac">{r.category}</span><span className="chip">{r.source === "claude" ? "Claude" : "Rule based"}</span><span className="chip">{r.confidence} confidence</span><span className="mu">Priority {r.priority}{r.account ? ` · ${r.account}` : ""}</span></div>
      <h3 id={`r-${r.rec_id}`}>{r.title}</h3>
      <p>{r.why}</p>
      {(r.evidence.length > 0 || !!r.sources?.length) && <><h4>Evidence</h4><ul className="ev">{r.evidence.map((e, i) => <li key={i}><span className={"chip " + (SEV[e.severity] ?? "")}>{e.severity}</span> {e.title}</li>)}
        {(r.sources ?? []).map((x, i) => <li key={`s${i}`}>Market: {x.topic}{x.url && <> · <a href={x.url} target="_blank" rel="noreferrer">{(x.title || x.url).slice(0, 60)}</a></>}</li>)}</ul></>}
      <h4>Action</h4><p>{r.action}</p>
      {r.expected_effect && <p className="mu">Expected: {r.expected_effect}</p>}
      {r.status === "dismissed" && r.dismissed_reason && <p className="mu">Dismissed: {r.dismissed_reason}</p>}
      {r.status === "done" && <Outcome r={r} />}
      <div className="row">
        {r.status === "open" ? <>
          <button className="btn p" disabled={busy} onClick={() => put(r.rec_id)}>Put it to work<span className="sr">: {r.title}</span></button>
          <button className="btn" disabled={busy} onClick={() => set(r.rec_id, "done")}>Done<span className="sr">: {r.title}</span></button>
          <button className="btn" disabled={busy} onClick={() => set(r.rec_id, "dismissed")}>Dismiss<span className="sr">: {r.title}</span></button>
        </> : <button className="btn" disabled={busy} onClick={() => set(r.rec_id, "open")}>Reopen<span className="sr">: {r.title}</span></button>}
      </div>
    </article>
  );
}

export default function Recs({ d, reload }: { d: Overview; reload: () => void }) {
  const [which, setWhich] = useState<Which>("open");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const nav = useNavigate();
  const put = async (id: string) => {   // timing opens the schedule picker; the rest becomes a standing rule the caption, YouTube text and director steps read
    setBusy(true); setErr("");
    try { const r = await postJSON<{ kind?: string; type?: string }>("/api/analytics/implement", { id }); if (r.kind === "schedule") nav(`/studio/schedule?type=${encodeURIComponent(r.type ?? "music")}&open=1`); else reload(); }
    catch (e) { setErr(errText(e)); } finally { setBusy(false); }
  };
  const set = async (id: string, status: Which) => {
    setBusy(true); setErr("");
    try { await postJSON("/api/analytics/rec", { id, status }); reload(); } catch (e) { setErr(errText(e)); } finally { setBusy(false); }
  };
  const list = [...d.reco[which]].sort((a, b) => (CONF[a.confidence?.toLowerCase()] ?? 1) - (CONF[b.confidence?.toLowerCase()] ?? 1));   // the surest first
  const R = d.reco, ask = R.ask ?? {};
  return (
    <>
      <div className="seg" role="group" aria-label="Recommendation status" style={{ alignSelf: "flex-start" }}>
        {(Object.keys(LABEL) as Which[]).map((k) => <button key={k} aria-pressed={which === k} onClick={() => setWhich(k)}>{LABEL[k]} <span className="mu">{d.reco[k].length}</span></button>)}
      </div>
      <p className="mu">{R.ready ? `${R.findings ?? R.open.length} open finding${(R.findings ?? R.open.length) === 1 ? "" : "s"}${R.analyzed_at ? `, analysed ${new Date(R.analyzed_at).toLocaleString([], { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" })}` : ""} · ${R.notes ?? 0} market note${R.notes === 1 ? "" : "s"}. Organic growth only.` : "Not analysed yet."}{ask.running ? " Claude is researching the market now." : ""}</p>
      {!!ask.rc && !ask.running && ask.tail && <div className="card alert" role="alert"><h2>The last Claude run did not finish</h2><pre className="art" tabIndex={0}>{ask.tail}</pre></div>}
      {err && <div className="card" role="alert"><h2>That did not work</h2><p className="mu">{err}</p></div>}
      {!d.reco.ready && <div className="card"><p className="empty">No recommendations yet. They appear after the next analysis.</p></div>}
      {d.reco.ready && !list.length && <div className="card"><p className="empty">Nothing {which === "open" ? "open" : which}.</p></div>}
      {list.map((r) => <Card key={r.rec_id} r={r} set={set} busy={busy} put={put} />)}
    </>
  );
}

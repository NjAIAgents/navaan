import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { postJSON, type Overview, type Rec } from "../../lib/api";
import { errText } from "../../lib/songs";

type Which = "open" | "done" | "dismissed";
const LABEL: Record<Which, string> = { open: "Open", done: "Done", dismissed: "Dismissed" };
const SEV: Record<string, string> = { high: "bad", medium: "wn", low: "", info: "" };

function Card({ r, set, busy, put }: { r: Rec; set: (id: string, status: Which) => void; busy: boolean; put: (id: string) => void }) {
  return (
    <article className="card rec" aria-labelledby={`r-${r.rec_id}`}>
      <div className="row"><span className="chip ac">{r.category}</span><span className="chip">{r.confidence} confidence</span><span className="mu">Priority {r.priority}{r.account ? ` · ${r.account}` : ""}</span></div>
      <h3 id={`r-${r.rec_id}`}>{r.title}</h3>
      <p>{r.why}</p>
      {r.evidence.length > 0 && <><h4>Evidence</h4><ul className="ev">{r.evidence.map((e, i) => <li key={i}><span className={"chip " + (SEV[e.severity] ?? "")}>{e.severity}</span> {e.title}</li>)}</ul></>}
      <h4>Action</h4><p>{r.action}</p>
      {r.expected_effect && <p className="mu">Expected: {r.expected_effect}</p>}
      {r.status === "dismissed" && r.dismissed_reason && <p className="mu">Dismissed: {r.dismissed_reason}</p>}
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
  const list = d.reco[which];
  return (
    <>
      <div className="seg" role="group" aria-label="Recommendation status" style={{ alignSelf: "flex-start" }}>
        {(Object.keys(LABEL) as Which[]).map((k) => <button key={k} aria-pressed={which === k} onClick={() => setWhich(k)}>{LABEL[k]} <span className="mu">{d.reco[k].length}</span></button>)}
      </div>
      {err && <div className="card" role="alert"><h2>That did not work</h2><p className="mu">{err}</p></div>}
      {!d.reco.ready && <div className="card"><p className="empty">No recommendations yet. They appear after the next analysis.</p></div>}
      {d.reco.ready && !list.length && <div className="card"><p className="empty">Nothing {which === "open" ? "open" : which}.</p></div>}
      {list.map((r) => <Card key={r.rec_id} r={r} set={set} busy={busy} put={put} />)}
    </>
  );
}

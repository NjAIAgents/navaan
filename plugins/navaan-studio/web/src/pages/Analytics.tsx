import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { getJSON, type Overview } from "../lib/api";
import { errText } from "../lib/songs";
import Feedback from "./analytics/Feedback";
import Interactions from "./analytics/Interactions";
import Numbers from "./analytics/Numbers";
import Recs from "./analytics/Recs";
import Visitors from "./analytics/Visitors";
import { Actions, Auto, Hashtags, Peers } from "./analytics/Extras";
import { Loading } from "../components/Loading";

const TABS = [["analytics", "Analytics"], ["recommendations", "Recommendations"], ["interactions", "Interactions"], ["feedback", "Feedback"], ["visitors", "Visitors"]] as const;

// Studio > Analytics: numbers, advice and audience replies on their own tabs. The state is in the address, so a view can be linked.
export default function Analytics() {
  const [sp, setSp] = useSearchParams();
  const tab = TABS.some(([k]) => k === sp.get("tab")) ? sp.get("tab")! : "analytics";
  const platform = sp.get("platform") === "youtube" ? "youtube" : "instagram";
  const account = sp.get("account") || "all"; const days = ["7", "30", "90"].includes(sp.get("days") ?? "") ? sp.get("days")! : "30";
  const set = (k: string, v: string) => setSp((p) => { const n = new URLSearchParams(p); n.set(k, v); if (k === "platform") n.set("account", "all"); return n; }, { replace: true });
  const [d, setD] = useState<Overview | null>(null);
  const [err, setErr] = useState("");
  const load = useCallback(() => getJSON<Overview>(`/api/analytics${platform === "youtube" ? "/youtube" : ""}?account=${encodeURIComponent(account)}&days=${days}`).then((x) => { setD(x); setErr(""); }).catch((e) => setErr(errText(e))), [platform, account, days]);
  useEffect(() => { setD(null); void load(); }, [load]);
  return (
    <>
      <div className="ph"><h1 className="disp">Analytics</h1><p>Numbers, advice and what people said.</p></div>
      <div className="row">
        <div className="seg" role="group" aria-label="Platform">{(["instagram", "youtube"] as const).map((p) => <button key={p} aria-pressed={platform === p} onClick={() => set("platform", p)}>{p === "youtube" ? "YouTube" : "Instagram"}</button>)}</div>
        <label className="sr" htmlFor="acc">Account</label>
        <select id="acc" className="field sel" value={account} onChange={(e) => set("account", e.target.value)}><option value="all">All accounts</option>{d?.accounts?.map((a) => <option key={a.label} value={a.label}>{a.label}</option>)}</select>
        <label className="sr" htmlFor="days">Period</label>
        <select id="days" className="field sel" value={days} onChange={(e) => set("days", e.target.value)}>{["7", "30", "90"].map((x) => <option key={x} value={x}>Last {x} days</option>)}</select>
      </div>
      <div className="seg" role="tablist" aria-label="Analytics sections" style={{ alignSelf: "flex-start", flexWrap: "wrap" }}>
        {TABS.map(([k, label]) => <button key={k} role="tab" id={`tab-${k}`} aria-selected={tab === k} aria-controls="panel" tabIndex={tab === k ? 0 : -1} onClick={() => set("tab", k)}>{label}{k === "recommendations" && d?.reco?.open ? <span className="mu"> {d.reco.open.length}</span> : null}</button>)}
      </div>
      <div id="panel" role="tabpanel" aria-labelledby={`tab-${tab}`} className="stack" style={{ gap: 20 }}>
        {err && <div className="card" role="alert"><h2>Could not load analytics</h2><p className="mu">{err}</p></div>}
        {tab === "visitors" ? <Visitors days={days} /> : tab === "feedback" ? <Feedback /> : tab === "interactions" ? <Interactions platform={platform} /> : (
          <>
            {!d && !err && <Loading />}
            {d?.empty && <div className="card"><p className="empty">Nothing collected yet{d.error ? ` (${d.error})` : ""}.</p></div>}
            {d?.empty && <Actions d={d} platform={platform} account={account} reload={load} />}
            {d && !d.empty && <Actions d={d} platform={platform} account={account} reload={load} />}
            {d && !d.empty && (tab === "recommendations" ? <Recs d={d} reload={load} /> : <Numbers d={d} platform={platform} reload={load} />)}
            {d && !d.empty && tab === "analytics" && platform === "instagram" && <><Peers d={d} /><Hashtags d={d} /></>}
            {(tab === "analytics" || tab === "recommendations") && <Auto />}
          </>
        )}
      </div>
    </>
  );
}

import { useEffect, useState } from "react";
import { getJSON, type PlansData } from "../lib/api";
import { errText } from "../lib/songs";
import { Loading } from "../components/Loading";

const LABEL: Record<string, string> = { "playlists.max": "Playlists", "audio.play": "Listen to every song", "library.save": "Save songs and albums", "audio.quality_hi": "High quality audio", offline: "Listen offline", "ads.off": "No ads" };
const label = (f: string) => LABEL[f] ?? f;

// What Free and Premium include, read from the plan data (so a changed limit shows here with no release), and how much of the plan this person has used. Premium cannot be bought yet.
export default function Plans() {
  const [d, setD] = useState<PlansData | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { getJSON<PlansData>("/api/plans").then(setD).catch((e) => setErr(errText(e))); }, []);
  if (!d) return err ? <div className="card" role="alert"><h2>Could not load the plans</h2><p className="mu">{err}</p></div> : <Loading />;
  const cell = (e: PlansData["plans"][number]["entitlements"][number] | undefined) => !e || !e.enabled ? "Not included" : e.limit == null ? "Included" : `Up to ${e.limit}`;
  const features = [...new Set(d.plans.flatMap((p) => p.entitlements.map((e) => e.feature)))];
  const mine = d.mine;
  const lim = mine.entitlements["playlists.max"]?.limit;
  return (
    <>
      <div className="ph"><h1 className="disp">Plans</h1><p>{mine.unlimited ? "You are the owner: no limits apply." : <>You are on <b>{mine.plan.name}</b>.{lim != null ? ` ${mine.usage.playlists} of ${lim} playlists used.` : ""}</>}</p></div>
      <div className="card" style={{ padding: 8 }}>
        <table className="rt">
          <caption className="sr">What each plan includes</caption>
          <thead><tr><th scope="col">Feature</th>{d.plans.map((p) => <th scope="col" key={p.key}>{p.name}{p.key === mine.plan.key && !mine.unlimited ? " (yours)" : ""}</th>)}</tr></thead>
          <tbody>{features.map((f) => <tr key={f}><th scope="row" data-label="Feature">{label(f)}</th>{d.plans.map((p) => <td key={p.key} data-label={p.name}>{cell(p.entitlements.find((e) => e.feature === f))}</td>)}</tr>)}</tbody>
        </table>
      </div>
      <p className="mu">Premium cannot be bought yet. When it can, this page will say how.</p>
    </>
  );
}

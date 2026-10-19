import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getJSON } from "../../lib/api";
import { errText } from "../../lib/songs";
import { Loading } from "../../components/Loading";

type Tot = { views: number; plays: number; seconds: number; pitch: number; visitors: number };
type By = { name: string; views: number; plays: number; visitors: number };
type Visits = { days: number; totals: { today: Tot; d7: Tot; d30: Tot }; songs: { slug: string; title: string | null; views: number; plays: number; seconds: number; visitors: number }[]; sources: By[]; devices: By[] };

const SOURCE: Record<string, string> = { youtube: "YouTube", instagram: "Instagram", whatsapp: "WhatsApp", facebook: "Facebook", x: "X", email: "Email", search: "Search engines", direct: "Direct or an app", other: "Other sites" };
const DEVICE: Record<string, string> = { mobile: "Phone", tablet: "Tablet", desktop: "Computer" };
const mins = (s: number) => (s < 60 ? `${s} s` : `${Math.round(s / 60)} min`);

// Who comes to the public site and what they play (NAV-33). Anonymous: unique visitors are counted per day without cookies or stored addresses.
export default function Visitors({ days }: { days: string }) {
  const [d, setD] = useState<Visits | null>(null); const [err, setErr] = useState("");
  useEffect(() => { setD(null); getJSON<Visits>(`/api/site/visits?days=${days}`).then((x) => { setD(x); setErr(""); }).catch((e) => setErr(errText(e))); }, [days]);
  if (err) return <div className="card" role="alert"><h2>Could not load visitors</h2><p className="mu">{err}</p></div>;
  if (!d) return <Loading />;
  const table = (rows: By[], label: Record<string, string>, head: string) => rows.length
    ? <table className="rt"><thead><tr><th>{head}</th><th>Visitors</th><th>Page views</th><th>Plays</th></tr></thead>
        <tbody>{rows.map((r) => <tr key={r.name}><td data-label={head}>{label[r.name] ?? r.name}</td><td data-label="Visitors">{r.visitors}</td><td data-label="Page views">{r.views}</td><td data-label="Plays">{r.plays}</td></tr>)}</tbody></table>
    : <p className="empty">Nobody yet.</p>;
  return (
    <>
      <section className="sec" aria-labelledby="vt-h">
        <div className="sh"><h2 id="vt-h">Visitors of the public site</h2></div>
        <div className="grid">
          {([["today", "Today"], ["d7", "Last 7 days"], ["d30", "Last 30 days"]] as const).map(([k, label]) => { const t = d.totals[k]; return (
            <div key={k} className="card stack" aria-label={label}><h3>{label}</h3>
              <p><strong>{t.visitors}</strong> visitor{t.visitors === 1 ? "" : "s"}, {t.views} page view{t.views === 1 ? "" : "s"}</p>
              <p className="mu">{t.plays} play{t.plays === 1 ? "" : "s"}, {mins(t.seconds)} listened · {t.pitch} opened the account page</p></div>); })}
        </div>
        <p className="mu">Counted without cookies: a visitor is the same address and browser on the same day, kept only as a code that cannot be traced back. Add <code>?src=yt</code>, <code>ig</code> or <code>wa</code> to links you post so visits from YouTube, Instagram and WhatsApp are told apart.</p>
      </section>
      <section className="sec" aria-labelledby="vs-h">
        <div className="sh"><h2 id="vs-h">Songs, last {d.days} days</h2></div>
        <div className="card" style={{ padding: 8 }}>{d.songs.length
          ? <table className="rt"><thead><tr><th>Song</th><th>Visitors</th><th>Page views</th><th>Plays</th><th>Listened</th></tr></thead>
              <tbody>{d.songs.map((r) => <tr key={r.slug}><td data-label="Song"><Link to={`/studio/songs/${r.slug}`}>{r.title || r.slug}</Link></td><td data-label="Visitors">{r.visitors}</td><td data-label="Page views">{r.views}</td><td data-label="Plays">{r.plays}</td><td data-label="Listened">{mins(r.seconds)}</td></tr>)}</tbody></table>
          : <p className="empty">No song pages opened yet.</p>}</div>
      </section>
      <section className="sec" aria-labelledby="vsrc-h">
        <div className="sh"><h2 id="vsrc-h">Where they came from</h2></div>
        <div className="card" style={{ padding: 8 }}>{table(d.sources, SOURCE, "Source")}</div>
      </section>
      <section className="sec" aria-labelledby="vdev-h">
        <div className="sh"><h2 id="vdev-h">Devices</h2></div>
        <div className="card" style={{ padding: 8 }}>{table(d.devices, DEVICE, "Device")}</div>
      </section>
    </>
  );
}

import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Icon } from "../components/Icon";
import { getJSON, type ScheduleEntry } from "../lib/api";
import { byDay, monthGrid } from "../lib/calendar";
import { classic, errText, itemPath } from "../lib/songs";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const STATE: Record<ScheduleEntry["state"], { label: string; cls: string }> = { scheduled: { label: "Scheduled", cls: "" }, done: { label: "Published", cls: "ok" }, missed: { label: "Missed", cls: "bad" }, blocked: { label: "Blocked", cls: "wn" } };
const time = (at: string) => new Date(at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
const to = (e: ScheduleEntry) => itemPath(e.type, e.slug);

function Item({ e, children, className }: { e: ScheduleEntry; children: React.ReactNode; className?: string }) {
  const p = to(e);
  return p ? <Link className={className} to={p}>{children}</Link> : <a className={className} href={classic(e.slug)}>{children}</a>;
}

// What publishes when: a month calendar on a wide screen, and always a list under it with the day as a heading (the phone shows only the list).
export default function Schedule() {
  const now = new Date();
  const [ym, setYm] = useState({ y: now.getFullYear(), m: now.getMonth() });
  const [all, setAll] = useState<ScheduleEntry[] | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { getJSON<ScheduleEntry[]>("/api/schedule").then(setAll).catch((e) => setErr(errText(e))); }, []);
  const weeks = useMemo(() => monthGrid(ym.y, ym.m), [ym]);
  const days = useMemo(() => byDay(all ?? []), [all]);
  const shown = [...days.entries()].filter(([k]) => k.startsWith(`${ym.y}-${String(ym.m + 1).padStart(2, "0")}-`));
  const step = (n: number) => setYm(({ y, m }) => { const d = new Date(y, m + n, 1); return { y: d.getFullYear(), m: d.getMonth() }; });
  const title = new Date(ym.y, ym.m, 1).toLocaleDateString([], { month: "long", year: "numeric" });
  const attention = (all ?? []).filter((e) => e.state === "missed" || e.state === "blocked").length;
  return (
    <>
      <div className="ph"><h1 className="disp">Schedule</h1><p>What publishes when.{attention ? ` ${attention} need${attention === 1 ? "s" : ""} a look.` : ""}</p></div>
      <div className="row">
        <button className="btn sq" aria-label="Previous month" onClick={() => step(-1)}><span style={{ transform: "rotate(180deg)", display: "flex" }}><Icon name="chevron" /></span></button>
        <h2 className="mon" aria-live="polite">{title}</h2>
        <button className="btn sq" aria-label="Next month" onClick={() => step(1)}><Icon name="chevron" /></button>
      </div>
      {err && <div className="card" role="alert"><h2>Could not load the schedule</h2><p className="mu">{err}</p></div>}
      {!all && !err && <p className="mu" role="status">Loading…</p>}
      {all && (
        <>
          <table className="cal card" aria-label={`Calendar, ${title}`}>
            <thead><tr>{DAYS.map((d) => <th key={d} scope="col">{d}</th>)}</tr></thead>
            <tbody>
              {weeks.map((w, i) => (
                <tr key={i}>{w.map((c) => (
                  <td key={c.key} className={c.inMonth ? "" : "out"} data-day={c.key}>
                    <span className="dn">{c.date.getDate()}</span>
                    {c.inMonth && (days.get(c.key) ?? []).map((e, j) => (
                      <Item key={j} e={e} className={"ent " + STATE[e.state].cls}>{time(e.at)} {e.platform === "YouTube" ? "YT" : "IG"}<span className="sr">, {e.title || e.slug}, {STATE[e.state].label}</span></Item>
                    ))}
                  </td>
                ))}</tr>
              ))}
            </tbody>
          </table>
          <section className="sec" aria-labelledby="list-h">
            <div className="sh"><h2 id="list-h">Day by day</h2><span className="n">{shown.reduce((n, [, v]) => n + v.length, 0)}</span></div>
            {shown.length ? shown.map(([k, es]) => (
              <div key={k} className="card" style={{ padding: 8 }}>
                <h3 className="dayh">{new Date(`${k}T12:00:00`).toLocaleDateString([], { weekday: "long", day: "numeric", month: "long" })}</h3>
                {es.map((e, i) => (
                  <Item key={i} e={e} className="q">
                    <span className="tx"><b>{e.title || e.slug}</b><span className="s">{time(e.at)} · {e.platform}{e.reason ? ` · ${e.reason}` : ""}</span></span>
                    <span className={"chip " + STATE[e.state].cls}>{STATE[e.state].label}</span>
                  </Item>
                ))}
              </div>
            )) : <div className="card"><p className="empty">Nothing scheduled in {title}.</p></div>}
          </section>
        </>
      )}
    </>
  );
}

import { useEffect, useState } from "react";
import { getJSON, postJSON, type BestTime, type SchedOption, type Schedule, type Suggestion } from "../lib/api";
import { fmtL, plusMin, toIso, toLocalIn } from "../lib/datetime";
import { errText } from "../lib/songs";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

// Which hours and weekdays did best, from the analytics. The bars are decoration: the sentence is the content.
export function BestTimes({ b, label }: { b: BestTime | null; label: string }) {
  if (!b) return <p className="mu" role="status">Loading…</p>;
  if (b.empty || !b.hours) return <p className="mu">{(b.notes ?? []).join(" ") || "Not enough data yet. Run Collect on the Analytics page."}</p>;
  const top = (v: number[], n: number) => v.map((x, i) => [x, i] as const).sort((a, c) => c[0] - a[0]).slice(0, n).map(([, i]) => i);
  const hours = top(b.hours, 3).sort((a, c) => a - c); const days = top(b.weekdays ?? [], 3);
  return (
    <div className="stack">
      <p>{label}: best hours (UTC) {hours.map((h) => `${h}:00`).join(", ")}. Best weekdays {days.map((d) => DAYS[(d + 6) % 7] ?? DAYS[d]).join(", ")}.</p>
      <div aria-hidden="true" style={{ display: "flex", alignItems: "flex-end", gap: 2, height: 48 }}>{b.hours.map((v, i) => <span key={i} style={{ flex: 1, height: `${Math.max(4, v)}%`, background: "var(--accent)", opacity: 0.7, borderRadius: 2 }} />)}</div>
    </div>
  );
}

type Props = { type: string; slug?: string; onDone: () => void; onCancel?: () => void };

export function SchedulePanel({ type, slug: slug0 = "", onDone, onCancel }: Props) {
  const [opts, setOpts] = useState<SchedOption[] | null>(null); const [ig, setIg] = useState<BestTime | null>(null); const [yt, setYt] = useState<BestTime | null>(null);
  const [slug, setSlug] = useState(slug0); const [at, setAt] = useState(""); const [ytAt, setYtAt] = useState("");
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  useEffect(() => {
    const t = encodeURIComponent(type);
    getJSON<{ songs: SchedOption[] }>(`/api/schedule/options?type=${t}`).then((r) => { setOpts(r.songs); if (!slug0 && r.songs.length === 1) setSlug(r.songs[0].slug); }).catch((e) => setErr(errText(e)));
    getJSON<BestTime>(`/api/besttime?type=${t}`).then((b) => { setIg(b); setAt((cur) => cur || (b.slots?.[0] ? toLocalIn(b.slots[0].at) : "")); }).catch(() => setIg({ empty: true }));   // expected: no timing data is not an error
    getJSON<BestTime>(`/api/besttime?type=${t}&platform=youtube`).then(setYt).catch(() => setYt({ empty: true }));
  }, [type, slug0]);
  const chosen = opts?.find((o) => o.slug === slug);
  const ytSlots = yt?.kinds?.video && !yt.kinds.video.empty ? yt.kinds.video.slots ?? [] : [];
  const pickYt = (v: string) => { setYtAt(v); if (v && (!at || new Date(at).getTime() < new Date(v).getTime() + 5 * 60000)) setAt(plusMin(v, 60)); };
  const tooClose = !!(ytAt && at && new Date(at).getTime() < new Date(ytAt).getTime() + 5 * 60000);
  const save = async () => {
    setBusy(true); setErr("");
    try { await postJSON("/api/schedule/set", { slug, instagram_at: toIso(at), youtube_at: ytAt ? toIso(ytAt) : null }); onDone(); }
    catch (e) { setErr(errText(e)); } finally { setBusy(false); }
  };
  return (
    <section className="card stack" aria-labelledby="sp-h">
      <h2 id="sp-h">Schedule publishing</h2>
      <label htmlFor="sp-song">Item</label>
      <select id="sp-song" className="field" value={slug} onChange={(e) => setSlug(e.target.value)} disabled={!!slug0}>
        <option value="">{opts === null ? "Loading…" : "Choose one"}</option>
        {(opts ?? []).map((o) => <option key={o.slug} value={o.slug}>{o.slug}{o.title ? ` · ${o.title}` : ""} (next: {o.next})</option>)}
      </select>
      {chosen?.missing_gates.length ? <p className="mu">Still to approve before that time: {chosen.missing_gates.join(", ")}. Nothing posts without them.</p> : null}
      <h3>YouTube</h3>
      {ytSlots.length > 0 && <div className="row" style={{ flexWrap: "wrap" }} role="group" aria-label="Recommended YouTube times">{ytSlots.map((x) => <button key={x.at} className={"btn" + (toLocalIn(x.at) === ytAt ? " p" : "")} onClick={() => pickYt(toLocalIn(x.at))}>{fmtL(x.at)} · {x.score}</button>)}</div>}
      <p className="mu">{!yt ? "Loading…" : yt.kinds?.video && !yt.kinds.video.empty ? `From ${(yt.kinds.video.basis?.signals ?? []).join(", ")}. Confidence ${yt.kinds.video.confidence}. ${(yt.kinds.video.notes ?? []).join(" ")}` : (yt.kinds?.video?.notes ?? yt.notes ?? []).join(" ") || "No YouTube timing data yet. Run Collect on the YouTube tab."}</p>
      <label htmlFor="sp-yt">YouTube public at (your local time)</label>
      <div className="row"><input id="sp-yt" className="field" type="datetime-local" value={ytAt} onChange={(e) => pickYt(e.target.value)} /><button className="btn g" onClick={() => setYtAt("")}>Auto, 15 min before the Reel</button></div>
      <h3>Instagram</h3>
      {(ig?.slots ?? []).length > 0 && <div className="row" style={{ flexWrap: "wrap" }} role="group" aria-label="Recommended Instagram times">{(ig?.slots ?? []).map((x) => <button key={x.at} className={"btn" + (toLocalIn(x.at) === at ? " p" : "")} onClick={() => setAt(toLocalIn(x.at))}>{fmtL(x.at)} · {x.score}</button>)}</div>}
      <BestTimes b={ig} label="Instagram" />
      <label htmlFor="sp-ig">Instagram Reel at (your local time)</label>
      <input id="sp-ig" className="field" type="datetime-local" value={at} onChange={(e) => setAt(e.target.value)} />
      {tooClose ? <p role="alert" className="mu">The Reel must be at least 5 minutes after the YouTube time, because it links to the public video.</p> : <p className="mu">The server must be running at those times.</p>}
      {err && <p role="alert" className="mu">{err}</p>}
      <div className="row">
        <button className="btn p" disabled={!slug || !at || busy || tooClose} onClick={() => void save()}>{busy ? "Saving…" : "Schedule"}</button>
        {onCancel && <button className="btn g" onClick={onCancel}>Cancel</button>}
      </div>
    </section>
  );
}

// On a song: what is scheduled (change, clear), or the suggestion from the analytics to accept.
export function ScheduleCard({ slug, type, schedule, done }: { slug: string; type: string; schedule?: Schedule; done: () => Promise<unknown> | void }) {
  const [sug, setSug] = useState<Suggestion | null>(null); const [edit, setEdit] = useState(false); const [ask, setAsk] = useState(false);
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  useEffect(() => { if (schedule) return; getJSON<{ suggestion: Suggestion | null }>(`/api/schedule/suggest?slug=${encodeURIComponent(slug)}`).then((r) => setSug(r.suggestion)).catch(() => setSug(null)); }, [slug, schedule]);   // expected: no suggestion is fine
  const run = async (path: string) => { setBusy(true); setErr(""); try { await postJSON(path, { slug }); setAsk(false); await done(); } catch (e) { setErr(errText(e)); } finally { setBusy(false); } };
  if (edit) return <SchedulePanel type={type} slug={slug} onDone={() => { setEdit(false); void done(); }} onCancel={() => setEdit(false)} />;
  const blocked = Object.values(schedule?.blocked ?? {}); const missed = Object.keys(schedule?.missed ?? {});
  return (
    <section className="card stack" aria-labelledby="sc-h">
      <h2 id="sc-h">Publishing schedule {schedule?.done && <span className="chip ok">published</span>}</h2>
      {schedule ? (
        <>
          <p>YouTube public: <b>{fmtL(schedule.youtube_at)}</b><br />Instagram Reel: <b>{fmtL(schedule.instagram_at)}</b></p>
          {blocked.length > 0 && <p className="mu">{blocked.join(", ")}. Approve it and the step runs on the next check.</p>}
          {missed.length > 0 && <p className="mu">Missed: {missed.join(", ")}. Pick a new time.</p>}
          <div className="row">
            <button className="btn" disabled={busy} onClick={() => setEdit(true)}>Change</button>
            {ask
              ? <span className="row" role="group" aria-label="Confirm clearing the schedule"><button className="btn p" disabled={busy} onClick={() => void run("/api/schedule/clear")}>Yes, clear it</button><button className="btn g" onClick={() => setAsk(false)}>Keep</button></span>
              : <button className="btn g" disabled={busy} onClick={() => setAsk(true)}>Clear</button>}
          </div>
        </>
      ) : sug ? (
        <>
          <p>Suggested from your analytics <span className="chip">confidence: {sug.confidence}</span><br />YouTube public: <b>{sug.youtube_at ? fmtL(sug.youtube_at) : "auto, 15 minutes before the Reel"}</b><br />Instagram Reel: <b>{fmtL(sug.instagram_at)}</b></p>
          <p className="mu">Based on {sug.basis.join(", ") || "followers online"}. {sug.note ?? ""} Approvals stay yours.</p>
          <div className="row"><button className="btn p" disabled={busy} onClick={() => void run("/api/schedule/accept")}>Use these times</button><button className="btn" onClick={() => setEdit(true)}>Other time</button></div>
        </>
      ) : (
        <>
          <p className="mu">Publish at the time your analytics recommend. Approvals stay yours.</p>
          <button className="btn p" onClick={() => setEdit(true)}>Schedule publishing</button>
        </>
      )}
      {err && <p role="alert" className="mu">{err}</p>}
    </section>
  );
}

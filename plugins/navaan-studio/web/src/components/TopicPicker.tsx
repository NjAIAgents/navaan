import { useState } from "react";
import type { SongDetail } from "../lib/api";

type Act = (path: string, body: Record<string, unknown>) => Promise<boolean>;
type Topic = { title?: string; why_now?: string; angle?: string; audience?: string; signals?: string[]; sources?: string[] };

// The blog's topic approval (NAV-71): the 5 suggested topics side by side; pick one, reword its title or angle if you like, and that is the approval.
export function TopicPicker({ d, act, busy }: { d: SongDetail; act: Act; busy: boolean }) {
  let t: { candidates?: Topic[]; sources_failed?: string[] } = {};
  try { t = JSON.parse(d.text?.["topics.json"] ?? "{}"); } catch { t = {}; }   // expected: a half-written file reads as no topics yet
  const c = t.candidates ?? [];
  const [pick, setPick] = useState(-1); const [title, setTitle] = useState(""); const [angle, setAngle] = useState("");
  const choose = (i: number) => { setPick(i); setTitle(c[i]?.title ?? ""); setAngle(c[i]?.angle ?? ""); };
  if (!c.length) return <p className="mu">The topics are not written yet. Run the pipeline, or use Request changes to ask for new ones.</p>;
  return (
    <form className="stack" onSubmit={(e) => { e.preventDefault(); if (pick >= 0) void act("/api/blog/topic", { index: pick, title, angle }); }}>
      <fieldset className="stack" style={{ border: 0, padding: 0, margin: 0 }}>
        <legend><b>Which topic should it be?</b></legend>
        {c.map((x, i) => (
          <label key={i} className="card stack" style={{ gap: 6, cursor: "pointer" }}>
            <span className="row" style={{ gap: 10, alignItems: "flex-start" }}><input type="radio" name="topic" checked={pick === i} onChange={() => choose(i)} /><b>{x.title}</b></span>
            {x.why_now && <span><span className="mu">Why now: </span>{x.why_now}</span>}
            {x.angle && <span><span className="mu">Angle: </span>{x.angle}</span>}
            {x.audience && <span className="mu">For {x.audience}</span>}
            {!!x.signals?.length && <span className="row" style={{ flexWrap: "wrap", gap: 6 }}>{x.signals.map((s) => <span key={s} className="chip">{s}</span>)}</span>}
            {!!x.sources?.length && <span className="row" style={{ flexWrap: "wrap", gap: 10 }}>{x.sources.map((u, k) => <a key={u} href={u} target="_blank" rel="noreferrer">Source {k + 1}<span className="sr"> for {x.title}</span></a>)}</span>}
          </label>
        ))}
      </fieldset>
      {!!t.sources_failed?.length && <p className="mu" role="note">Not reachable this time: {t.sources_failed.join(", ")}. The topics come from the other sources and the web search.</p>}
      {pick >= 0 && (
        <>
          <label htmlFor="tp-title">Title</label>
          <input id="tp-title" className="field" value={title} maxLength={500} onChange={(e) => setTitle(e.target.value)} />
          <label htmlFor="tp-angle">Angle</label>
          <textarea id="tp-angle" className="field" rows={2} value={angle} maxLength={500} onChange={(e) => setAngle(e.target.value)} />
        </>
      )}
      <div className="row"><button className="btn p" type="submit" disabled={busy || pick < 0}>Use this topic</button></div>
    </form>
  );
}

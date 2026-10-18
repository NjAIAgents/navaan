import type { SongDetail } from "../lib/api";
import { ZoomImage } from "./ZoomImage";
import { GateSwitch, type SetGate } from "./GateSwitch";
import { StepStatus, type Kind } from "./StepStatus";
import { stepView } from "./stepViews";
import { gateTitle, stepLabel, stepWhat } from "../lib/gates";

const IMG = /\.(png|jpe?g|webp)$/i; const AUD = /\.(mp3|m4a|aac|wav|flac|ogg)$/i; const VID = /\.mp4$/i;

type Ev = { at: string; text: string };

// The words and pictures a draft step has already written, shown before the step runs so there is something to read and nothing to guess.
function Draft({ d, id }: { d: SongDetail; id: string }) {
  if (id === "instagram_caption" && d.text?.["instagram.txt"]?.trim()) return <div className="stack"><h3>Draft</h3><pre className="art" tabIndex={0} aria-label="Instagram caption draft">{d.text?.["instagram.txt"]}</pre></div>;
  if (id === "youtube_meta" && d.text?.["youtube.json"]) {
    try { const y = JSON.parse(d.text?.["youtube.json"]) as { title?: string; description?: string; tags?: string[] }; return <div className="stack"><h3>Draft</h3><b>{y.title}</b><pre className="art" tabIndex={0} aria-label="YouTube description draft">{y.description}</pre>{y.tags?.length ? <p className="mu">{y.tags.join(", ")}</p> : null}</div>; }
    catch { return null; }   // expected: not JSON, nothing to show as a draft
  }
  return null;
}

// One step opened: its live state, what it does, what it said and made (laid out for reading, with the raw file under it), its log and its history. Any step can be opened, finished or not.
export function StepDetail({ d, id, events, onBack, done = () => undefined, setGate, busy = false }: { d: SongDetail; id: string; events: Ev[]; onBack: () => void; done?: () => Promise<unknown> | void; setGate?: SetGate; busy?: boolean }) {
  const s = d.steps.find((x) => x.id === id); if (!s) return null;
  const failed = d.failure?.step === id; const waiting = s.status === "waiting for approval";
  const active = !!(d.job?.running || d.job?.queued); const live = active && d.run?.step === id;
  const here = d.next.type !== "done" && d.next.step === id && !s.done;
  const ranBefore = events.find((e) => e.text.includes(`step ${id} done`));
  const kind: Kind = failed ? "failed" : live ? "running" : waiting ? "waiting" : s.done ? "done" : ranBefore ? "stale" : here ? "next" : "later";
  const url = (n: string, size: number) => `/media/${d.slug}/${n}?v=${size}`;
  const made = s.made ?? []; const log = d.logs?.[id];
  const view = stepView(d, id, done); const texts = (s.texts ?? []).filter((t) => !view?.raw.includes(t.name)); const raws = (view?.raw ?? []).filter((n) => d.text?.[n]);
  const gates = [s.gate_before && ["before", s.gate_before], s.gate_after && ["after", s.gate_after]].filter(Boolean) as ["before" | "after", string][];
  const off = d.gates_off ?? [];
  return (
    <section className="card stack" aria-labelledby="sd-h">
      <div className="row"><button className="btn g" onClick={onBack}>Close this step</button></div>
      <StepStatus kind={kind} run={live ? d.run : undefined} usual={d.meta?.step_seconds?.[id]} />
      <h2 id="sd-h">{stepLabel(id)}</h2>
      {stepWhat(id) && <p>{stepWhat(id)}</p>}
      {s.spends_what && <p className="mu">Spends: {s.spends_what}</p>}
      {gates.map(([when, g]) => (
        <div key={g} className="stack" style={{ gap: 4 }}>
          <p className="mu">{s.done ? "Asked for your approval" : "Needs your approval"} {when === "before" ? (s.done ? "before it ran" : "before it runs") : (s.done ? "after it ran" : "after it runs")}: {gateTitle(g)}.</p>
          {setGate && <GateSwitch gate={g} when={when} off={off.includes(g)} busy={busy} setGate={setGate} />}
        </div>
      ))}
      {view?.node}
      {texts.map((t, i) => <details key={t.name} open={!view && i === 0}><summary><b>{t.name}</b></summary><pre className="art" tabIndex={0} aria-label={t.name}>{t.text}</pre></details>)}
      {raws.map((n) => <details key={n}><summary>Raw file: {n}</summary><pre className="art" tabIndex={0} aria-label={`Raw ${n}`}>{d.text?.[n]}</pre></details>)}
      {(s.links ?? []).length > 0 && (
        <div className="stack"><h3>Published</h3>
          <ul className="hist">{(s.links ?? []).map((l) => <li key={l.where + l.url}><b>{l.where}</b>{l.privacy ? <span className="mu"> · {l.privacy}</span> : null}{l.url ? <> · <a href={l.url} target="_blank" rel="noreferrer">{l.url}</a></> : <span className="mu"> · the link was not recorded</span>}</li>)}</ul>
        </div>
      )}
      {made.length > 0 && (
        <div className="stack"><h3>{live ? "Previous version (a new one is being made)" : "What it made"}</h3>
          <div className="row" style={{ flexWrap: "wrap", alignItems: "flex-start" }}>
            {made.map((f) => IMG.test(f.name)
              ? <ZoomImage key={f.name} src={url(f.name, f.size)} alt={f.name} loading="lazy" style={{ maxWidth: 160, maxHeight: 160, borderRadius: 8 }} />
              : VID.test(f.name) ? <video key={f.name} controls playsInline preload="metadata" src={url(f.name, f.size)} aria-label={f.name} style={{ maxWidth: 240, borderRadius: 8 }} />
              : AUD.test(f.name) ? <audio key={f.name} controls preload="none" src={url(f.name, f.size)} aria-label={f.name} />
              : <a key={f.name} href={url(f.name, f.size)} target="_blank" rel="noreferrer">{f.name}</a>)}
          </div>
        </div>
      )}
      {!made.length && !texts.length && !view && !(s.links ?? []).length && (
        <p className="mu">{live ? "Running now. What it makes appears here when it finishes." : s.done ? "This step did not save a file you can open here." : ranBefore ? `It ran before (${ranBefore.at}). Something it depends on changed, so it will run again.` : "It has not run yet."}</p>
      )}
      {!s.done && !live && <Draft d={d} id={id} />}
      {log && <details><summary>Log of this step</summary><pre className="art" tabIndex={0} aria-label={`Log of ${stepLabel(id)}`}>{log}</pre></details>}
      {events.length > 0 && <div className="stack"><h3>History of this step</h3><ul className="hist">{events.map((e, i) => <li key={i}><span className="mu">{e.at}</span> {e.text}</li>)}</ul></div>}
    </section>
  );
}

import type { SongDetail } from "../lib/api";
import { ZoomImage } from "./ZoomImage";
import { gateTitle, stepLabel } from "../lib/gates";

const IMG = /\.(png|jpe?g|webp)$/i; const AUD = /\.(mp3|m4a|aac|wav|flac|ogg)$/i; const VID = /\.mp4$/i;

// One step opened: what it said (a prompt, a plan), what it made, its log and its history. Any step can be opened, finished or not.
export function StepDetail({ d, id, events, onBack }: { d: SongDetail; id: string; events: { at: string; text: string }[]; onBack: () => void }) {
  const s = d.steps.find((x) => x.id === id); if (!s) return null;
  const failed = d.failure?.step === id; const waiting = s.status === "waiting for approval"; const here = d.next.type !== "done" && d.next.step === id && !s.done;
  const [kind, word] = failed ? ["bad", "Failed"] : waiting ? ["wn", "Waiting for you"] : s.done ? ["ok", "Done"] : here ? ["ac", "Next"] : ["", "Not run yet"];
  const url = (n: string, size: number) => `/media/${d.slug}/${n}?v=${size}`;
  const made = s.made ?? []; const texts = s.texts ?? []; const log = d.logs?.[id];
  const gates = [s.gate_before && `Needs your approval before it runs: ${gateTitle(s.gate_before)}.`, s.gate_after && `Needs your approval after it runs: ${gateTitle(s.gate_after)}.`].filter(Boolean) as string[];
  return (
    <section className="card stack" aria-labelledby="sd-h">
      <div className="row"><button className="btn g" onClick={onBack}>‹ Back to what needs you</button></div>
      <span className={`chip ${kind}`}><span className="dot" />{word}</span>
      <h2 id="sd-h">{stepLabel(id)}</h2>
      {s.spends_what && <p className="mu">Spends: {s.spends_what}</p>}
      {gates.map((g) => <p key={g} className="mu">{g}</p>)}
      {texts.map((t, i) => <details key={t.name} open={i === 0}><summary><b>{t.name}</b></summary><pre className="art" tabIndex={0} aria-label={t.name}>{t.text}</pre></details>)}
      {made.length > 0 && (
        <div className="stack"><h3>What it made</h3>
          <div className="row" style={{ flexWrap: "wrap", alignItems: "flex-start" }}>
            {made.map((f) => IMG.test(f.name)
              ? <ZoomImage key={f.name} src={url(f.name, f.size)} alt={f.name} loading="lazy" style={{ maxWidth: 160, maxHeight: 160, borderRadius: 8 }} />
              : VID.test(f.name) ? <video key={f.name} controls playsInline preload="metadata" src={url(f.name, f.size)} aria-label={f.name} style={{ maxWidth: 240, borderRadius: 8 }} />
              : AUD.test(f.name) ? <audio key={f.name} controls preload="none" src={url(f.name, f.size)} aria-label={f.name} />
              : <a key={f.name} href={url(f.name, f.size)} target="_blank" rel="noreferrer">{f.name}</a>)}
          </div>
        </div>
      )}
      {!made.length && !texts.length && <p className="mu">{s.done ? "This step did not save a file you can open here." : "It has not run yet, so there is nothing to show."}</p>}
      {log && <details><summary>Log of this step</summary><pre className="art" tabIndex={0} aria-label={`Log of ${stepLabel(id)}`}>{log}</pre></details>}
      {events.length > 0 && <div className="stack"><h3>History of this step</h3><ul className="hist">{events.map((e, i) => <li key={i}><span className="mu">{e.at}</span> {e.text}</li>)}</ul></div>}
    </section>
  );
}

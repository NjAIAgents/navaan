import { useState } from "react";
import type { SongDetail, Step } from "../lib/api";
import { stepLabel } from "../lib/gates";
import { Icon } from "./Icon";

type Act = (path: string, body: Record<string, unknown>) => Promise<boolean>;
type State = "done" | "now" | "waiting" | "failed" | "later";
const WORD: Record<State, string> = { done: "done", now: "now", waiting: "waiting for you", failed: "failed", later: "later" };

// One step of the pipeline: a node, its label beside it, what state it is in, and Redo / Restart on the row itself.
function Row({ s, state, act, busy, selected, onSelect }: { s: Step; state: State; act: Act; busy: boolean; selected: boolean; onSelect?: (id: string) => void }) {
  const [ask, setAsk] = useState<"redo" | "restart" | null>(null);
  const go = async () => { if (await act(ask === "redo" ? "/api/redo" : "/api/restart", { step: s.id })) setAsk(null); };
  const note = state === "waiting" ? "waiting for you" : state === "failed" ? "failed" : s.spends && state !== "done" ? "spends credits" : s.gate_before && state !== "done" ? "needs your approval first" : "";
  return (
    <li className={`rl ${state}${selected ? " sel" : ""}`} id={`step-${s.id}`} aria-current={state === "now" ? "step" : undefined}>
      <span className="nd" aria-hidden="true">{state === "done" ? <Icon name="check" /> : state === "waiting" ? "‖" : state === "failed" ? "✕" : ""}</span>
      <span className="rt">
        {onSelect ? <button type="button" className="lb lb-btn" aria-pressed={selected} onClick={() => onSelect(s.id)}><span className="sr">{WORD[state]}:</span>{" "}{stepLabel(s.id)}</button>
          : <span className="lb"><span className="sr">{WORD[state]}:</span>{" "}{stepLabel(s.id)}</span>}
        {note && <span className="mu st">{note}</span>}
      </span>
      {s.done && (s.redo || s.restart) && !ask && (
        <span className="row">
          {s.redo && <button className="btn g" disabled={busy} onClick={() => setAsk("redo")} aria-label={`Redo ${stepLabel(s.id)}`}>Redo</button>}
          {s.restart && <button className="btn g" disabled={busy} onClick={() => setAsk("restart")} aria-label={`Restart from ${stepLabel(s.id)}`}>Restart from here</button>}
        </span>
      )}
      {ask && (
        <span className="stack rc" role="group" aria-label={`Confirm ${ask} of ${stepLabel(s.id)}`}>
          <span className="mu">{ask === "redo" ? "Redo only this step? Its current files go to the _prev folder inside the song (nothing is deleted). If the new run fails, the old files are put back." + (s.spends ? " It spends credits, so approve the credits gate again first." : "") : "Restart from here? This step and every step after it will run again, and approvals after it are taken back."}</span>
          <span className="row"><button className="btn p" disabled={busy} onClick={() => void go()}>{ask === "redo" ? "Yes, redo it" : "Yes, restart"}</button><button className="btn g" onClick={() => setAsk(null)}>Not now</button></span>
        </span>
      )}
    </li>
  );
}

// The whole pipeline, top to bottom, in order, with the label beside each node. Replaces the chip strip plus the far-away Steps list.
export function PipelineRail({ d, act, busy, selected, onSelect }: { d: SongDetail; act: Act; busy: boolean; selected?: string; onSelect?: (id: string) => void }) {
  if (!d.steps?.length) return null;
  const cur = d.next.type === "done" ? "" : (d.next.step ?? ""); const failed = d.failure?.step ?? "";
  const done = d.steps.filter((s) => s.done).length;
  // Only the step whose approval is the one in front of you "waits for you". A step blocked behind a later approval is just later, so one amber row marks the one thing that needs you.
  const gate = d.next.type === "gate" ? d.next.gate : undefined;
  const asks = (s: Step) => s.status === "waiting for approval" && (s.done ? !!gate && s.needs_gate === gate : s.id === cur);
  const stateOf = (s: Step): State => (s.id === failed ? "failed" : asks(s) ? "waiting" : s.done ? "done" : s.id === cur ? "now" : "later");
  return (
    <section aria-labelledby="rail-h">
      <div className="sh"><h2 id="rail-h">Steps</h2><span className="n">{done}/{d.steps.length}</span></div>
      <ol className="card rail">{d.steps.map((s) => <Row key={s.id} s={s} state={stateOf(s)} act={act} busy={busy} selected={selected === s.id} onSelect={onSelect} />)}</ol>
    </section>
  );
}

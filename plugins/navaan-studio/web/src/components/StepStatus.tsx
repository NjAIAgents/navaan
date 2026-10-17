import type { ReactNode } from "react";
import { dur, usually } from "../lib/dur";

export type Kind = "running" | "waiting" | "failed" | "done" | "next" | "later" | "stale";
const WORD: Record<Kind, string> = { running: "Running", waiting: "Waiting for you", failed: "Failed", done: "Done", next: "Next", later: "Not run yet", stale: "Needs to run again" };
const CHIP: Record<Kind, string> = { running: "ac", waiting: "wn", failed: "bad", done: "ok", next: "ac", later: "", stale: "wn" };

export type RunInfo = { step?: string; attempt?: number; attempts?: number; elapsed?: number; quiet_s?: number; pct?: number; label?: string };

// A progress bar. With a share it fills; without one it moves, so a step that reports nothing still looks alive.
export function Bar({ pct, label, small = false }: { pct?: number; label?: string; small?: boolean }) {
  const cls = `bar${small ? " sm" : ""}`;
  return pct === undefined
    ? <div className={`${cls} ind`} role="progressbar" aria-label={label || "Working"} aria-busy="true"><i /></div>
    : <div className={cls} role="progressbar" aria-label={label || "Progress"} aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct}><i style={{ width: `${pct}%` }} /></div>;
}

// The state of one step, the same wherever it is shown: a chip with an icon that moves while it runs, the bar, and the facts that tell a slow step from a stuck one.
export function StepStatus({ kind, run, usual, children }: { kind: Kind; run?: RunInfo; usual?: number; children?: ReactNode }) {
  const facts = kind !== "running" ? [] : [
    run?.label ? (run.pct !== undefined ? `${run.label} (${run.pct}%)` : run.label) : "",
    run?.elapsed !== undefined ? `running for ${dur(run.elapsed)}` : "",
    run?.attempts && run.attempts > 1 ? `attempt ${run.attempt ?? 1} of ${run.attempts}` : "",
    run?.quiet_s !== undefined ? `last activity ${dur(run.quiet_s)} ago` : "",
    usual ? `usually ${usually(usual)}` : "",
  ].filter(Boolean);
  return (
    <div className="stack ss" data-kind={kind}>
      <span className={`chip ${CHIP[kind]}`}>{kind === "running" ? <span className="spin" aria-hidden="true" /> : kind === "waiting" ? <span className="pulse" aria-hidden="true" /> : <span className="dot" />}{WORD[kind]}</span>
      {kind === "running" && <Bar pct={run?.pct} label={run?.label} />}
      {facts.length > 0 && <p className="mu">{facts.join(" · ")}</p>}
      {children}
    </div>
  );
}

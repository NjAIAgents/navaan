import type { SongDetail } from "../lib/api";
import { stepLabel } from "../lib/gates";
import { Icon } from "./Icon";

// The whole pipeline at a glance: one chip per step, in order, saying done, the one you are at (or that waits for you), failed, or later. A chip jumps to its row in the Steps list below.
export function StepStrip({ d }: { d: SongDetail }) {
  if (!d.steps?.length) return null;
  const cur = d.next.type === "done" ? "" : (d.next.step ?? ""); const failed = d.failure?.step ?? "";
  const done = d.steps.filter((s) => s.done).length;
  return (
    <nav aria-label="Pipeline progress" className="stack" style={{ gap: 8 }}>
      <p className="mu" style={{ margin: 0 }}>{done} of {d.steps.length} steps done{cur ? ` · now: ${stepLabel(cur)}` : " · all done"}</p>
      <ol className="strip">
        {d.steps.map((s) => {
          const bad = s.id === failed; const here = s.id === cur && !s.done; const wait = s.status === "waiting for approval";
          const kind = bad ? "bad" : wait ? "wn" : s.done ? "ok" : here ? "ac" : "";
          const state = bad ? "failed" : wait ? "waiting for you" : s.done ? "done" : here ? "now" : "later";
          return (
            <li key={s.id}><a className={`chip ${kind}`} href={`#step-${s.id}`} aria-label={`${stepLabel(s.id)}: ${state}`} aria-current={here ? "step" : undefined}>
              {kind === "ok" ? <Icon name="check" /> : <span className="dot" />}{stepLabel(s.id)}</a></li>
          );
        })}
      </ol>
    </nav>
  );
}

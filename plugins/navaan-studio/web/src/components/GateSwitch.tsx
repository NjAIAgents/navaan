import { useState } from "react";
import { RISKY, gateTitle, riskText } from "../lib/gates";

export type SetGate = (gate: string, on: boolean) => Promise<boolean>;

// "Ask me before this runs": the same switch as Settings, Approvals that approve themselves, so it applies to every song. Switching a risky one off asks first.
export function GateSwitch({ gate, when, off, busy, setGate }: { gate: string; when: "before" | "after"; off: boolean; busy: boolean; setGate: SetGate }) {
  const [ask, setAsk] = useState(false);
  const id = `gs-${gate}-${when}`;
  const flip = (on: boolean) => { if (!on && RISKY.has(gate)) setAsk(true); else void setGate(gate, on); };
  return (
    <span className="gsw">
      <label htmlFor={id} className="gsw-l mu"><input id={id} className="gsw-in" type="checkbox" role="switch" checked={!off} disabled={busy} onChange={(e) => flip(e.target.checked)} /><span className="gsw-t" aria-hidden="true" /> <span>{when === "before" ? "Ask me before it runs" : "Ask me after it runs"}</span></label>
      {ask && (
        <span className="stack rc" role="alertdialog" aria-label={`Confirm switching off ${gateTitle(gate)}`}>
          <span className="mu">{gateTitle(gate)} will approve itself from now on, for every song, without asking you. It {riskText(gate)}.</span>
          <span className="row">
            <button className="btn p" disabled={busy} onClick={() => void setGate(gate, false).then(() => setAsk(false))}>Yes, approve it automatically</button>
            <button className="btn g" onClick={() => setAsk(false)}>Keep asking me</button>
          </span>
        </span>
      )}
    </span>
  );
}

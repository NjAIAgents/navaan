import { useState } from "react";

export type View = "grid" | "list";

// Grid or list for a screen, remembered per screen in this browser. Grid is the default.
export function useView(key: string): [View, (v: View) => void] {
  const k = `navaan.view.${key}`;
  const [v, setV] = useState<View>(() => { try { return localStorage.getItem(k) === "list" ? "list" : "grid"; } catch { return "grid"; } });   // expected: storage can be blocked
  const set = (n: View) => { setV(n); try { localStorage.setItem(k, n); } catch { /* expected: storage can be blocked, the choice just is not remembered */ } };
  return [v, set];
}

export function ViewToggle({ view, onChange }: { view: View; onChange: (v: View) => void }) {
  return (
    <div className="seg" role="group" aria-label="View">
      {(["grid", "list"] as const).map((x) => <button key={x} aria-pressed={view === x} onClick={() => onChange(x)}>{x === "grid" ? "Grid" : "List"}</button>)}
    </div>
  );
}

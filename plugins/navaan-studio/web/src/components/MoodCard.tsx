import { useState } from "react";
import { postJSON, type SongDetail } from "../lib/api";
import { errText } from "../lib/songs";

export const MOODS: [string, string][] = [["", "None (the night picture)"], ["dawn", "Dawn: hopeful, first light"], ["dusk", "Dusk: warm, nostalgic"], ["night", "Night: quiet, reflective"], ["quiet", "Quiet: intimate, candlelit room"]];

// The song's mood picks the picture behind the lyrics in full screen play mode.
export function MoodCard({ d, done }: { d: SongDetail; done: () => Promise<unknown> | void }) {
  const [busy, setBusy] = useState(false); const [err, setErr] = useState("");
  const cur = d.meta.mood ?? "";
  const set = async (mood: string) => { setBusy(true); setErr(""); try { await postJSON("/api/mood", { slug: d.slug, mood }); await done(); } catch (e) { setErr(errText(e)); } finally { setBusy(false); } };
  return (
    <section className="card stack" aria-labelledby="mood-h">
      <h2 id="mood-h">Mood</h2>
      <label htmlFor="mood-sel">Picture behind the lyrics in play mode</label>
      <select id="mood-sel" className="field" value={cur} disabled={busy} onChange={(e) => void set(e.target.value)}>{MOODS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
      {cur && <img src={`/app/moods/${cur}-wide.webp`} alt={`The ${cur} picture`} width={240} height={135} style={{ borderRadius: 8, objectFit: "cover" }} />}
      {err && <p role="alert" style={{ color: "var(--bad)" }}>{err}</p>}
    </section>
  );
}

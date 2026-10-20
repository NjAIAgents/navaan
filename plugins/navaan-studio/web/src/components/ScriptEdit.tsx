import { useState } from "react";
import { postJSON, type SongDetail } from "../lib/api";
import { errText } from "../lib/songs";

type Done = () => Promise<unknown> | void;
const read = (t: string | undefined): { lines: string[]; captions: string[] } => {
  try { const q = JSON.parse(t ?? "{}"); const lines: string[] = Array.isArray(q.lines) ? q.lines.map(String) : []; const caps: string[] = Array.isArray(q.captions) ? q.captions.map(String) : []; return { lines, captions: lines.map((_, i) => caps[i] ?? "") }; }
  catch { return { lines: [], captions: [] }; }   // expected: a script that is not JSON has nothing to edit here (the Content tab has the raw file)
};

// An Aha-lorithm script at its approval (NAV-133): change the words of its beats, or give your own words and have the script made again from them. Mount it with a key of the script's text so it starts over when the script changes.
export function ScriptEdit({ d, done }: { d: SongDetail; done: Done }) {
  const first = read(d.text["quote.json"]);
  const [lines, setLines] = useState(first.lines); const [caps, setCaps] = useState(first.captions); const [own, setOwn] = useState("");
  const [busy, setBusy] = useState(false); const [err, setErr] = useState(""); const [said, setSaid] = useState("");
  const dirty = lines.some((l, i) => l !== first.lines[i]) || caps.some((c, i) => c !== first.captions[i]);
  const send = async (path: string, body: Record<string, unknown>, ok: string) => {
    setBusy(true); setErr(""); setSaid("");
    try { await postJSON(path, { slug: d.slug, ...body }); setSaid(ok); await done(); } catch (e) { setErr(errText(e)); } finally { setBusy(false); }
  };
  if (!first.lines.length) return null;
  return (
    <section className="card stack" aria-label="Change the script">
      <h3>Not quite right?</h3>
      <details className="stack">
        <summary><b>Edit the words</b>{dirty && <span className="chip wn"> Unsaved changes</span>}</summary>
        <p className="mu">Change what is spoken and what is drawn for each beat. The beats, pictures and visual plan stay as they are.</p>
        {lines.map((l, i) => (
          <div key={i} className="stack">
            <label htmlFor={`sl-${i}`}>Beat {i + 1}, spoken</label>
            <textarea id={`sl-${i}`} className="field" rows={2} value={l} onChange={(e) => setLines(lines.map((x, j) => (j === i ? e.target.value : x)))} />
            <label htmlFor={`sc-${i}`}>Beat {i + 1}, caption <span className="mu">(*star* a phrase to colour it)</span></label>
            <input id={`sc-${i}`} className="field" value={caps[i]} onChange={(e) => setCaps(caps.map((x, j) => (j === i ? e.target.value : x)))} />
          </div>
        ))}
        <div className="row">
          <button className="btn p" disabled={busy || !dirty} aria-busy={busy} onClick={() => void send("/api/aha/edit-script", { lines, captions: caps }, "Saved. Approve the script when you are happy with it.")}>Save the words</button>
          {dirty && <button className="btn g" disabled={busy} onClick={() => { setLines(first.lines); setCaps(first.captions); }}>Discard changes</button>}
        </div>
      </details>
      <details className="stack">
        <summary><b>Use my own words</b></summary>
        <p className="mu">Paste your script, one sentence per line. It is kept exactly as you write it: Claude splits it into beats and makes the captions, picture prompts and visual plan for it (one Claude call). This replaces the current script.</p>
        <label htmlFor="own-words">Your words</label>
        <textarea id="own-words" className="field" rows={6} value={own} onChange={(e) => setOwn(e.target.value)} />
        <div className="row"><button className="btn p" disabled={busy || own.trim().length < 20} aria-busy={busy} onClick={() => void send("/api/aha/replace-script", { text: own }, "Making the script from your words.")}>Make the script from my words</button></div>
      </details>
      {err && <p role="alert" className="err">{err}</p>}
      {said && !err && <p role="status" className="mu">{said}</p>}
    </section>
  );
}

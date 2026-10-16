import { useState } from "react";
import { postJSON, type SongDetail } from "../lib/api";
import { fileB64 } from "../lib/files";
import { errText } from "../lib/songs";

const LOOK: Record<string, string> = { bold: "Bold serif", brush: "Brush", hand: "Handwritten" };

// The poster: portrait art made from a prompt you can read and change, with the title and artist drawn by us. Generating spends on the OpenAI images API, so the cost is on the button.
export function PosterCard({ d, done }: { d: SongDetail; done: () => Promise<unknown> | void }) {
  const p = d.poster;
  const [text, setText] = useState<string | null>(null); const [style, setStyle] = useState<string | null>(null);
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  if (!p) return null;
  const prompt = text ?? p.prompt; const running = !!p.running || busy;
  const go = async (body: Record<string, unknown>) => {
    setBusy(true); setErr("");
    try { await postJSON("/api/poster/generate", { slug: d.slug, ...body }); await done(); } catch (e) { setErr(errText(e)); } finally { setBusy(false); }
  };
  const look = style ?? p.style;
  const cover = !!(d.files ?? {})["cover_1x1.png"];
  return (
    <section className="card stack" aria-labelledby="poster-h">
      <h2 id="poster-h">Poster</h2>
      <div className="row" style={{ alignItems: "flex-start", flexWrap: "wrap" }}>
        {cover && <figure className="stack" style={{ margin: 0 }}><img src={`/media/${d.slug}/cover_1x1.png?w=240`} alt="Cover" width={120} height={120} style={{ borderRadius: 8, objectFit: "cover" }} /><figcaption className="mu">Cover</figcaption></figure>}
        <figure className="stack" style={{ margin: 0 }}>
          {p.has ? <img src={`/media/${d.slug}/poster_2x3.png?w=360&v=${p.v}`} alt="Poster" width={120} height={180} style={{ borderRadius: 8, objectFit: "cover" }} /> : <span className="mu">No poster yet.</span>}
          <figcaption className="mu">Poster</figcaption>
        </figure>
      </div>
      <label htmlFor="poster-prompt">Prompt for the art (change it as you like)</label>
      <textarea id="poster-prompt" className="field" rows={6} value={prompt} onChange={(e) => setText(e.target.value)} disabled={running} />
      <label htmlFor="poster-style">Lettering</label>
      <select id="poster-style" className="field" value={look} disabled={running} onChange={(e) => { setStyle(e.target.value); if (p.has) void go({ only_text: true, style: e.target.value }); }}>
        {p.styles.map((k) => <option key={k} value={k}>{LOOK[k] ?? k}</option>)}
      </select>
      <p className="mu">The NAVAAN mark, title and artist are drawn over the art by us, so the art must have no lettering.</p>
      {!p.key && <p className="mu" role="status">Paste an OpenAI key in Settings first.</p>}
      <div className="row">
        <button className="btn p" disabled={running || !p.key || prompt.trim().length < 20} onClick={() => void go({ prompt, style: look })}>{running ? "Making…" : `${p.has ? "Make a new poster" : "Make poster"} (about $${p.usd.toFixed(2)})`}</button>
        {p.has && <button className="btn g" disabled={running} onClick={() => void go({ only_text: true })}>Redraw the title (free)</button>}
        <label className="btn g" style={{ cursor: running ? "default" : "pointer" }}>Use my own picture<input type="file" accept="image/*" hidden disabled={running} onChange={(e) => { const f = e.target.files?.[0]; if (f) void fileB64(f).then((picture) => go({ picture })); e.target.value = ""; }} /></label>
        {text !== null && <button className="btn g" disabled={running} onClick={() => setText(null)}>Reset prompt</button>}
      </div>
      {(err || p.error) && <p role="alert" style={{ color: "var(--bad)" }}>{err || p.error}</p>}
    </section>
  );
}

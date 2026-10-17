import { useCallback, useEffect, useState } from "react";
import { getJSON, postJSON } from "../lib/api";
import { fileB64 } from "../lib/files";
import { errText } from "../lib/songs";

type State = { prompt: string; has: boolean; v: number; style: string; styles: string[]; usd: number; key: boolean; running?: boolean; error?: string };
const LOOK: Record<string, string> = { bold: "Bold serif", brush: "Brush", hand: "Handwritten" };

// The album's cover: square art from a prompt you can read and change (OpenAI images, the cost is on the button), with the NAVAAN mark, the title and the artist drawn by us. Or use your own picture.
export function AlbumCoverCard({ slug }: { slug: string }) {
  const [s, setS] = useState<State | null>(null); const [text, setText] = useState<string | null>(null); const [style, setStyle] = useState<string | null>(null);
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  const load = useCallback(() => getJSON<State>(`/api/albums/cover?album=${encodeURIComponent(slug)}`).then(setS).catch((e) => setErr(errText(e))), [slug]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => { if (!s?.running) return; const t = setInterval(() => void load(), 3000); return () => clearInterval(t); }, [s?.running, load]);
  if (!s || !Array.isArray(s.styles)) return err ? <p role="alert" className="mu">{err}</p> : null;   // not loaded yet, or an answer that is not a cover state
  const prompt = text ?? s.prompt; const look = style ?? s.style; const running = !!s.running || busy;
  const go = async (body: Record<string, unknown>) => { setBusy(true); setErr(""); try { await postJSON("/api/albums/cover", { album: slug, ...body }); await load(); } catch (e) { setErr(errText(e)); } finally { setBusy(false); } };
  return (
    <section className="card stack" aria-labelledby="ac-h">
      <h2 id="ac-h">Cover</h2>
      {s.has ? <img src={`/api/albums/cover/${slug}.png?v=${s.v}`} alt="Album cover" width={180} height={180} style={{ borderRadius: 10, objectFit: "cover" }} /> : <span className="mu">No cover yet.</span>}
      <label htmlFor="ac-prompt">Prompt for the art (change it as you like)</label>
      <textarea id="ac-prompt" className="field" rows={5} value={prompt} onChange={(e) => setText(e.target.value)} disabled={running} />
      <label htmlFor="ac-style">Lettering</label>
      <select id="ac-style" className="field" value={look} disabled={running} onChange={(e) => { setStyle(e.target.value); if (s.has) void go({ only_text: true, style: e.target.value }); }}>{s.styles.map((k) => <option key={k} value={k}>{LOOK[k] ?? k}</option>)}</select>
      {!s.key && <p className="mu" role="status">Paste an OpenAI key in Settings first.</p>}
      <div className="row">
        <button className="btn p" disabled={running || !s.key || prompt.trim().length < 20} onClick={() => void go({ prompt, style: look })}>{running ? "Making…" : `${s.has ? "Make a new cover" : "Make cover"} (about $${s.usd.toFixed(2)})`}</button>
        <label className="btn g" style={{ cursor: running ? "default" : "pointer" }}>Use my own picture<input type="file" accept="image/*" hidden disabled={running} onChange={(e) => { const f = e.target.files?.[0]; if (f) void fileB64(f).then((picture) => go({ picture })); e.target.value = ""; }} /></label>
        {text !== null && <button className="btn g" disabled={running} onClick={() => setText(null)}>Reset prompt</button>}
      </div>
      {(err || s.error) && <p role="alert" style={{ color: "var(--bad)" }}>{err || s.error}</p>}
    </section>
  );
}

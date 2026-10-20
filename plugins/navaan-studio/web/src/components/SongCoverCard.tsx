import { useState } from "react";
import { ZoomImage } from "./ZoomImage";
import { postJSON, type SongDetail } from "../lib/api";
import { fileB64 } from "../lib/files";
import { errText } from "../lib/songs";

// The song's cover: square art in the modern look, made from a prompt you can read and change (OpenAI images, the cost is on the button) with the title and artist drawn by us, or your own picture.
// The pipeline makes one too; whatever is made here replaces it, in the mp3's next tagging, YouTube, Instagram and, when the song is in the bucket, on the site.
export function SongCoverCard({ d, done }: { d: SongDetail; done: () => Promise<unknown> | void }) {
  const c = d.cover;
  const [text, setText] = useState<string | null>(null); const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  if (!c) return null;
  const prompt = text ?? c.prompt; const running = !!c.running || busy;
  const go = async (url: string, body: Record<string, unknown>) => { setBusy(true); setErr(""); try { await postJSON(url, { slug: d.slug, ...body }); await done(); } catch (e) { setErr(errText(e)); } finally { setBusy(false); } };
  return (
    <section className="card stack" aria-labelledby="songcover-h">
      <h2 id="songcover-h">Cover</h2>
      {c.has ? <ZoomImage src={`/media/${d.slug}/cover_1x1.png?w=240&v=${c.v}`} full={`/media/${d.slug}/cover_1x1.png?v=${c.v}`} alt="Cover" width={160} height={160} style={{ borderRadius: 8, objectFit: "cover" }} /> : <span className="mu">No cover yet. The pipeline makes one before the video; you can make it now.</span>}
      <label htmlFor="songcover-prompt">Prompt for the cover art (change it as you like)</label>
      <textarea id="songcover-prompt" className="field" rows={6} value={prompt} onChange={(e) => setText(e.target.value)} disabled={running} />
      <p className="mu">The title and artist are drawn over the art by us, so the art must have no lettering.</p>
      {!c.key && <p className="mu" role="status">Paste an OpenAI key in Settings first.</p>}
      {c.has && c.in_bucket && !c.published && <p className="mu" role="status">This cover is not on the site yet.</p>}
      <div className="row">
        <button className="btn p" disabled={running || !c.key || prompt.trim().length < 20} onClick={() => void go("/api/cover/generate", { prompt })}>{running ? "Making…" : `${c.has ? "Make a new cover" : "Make cover"} (about $${c.usd.toFixed(2)})`}</button>
        {c.art && <button className="btn g" disabled={running} onClick={() => void go("/api/cover/generate", { only_text: true })}>Redraw the title (free)</button>}
        <label className="btn g" style={{ cursor: running ? "default" : "pointer" }}>Use my own picture<input type="file" accept="image/*" hidden disabled={running} onChange={(e) => { const f = e.target.files?.[0]; if (f) void fileB64(f).then((picture) => go("/api/cover/generate", { picture })); e.target.value = ""; }} /></label>
        {c.has && c.in_bucket && !c.published && <button className="btn g" disabled={running} onClick={() => void go("/api/cover/publish", {})}>Save for the site</button>}
        {c.default && prompt !== c.default && <button className="btn g" disabled={running} onClick={() => setText(c.default ?? null)}>Reset to the suggested prompt</button>}
      </div>
      {(err || c.error) && <p role="alert" style={{ color: "var(--bad)" }}>{err || c.error}</p>}
    </section>
  );
}

import { useState } from "react";
import { postJSON, type SongDetail } from "../lib/api";
import { fileB64 } from "../lib/files";
import { errText } from "../lib/songs";

type Look = "video" | "static" | "flow";

// The visuals_mode gate: how the video looks, the pictures it uses, and the helpers that make pictures (prompts to paste into Gemini or ChatGPT, a 2-picture OpenAI test, 9:16 versions).
export function VisualsCard({ d, done }: { d: SongDetail; done: () => Promise<unknown> | void }) {
  const v = d.visuals ?? {};
  const [look, setLook] = useState<Look>(v.mode === "flow" ? "flow" : v.layout === "static" ? "static" : "video");
  const [camera, setCamera] = useState(v.camera ?? ""); const [scene, setScene] = useState(v.scene ?? "");
  const [busy, setBusy] = useState(""); const [err, setErr] = useState(""); const [note, setNote] = useState("");
  const imgs = d.images ?? []; const need = look === "static" ? 1 : 4;
  const later = !!d.openai_pictures && look === "video" && imgs.length < need;
  const ok = look === "flow" || imgs.length >= need || later;
  const pk = d.prompt_pack; const t = d.try ?? {}; const vert = d.vertical ?? {};
  const run = async (what: string, f: () => Promise<unknown>) => {
    setBusy(what); setErr("");
    try { await f(); await done(); } catch (e) { setErr(errText(e)); } finally { setBusy(""); }
  };
  const upload = (files: FileList | null) => run("Uploading…", async () => {
    for (const f of Array.from(files ?? [])) await postJSON("/api/visuals/upload", { slug: d.slug, name: f.name, data: await fileB64(f) });
  });
  const copy = async (text: string, what: string) => {
    try { await navigator.clipboard.writeText(text); setNote(`Copied ${what}`); } catch { setNote("Copy failed. Select the text by hand."); }   // expected: clipboard can be blocked
  };
  return (
    <section className="card stack" aria-labelledby="vs-h">
      <span className="chip wn"><span className="dot" />Waiting for you</span>
      <h2 id="vs-h">How should the video look?</h2>
      <label htmlFor="vs-look">Look</label>
      <select id="vs-look" className="field" value={look} onChange={(e) => setLook(e.target.value as Look)}>
        <option value="video">Video from 4 or more pictures (default)</option>
        <option value="static">One cover picture</option>
        <option value="flow">Google Flow clips (spends credits)</option>
      </select>
      {look === "flow" ? <p className="mu">Flow clips spend credits. You approve the credits next.</p> : (
        <>
          <p className="mu">{look === "static" ? "The picture stays on screen for the whole song." : "The director writes a shot list from the lyrics (picture, camera move, timing per section). You approve or edit it, then it renders here. No credits."}</p>
          <label htmlFor="vs-files">Pictures</label>
          <input id="vs-files" className="field" type="file" accept="image/*" multiple disabled={!!busy} onChange={(e) => void upload(e.target.files)} />
          {imgs.length > 0 && (
            <ul className="row" aria-label="Pictures added" style={{ listStyle: "none", padding: 0, flexWrap: "wrap" }}>
              {imgs.map((f, i) => (
                <li key={f} className="stack" style={{ width: 96 }}>
                  <img src={`/media/${d.slug}/images~${encodeURIComponent(f)}?w=160`} alt="" width={92} height={62} style={{ objectFit: "cover", borderRadius: 6 }} />
                  <button className="btn g" disabled={!!busy} onClick={() => void run("Removing…", () => postJSON("/api/visuals/remove", { slug: d.slug, path: `images/${f}` }))} aria-label={`Remove picture ${f}`}>Remove</button>
                  {d.openai_pictures && (() => { const m = /pic_(\d+)/.exec(f); if (!m) return null; const k = Number(m[1]);
                    return (vert.done ?? []).includes(k) ? <span className="mu">9:16 ready</span>
                      : <button className="btn g" disabled={!!busy || !!vert.running} onClick={() => void run("Making 9:16…", () => postJSON("/api/visuals/vertical", { slug: d.slug, pics: [k] }))}>{vert.running ? "Making…" : "Make 9:16 (about 5 cents)"}</button>; })()}
                  <span className="sr">Picture {i + 1}</span>
                </li>
              ))}
            </ul>
          )}
          <p className="mu" role="status">{later ? "OpenAI will make the pictures after you save: the director writes the plan first, then you approve the cost before anything is spent. You can also upload your own." : `${imgs.length} picture${imgs.length === 1 ? "" : "s"} added, ${need} needed at least.`} {busy}</p>
          {look === "video" && (
            <div className="card stack">
              <h3>No pictures yet? Make them with Gemini or ChatGPT</h3>
              <p className="mu">Claude writes one image prompt per picture. Paste each into Gemini or ChatGPT (your own plan, nothing is spent here), then upload the results above. Ask for {pk?.aspect ?? "16:9"} landscape.</p>
              <div className="row">
                <button className="btn" disabled={!!busy} onClick={() => void run("Writing prompts…", () => postJSON("/api/visuals/prompts", { slug: d.slug }))}>{busy === "Writing prompts…" ? "Writing prompts, about a minute…" : pk ? "Write them again" : "Write the prompts"}</button>
                {pk && <button className="btn g" onClick={() => void copy(`${pk.style_line}\n\n${pk.prompts.map((p) => `${p.n}. ${p.prompt}`).join("\n")}`, "all prompts")}>Copy all, numbered</button>}
              </div>
              {pk && (
                <>
                  <p className="mu">Style line (added in front of every prompt): {pk.style_line}</p>
                  <ol>{pk.prompts.map((p) => <li key={p.n}><span className="mu">{p.section}</span> {p.prompt} <button className="btn g" onClick={() => void copy(`${pk.style_line} ${p.prompt}`, `prompt ${p.n}`)} aria-label={`Copy prompt ${p.n} with style line`}>Copy</button></li>)}</ol>
                </>
              )}
              {d.openai_pictures && pk && !d.meta.cleanup && (
                <div className="stack">
                  <button className="btn p" disabled={!!busy || !!t.running} onClick={() => void run("Making 2 pictures…", () => postJSON("/api/visuals/try", { slug: d.slug }))}>{t.running ? "Making 2 pictures, about a minute…" : (t.files ?? []).length ? "Try again (about 9 cents)" : "Try the first 2 pictures (about 9 cents)"}</button>
                  {(t.files ?? []).length > 0 && <div className="row">{(t.files ?? []).map((n) => <a key={n} href={`/media/${d.slug}/${n}?v=${t.v ?? 0}`} target="_blank" rel="noreferrer"><img src={`/media/${d.slug}/${n}?v=${t.v ?? 0}`} alt={`Test picture ${n}`} style={{ width: "100%", aspectRatio: "16/9", objectFit: "cover", borderRadius: 8 }} /></a>)}</div>}
                  {t.error && <p role="alert" className="mu">{t.error}</p>}
                </div>
              )}
            </div>
          )}
          <label htmlFor="vs-cam">Camera notes (optional). Leave empty: the camera operator chooses each move</label>
          <textarea id="vs-cam" className="field" rows={2} placeholder="slow pushes, handheld feel, always end on a pull out" value={camera} onChange={(e) => setCamera(e.target.value)} />
          <label htmlFor="vs-scene">Look notes (optional). Leave empty: the art director chooses the look from the song</label>
          <textarea id="vs-scene" className="field" rows={2} placeholder="monsoon night, warm lamps, nostalgic" value={scene} onChange={(e) => setScene(e.target.value)} />
        </>
      )}
      {note && <p className="mu" role="status">{note}</p>}
      {err && <p role="alert" className="mu">{err}</p>}
      <button className="btn p" disabled={!ok || !!busy} onClick={() => void run("Saving…", () => postJSON("/api/visuals/save", { slug: d.slug, mode: look === "flow" ? "flow" : "own", layout: look === "flow" ? "video" : look, camera, scene }))}>Save and continue</button>
    </section>
  );
}

import { useState } from "react";
import { postJSON, type SongDetail } from "../lib/api";
import { errText } from "../lib/songs";

type Pack = NonNullable<SongDetail["prompt_pack"]>;

// The picture prompts for Gemini or ChatGPT, one tab per picture, each one editable, plus a tab for the look and the people that every prompt shares.
// An edit is saved to the picture plan (the same words the pipeline paints from), so the owner can change a detail here and copy the result.
export function PromptTabs({ slug, pack, copy, done }: { slug: string; pack: Pack; copy: (text: string, what: string) => Promise<void>; done: () => Promise<unknown> | void }) {
  const [want, setTab] = useState<number>(pack.prompts[0]?.n ?? 0);   // 0 is the look tab
  const tab = want === 0 || pack.prompts.some((p) => p.n === want) ? want : (pack.prompts[0]?.n ?? 0);   // the plan was written again and this picture is gone
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false); const [err, setErr] = useState("");
  const val = (k: string, saved: string) => (k in draft ? draft[k] : saved);
  const edit = (k: string, v: string) => setDraft((o) => ({ ...o, [k]: v }));
  const sel = pack.prompts.find((p) => p.n === tab);
  const keys = tab === 0 ? ["style_line", "character"] : [`p${tab}`];
  const dirty = keys.some((k) => k in draft && draft[k].trim() !== (k === "style_line" ? pack.style_line : k === "character" ? (pack.character ?? "") : (sel?.prompt ?? "")).trim());
  const save = async () => {
    setBusy(true); setErr("");
    try {
      const body: Record<string, unknown> = { slug };
      if (tab === 0) { if ("style_line" in draft) body.style_line = draft.style_line; if ("character" in draft) body.character = draft.character; }
      else body.prompts = [{ n: tab, prompt: draft[`p${tab}`] }];
      await postJSON("/api/plan/save", body);
      setDraft((o) => { const n = { ...o }; for (const k of keys) delete n[k]; return n; });
      await done();
    } catch (e) { setErr(errText(e)); } finally { setBusy(false); }
  };
  const lines = (s?: string) => (s ? s.split("\n").filter(Boolean) : []);
  return (
    <div className="stack">
      <div className="tabs" role="tablist" aria-label="Pictures" style={{ flexWrap: "wrap" }}>
        {pack.prompts.map((p) => <button key={p.n} role="tab" id={`pt-${p.n}`} aria-selected={tab === p.n} aria-controls="pt-panel" onClick={() => setTab(p.n)}>{p.n}<span className="sr"> {p.section}</span>{`p${p.n}` in draft ? " •" : ""}</button>)}
        <button role="tab" id="pt-0" aria-selected={tab === 0} aria-controls="pt-panel" onClick={() => setTab(0)}>Look and people</button>
      </div>
      <div id="pt-panel" role="tabpanel" aria-labelledby={`pt-${tab}`} className="stack">
        {tab === 0 ? (
          <>
            <p className="mu">Added in front of every picture prompt, so the pictures look like one film and the same people come back.</p>
            <label htmlFor="pt-style">Style line</label>
            <textarea id="pt-style" className="field" rows={4} value={val("style_line", pack.style_line)} onChange={(e) => edit("style_line", e.target.value)} />
            <label htmlFor="pt-char">The people (repeated word for word in every picture)</label>
            <textarea id="pt-char" className="field" rows={6} value={val("character", pack.character ?? "")} onChange={(e) => edit("character", e.target.value)} />
          </>
        ) : sel ? (
          <>
            <h4 style={{ margin: 0 }}>Picture {sel.n}{sel.section ? ` · ${sel.section}` : ""}</h4>
            {lines(sel.lyric).length > 0 && <p className="mu">{lines(sel.lyric).join(" / ")}</p>}
            <label htmlFor={`pt-p${sel.n}`}>Prompt for picture {sel.n}</label>
            <textarea id={`pt-p${sel.n}`} className="field" rows={8} value={val(`p${sel.n}`, sel.prompt)} onChange={(e) => edit(`p${sel.n}`, e.target.value)} />
            {(sel.camera || sel.motion) && <p className="mu">{sel.camera ? `Camera: ${sel.camera.replace(/_/g, " ")}. ` : ""}{sel.motion ? `Moving: ${sel.motion}` : ""}</p>}
          </>
        ) : null}
        {err && <p role="alert" className="mu">{err}</p>}
        <div className="row">
          {sel && <button className="btn g" onClick={() => void copy(`${val("style_line", pack.style_line)} ${val(`p${sel.n}`, sel.prompt)}`, `prompt ${sel.n}`)} aria-label={`Copy prompt ${sel.n} with style line`}>Copy this prompt</button>}
          <button className="btn p" disabled={busy || !dirty} aria-busy={busy} onClick={() => void save()}>{busy ? "Saving…" : "Save my changes"}</button>
          {dirty && !busy && <button className="btn g" onClick={() => setDraft((o) => { const n = { ...o }; for (const k of keys) delete n[k]; return n; })}>Undo changes</button>}
        </div>
      </div>
    </div>
  );
}

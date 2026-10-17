import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fileB64, MAX_AUDIO_BYTES } from "../lib/files";
import { getJSON, postJSON, type SettingsData } from "../lib/api";
import { errText, itemPath } from "../lib/songs";

type Mode = "idea" | "import";

// Start something new: a song from an idea (or none), a song imported from Suno (its link, an MP3, or both), or an inspiration short from a quote or idea.
// Creating an item runs nothing; an import starts the pipeline, as the classic page does, so it says so.
export function NewItem({ type }: { type: "music" | "inspiration" }) {
  const go = useNavigate();
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<Mode>("idea");
  const [idea, setIdea] = useState("");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const song = type === "music";
  const [nar, setNar] = useState<{ key: boolean; voices: Record<string, string> } | null>(null); const [narrate, setNarrate] = useState(true); const [voice, setVoice] = useState("frank");
  useEffect(() => {   // an inspiration can start with the quote narrated by ElevenLabs: on by default when a key is saved
    if (!open || song) return;
    getJSON<SettingsData>("/api/settings").then((d) => { if (d?.media?.keys) { setNar({ key: !!d.media.keys.elevenlabs, voices: d.media.voices ?? {} }); setVoice(String(d.media.settings?.voice || "frank")); } }).catch(() => setNar(null));   // expected: without the settings the option is simply not offered
  }, [open, song]);
  const useNarr = !song && !!nar?.key && narrate;
  const done = (slug: string) => go(itemPath(type, slug) ?? "/");
  const create = async (e: React.FormEvent) => {
    e.preventDefault(); setErr("");
    if (!song && !idea.trim()) return setErr("Write the quote or the idea first.");
    setBusy(true);
    try { const r = await postJSON<{ slug: string }>("/api/new", { type, idea: idea.trim(), ...(useNarr ? { narrate: "eleven", voice } : {}) }); done(r.slug); } catch (x) { setErr(errText(x)); } finally { setBusy(false); }
  };
  const doImport = async (e: React.FormEvent) => {
    e.preventDefault(); setErr("");
    if (!url.trim() && !file) return setErr("Give the Suno link, an MP3, or both.");
    if (file && file.size > MAX_AUDIO_BYTES) return setErr("That file is over 22 MB.");
    setBusy(true);
    try {
      const body: Record<string, unknown> = { url: url.trim() };
      if (file) body.audio = { name: file.name, data: await fileB64(file) };
      const r = await postJSON<{ slug: string }>("/api/import", body); done(r.slug);
    } catch (x) { setErr(errText(x)); } finally { setBusy(false); }
  };
  if (!open) return <div className="row"><button className="btn p" onClick={() => setOpen(true)}>{song ? "New song" : "New inspiration"}</button></div>;
  return (
    <section className="card stack" aria-labelledby="new-h">
      <h2 id="new-h">{song ? "New song" : "New inspiration"}</h2>
      {song && (
        <div className="seg" role="group" aria-label="How to start" style={{ alignSelf: "flex-start" }}>
          <button aria-pressed={mode === "idea"} onClick={() => setMode("idea")}>Start from an idea</button>
          <button aria-pressed={mode === "import"} onClick={() => setMode("import")}>Import from Suno</button>
        </div>
      )}
      {mode === "idea" || !song ? (
        <form className="stack" onSubmit={(e) => void create(e)}>
          <label htmlFor="ni-idea">{song ? "Idea (optional)" : "Quote or idea"}</label>
          <textarea id="ni-idea" className="field" rows={3} value={idea} onChange={(e) => setIdea(e.target.value)} placeholder={song ? "A line about what the song is about" : "The quote, or what the short should say"} />
          {!song && nar && (
            <div className="stack" role="group" aria-label="Narration">
              <label className="row" style={{ gap: 10 }}><input type="checkbox" checked={useNarr} disabled={!nar.key} onChange={(e) => setNarrate(e.target.checked)} /> Narrate the quote with ElevenLabs</label>
              {nar.key ? (useNarr && <><label htmlFor="ni-voice">Voice</label><select id="ni-voice" className="field sel" value={voice} onChange={(e) => setVoice(e.target.value)}>{Object.entries(nar.voices).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></>)
                : <p className="mu">Paste an ElevenLabs key in Settings to add a voice. Without one the video has music and text only.</p>}
            </div>
          )}
          <div className="row"><button className="btn p" type="submit" disabled={busy}>{busy ? "Creating…" : "Create"}</button><button className="btn g" type="button" onClick={() => setOpen(false)}>Cancel</button></div>
        </form>
      ) : (
        <form className="stack" onSubmit={(e) => void doImport(e)}>
          <p className="mu">Importing starts the pipeline: it fetches the text and cover from the link, takes the audio from the MP3, and runs to the first approval.</p>
          <label htmlFor="ni-url">Suno link</label>
          <input id="ni-url" className="field" type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://suno.com/song/…" autoComplete="off" />
          <label htmlFor="ni-file">MP3 file (optional when you give the link; up to 22 MB)</label>
          <input id="ni-file" className="field" type="file" accept="audio/*,.mp3,.m4a,.wav,.flac" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          <div className="row"><button className="btn p" type="submit" disabled={busy}>{busy ? "Importing…" : "Import"}</button><button className="btn g" type="button" onClick={() => setOpen(false)}>Cancel</button></div>
        </form>
      )}
      {err && <p role="alert" className="mu">{err}</p>}
    </section>
  );
}

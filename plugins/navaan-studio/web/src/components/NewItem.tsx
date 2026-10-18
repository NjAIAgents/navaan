import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fileB64, MAX_AUDIO_BYTES } from "../lib/files";
import { getJSON, postJSON, type SettingsData } from "../lib/api";
import { errText, itemPath } from "../lib/songs";

type Mode = "idea" | "import";

// Start something new: a song from an idea (or none), a song imported from Suno (its link; the sound from the Suno page, or your own audio file), or an inspiration short from a quote or idea.
// Creating an item runs nothing; an import starts the pipeline, as the classic page does, so it says so.
export function NewItem({ type }: { type: "music" | "inspiration" | "aha" }) {
  const go = useNavigate();
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<Mode>("idea");
  const [idea, setIdea] = useState("");
  const [url, setUrl] = useState("");
  const [sunoUrl, setSunoUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [later, setLater] = useState(false); const [at, setAt] = useState("");   // publish when the pipeline finishes (default) or at a set time, US Central
  const song = type === "music";
  const [nar, setNar] = useState<{ key: boolean; voices: Record<string, string> } | null>(null); const [narrate, setNarrate] = useState(true); const [voice, setVoice] = useState("suno1");
  useEffect(() => {   // an inspiration can start with the quote narrated by ElevenLabs: on by default when a key is saved
    if (!open || song) return;
    getJSON<SettingsData>("/api/settings").then((d) => { if (d?.media?.keys) { setNar({ key: !!d.media.keys.elevenlabs, voices: d.media.voices ?? {} }); setVoice(String(d.media.settings?.voice || "suno1")); } }).catch(() => setNar(null));   // expected: without the settings the option is simply not offered
  }, [open, song]);
  const when = later && at ? { publish_at_ct: at } : {};
  const useNarr = !song && narrate;   // narration is a standard step: on unless this short skips it
  const done = (slug: string) => go(itemPath(type, slug) ?? "/");
  const create = async (e: React.FormEvent) => {
    e.preventDefault(); setErr("");
    if (!song && !idea.trim() && !sunoUrl.trim()) return setErr("Write the quote or the idea first, or paste a Suno link.");
    if (later && !at) return setErr("Pick the date and time to publish, or choose to publish when the pipeline finishes.");
    setBusy(true);
    try { const r = await postJSON<{ slug: string }>("/api/new", { type, ...when, idea: !song && sunoUrl.trim() ? "" : idea.trim(), ...(song ? {} : { ...(useNarr ? { narrate: "eleven", voice } : { narrate: "none" }), ...(sunoUrl.trim() ? { suno_url: sunoUrl.trim() } : {}) }) }); done(r.slug); } catch (x) { setErr(errText(x)); } finally { setBusy(false); }
  };
  const doImport = async (e: React.FormEvent) => {
    e.preventDefault(); setErr("");
    if (!url.trim()) return setErr("Add the Suno link: the title, lyrics and style are read from it.");
    if (later && !at) return setErr("Pick the date and time to publish, or choose to publish when the pipeline finishes.");
    if (file && file.size > MAX_AUDIO_BYTES) return setErr("That file is over 22 MB.");
    setBusy(true);
    try {
      const body: Record<string, unknown> = { url: url.trim(), ...when, ...(file ? { audio: { name: file.name, data: await fileB64(file) } } : {}) };
      const r = await postJSON<{ slug: string }>("/api/import", body); done(r.slug);
    } catch (x) { setErr(errText(x)); } finally { setBusy(false); }
  };
  if (!open) return <div className="row"><button className="btn p" onClick={() => setOpen(true)}>{song ? "New song" : type === "aha" ? "New Aha-lorithm short" : "New inspiration"}</button></div>;
  return (
    <section className="card stack" aria-labelledby="new-h">
      <h2 id="new-h">{song ? "New song" : type === "aha" ? "New Aha-lorithm short" : "New inspiration"}</h2>
      {song && (
        <div className="seg" role="group" aria-label="How to start" style={{ alignSelf: "flex-start" }}>
          <button aria-pressed={mode === "idea"} onClick={() => setMode("idea")}>Start from an idea</button>
          <button aria-pressed={mode === "import"} onClick={() => setMode("import")}>Import from Suno</button>
        </div>
      )}
      {mode === "idea" || !song ? (
        <form className="stack" onSubmit={(e) => void create(e)}>
          {!song && (
            <>
              <label htmlFor="ni-suno">Suno link (optional)</label>
              <input id="ni-suno" className="field" type="url" value={sunoUrl} onChange={(e) => setSunoUrl(e.target.value)} placeholder="https://suno.com/s/…" autoComplete="off" />
              <p className="mu">With a link, the words and the voice come from that Suno song, and the quote below is not needed. Without one, the quote is narrated by ElevenLabs.</p>
            </>
          )}
          <label htmlFor="ni-idea">{song ? "Idea (optional)" : "Quote or idea"}</label>
          <textarea id="ni-idea" className="field" rows={3} value={idea} disabled={!song && !!sunoUrl.trim()} onChange={(e) => setIdea(e.target.value)} placeholder={song ? "A line about what the song is about" : "The quote, or what the short should say"} />
          {!song && (
            <div className="stack" role="group" aria-label="Narration">
              <label className="row" style={{ gap: 10 }}><input type="checkbox" checked={narrate} onChange={(e) => setNarrate(e.target.checked)} /> {sunoUrl.trim() ? "Keep ElevenLabs as the backup voice" : "Narrate the quote with ElevenLabs"}</label>
              {narrate && nar && <><label htmlFor="ni-voice">Voice</label><select id="ni-voice" className="field sel" value={voice} onChange={(e) => setVoice(e.target.value)}>{Object.entries(nar.voices).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></>}
              {narrate && nar && !nar.key && !sunoUrl.trim() && <p className="mu" role="status">Paste an ElevenLabs key in Settings before this step runs. Untick the box to make this short with music and text only.</p>}
            </div>
          )}
          <fieldset className="stack" style={{ border: 0, padding: 0, margin: 0 }}>
            <legend><b>When should it be published?</b></legend>
            <label className="row" style={{ gap: 10 }}><input type="radio" name="ni-when" checked={!later} onChange={() => setLater(false)} /> When the pipeline finishes (after your approvals)</label>
            <label className="row" style={{ gap: 10 }}><input type="radio" name="ni-when" checked={later} onChange={() => setLater(true)} /> On a date and time I choose</label>
            {later && <><label htmlFor="ni-at">Date and time (Central Time, CST/CDT)</label><input id="ni-at" className="field" type="datetime-local" value={at} onChange={(e) => setAt(e.target.value)} /><p className="mu">YouTube and Instagram both go out then, once the approvals are given. You can change either time later on the item's Publishing schedule card.</p></>}
          </fieldset>
          <div className="row"><button className="btn p" type="submit" disabled={busy}>{busy ? "Creating…" : "Create"}</button><button className="btn g" type="button" onClick={() => setOpen(false)}>Cancel</button></div>
        </form>
      ) : (
        <form className="stack" noValidate onSubmit={(e) => void doImport(e)}>   {/* our own messages say what is missing, in one place, instead of the browser's bubble */}
          <p className="mu">The link gives the title, lyrics and style, and the sound is taken from the video on the Suno page. If you add an audio file instead, your file is the sound. Importing then starts the pipeline and runs to the first approval.</p>
          <label htmlFor="ni-url">Suno link (required)</label>
          <input id="ni-url" className="field" type="url" required aria-required="true" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://suno.com/song/… or https://suno.com/s/…" autoComplete="off" />
          <label htmlFor="ni-file">Audio file (optional; mp3, wav or m4a, up to 22 MB)</label>
          <input id="ni-file" className="field" type="file" accept="audio/*,.mp3,.m4a,.wav,.flac" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          <fieldset className="stack" style={{ border: 0, padding: 0, margin: 0 }}>
            <legend><b>When should it be published?</b></legend>
            <label className="row" style={{ gap: 10 }}><input type="radio" name="ni-when" checked={!later} onChange={() => setLater(false)} /> When the pipeline finishes (after your approvals)</label>
            <label className="row" style={{ gap: 10 }}><input type="radio" name="ni-when" checked={later} onChange={() => setLater(true)} /> On a date and time I choose</label>
            {later && <><label htmlFor="ni-at">Date and time (Central Time, CST/CDT)</label><input id="ni-at" className="field" type="datetime-local" value={at} onChange={(e) => setAt(e.target.value)} /><p className="mu">YouTube and Instagram both go out then, once the approvals are given. You can change either time later on the item's Publishing schedule card.</p></>}
          </fieldset>
          <div className="row"><button className="btn p" type="submit" disabled={busy}>{busy ? "Importing…" : "Import"}</button><button className="btn g" type="button" onClick={() => setOpen(false)}>Cancel</button></div>
        </form>
      )}
      {err && <p role="alert" className="mu">{err}</p>}
    </section>
  );
}

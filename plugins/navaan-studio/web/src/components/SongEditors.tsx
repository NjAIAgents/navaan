import { useEffect, useState } from "react";
import { postJSON, type SongDetail } from "../lib/api";
import { fileB64, MAX_AUDIO_BYTES } from "../lib/files";
import { errText, isShort } from "../lib/songs";

type Done = () => Promise<unknown> | void;

const FILES: [string, string][] = [["title.txt", "Title"], ["lyrics.txt", "Lyrics"], ["style.txt", "Style"], ["instagram.txt", "Instagram caption"], ["quote.json", "Quote"], ["tags.json", "Tags"], ["brief.md", "Brief"]];

// A draft survives a reload or a wrong tap: it is kept in this tab until it is saved.
const draftKey = (slug: string, name: string) => `navaan-draft:${slug}:${name}`;
const readDraft = (k: string) => { try { return sessionStorage.getItem(k); } catch { return null; } };   // expected: storage can be blocked
const writeDraft = (k: string, v: string | null) => { try { v === null ? sessionStorage.removeItem(k) : sessionStorage.setItem(k, v); } catch { /* expected: storage can be blocked */ } };

function FileEditor({ slug, name, label, saved, done }: { slug: string; name: string; label: string; saved: string; done: Done }) {
  const k = draftKey(slug, name);
  const [text, setText] = useState(() => readDraft(k) ?? saved);
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false); const [ok, setOk] = useState(false);
  const dirty = text !== saved;
  useEffect(() => { writeDraft(k, dirty ? text : null); }, [k, text, dirty]);
  useEffect(() => {
    if (!dirty) return;
    const h = (e: BeforeUnloadEvent) => { e.preventDefault(); };
    window.addEventListener("beforeunload", h); return () => window.removeEventListener("beforeunload", h);
  }, [dirty]);
  const save = async () => {
    setBusy(true); setErr(""); setOk(false);
    try { await postJSON("/api/save", { slug, file: name, content: text }); writeDraft(k, null); await done(); setOk(true); }
    catch (e) { setErr(errText(e)); } finally { setBusy(false); }
  };
  const id = `ed-${name}`;
  return (
    <details className="card stack">
      <summary><b>{label}</b>{dirty && <span className="chip wn"> Unsaved changes</span>}</summary>
      <label htmlFor={id}>{label}</label>
      <textarea id={id} className="field" rows={name === "lyrics.txt" ? 14 : 5} value={text} onChange={(e) => { setText(e.target.value); setOk(false); }} spellCheck={false} />
      <div className="row">
        <button className="btn p" disabled={busy || !dirty} onClick={() => void save()}>Save {label.toLowerCase()}</button>
        {dirty && <button className="btn g" disabled={busy} onClick={() => setText(saved)}>Discard changes</button>}
        {ok && !dirty && <span className="mu" role="status">Saved</span>}
      </div>
      {err && <p role="alert" className="mu">{err}</p>}
    </details>
  );
}

const IG_MAX = 2200; const YT_TITLE = 100; const YT_DESC_BYTES = 5000;
type YtText = { title?: string; description?: string; tags?: string[]; [k: string]: unknown };
const parseYt = (raw?: string): YtText | null => { try { const y = raw ? JSON.parse(raw) : null; return y && typeof y === "object" && !Array.isArray(y) ? y as YtText : null; } catch { return null; } };   // expected: a half-written file shows nothing

// The words that go out with the video: the Instagram caption and the YouTube title, description and tags. Written by the agent, changed here. An edit is checked on the server for what
// each platform accepts; a changed Instagram caption is approved again, since the approval is for the exact words.
export function PostTextEditor({ d, kind, done }: { d: SongDetail; kind: "instagram" | "youtube"; done: Done }) {
  const ig = kind === "instagram"; const raw = d.text?.[ig ? "instagram.txt" : "youtube.json"];
  const y = ig ? null : parseYt(raw);
  const savedBody = ig ? (raw ?? "") : (y?.description ?? ""); const savedTitle = y?.title ?? ""; const savedTags = (y?.tags ?? []).join(", ");
  const [body, setBody] = useState(savedBody); const [title, setTitle] = useState(savedTitle); const [tags, setTags] = useState(savedTags);
  const [seen, setSeen] = useState(`${savedBody}\u0000${savedTitle}\u0000${savedTags}`);
  const now = `${savedBody}\u0000${savedTitle}\u0000${savedTags}`;
  if (now !== seen) { setSeen(now); setBody(savedBody); setTitle(savedTitle); setTags(savedTags); }   // the saved text changed on the server (a new draft): show it
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false); const [ok, setOk] = useState(false);
  const dirty = body !== savedBody || title !== savedTitle || tags !== savedTags;
  if (!raw || (!ig && !y)) return <p className="mu">{ig ? "The Instagram caption" : "The YouTube text"} is not written yet. Run its step first.</p>;
  const bytes = new TextEncoder().encode(body).length;
  const save = async () => {
    setBusy(true); setErr(""); setOk(false);
    try {
      const content = ig ? body : JSON.stringify({ ...y, title: title.trim(), description: body, tags: tags.split(",").map((t) => t.trim()).filter(Boolean) }, null, 2) + "\n";
      await postJSON("/api/save", { slug: d.slug, file: ig ? "instagram.txt" : "youtube.json", content }); await done(); setOk(true);
    } catch (e) { setErr(errText(e)); } finally { setBusy(false); }
  };
  const id = `pt-${kind}`; const label = ig ? "Instagram caption" : "YouTube description";
  return (
    <div className="stack" role="group" aria-label={ig ? "Instagram caption" : "YouTube title, description and tags"}>
      {!ig && (<><label htmlFor={`${id}-t`}>YouTube title</label><input id={`${id}-t`} className="field" value={title} onChange={(e) => { setTitle(e.target.value); setOk(false); }} /><span className={title.length > YT_TITLE ? "chip bad" : "mu"}>{title.length} of {YT_TITLE}</span></>)}
      <label htmlFor={`${id}-b`}>{label}</label>
      <textarea id={`${id}-b`} className="field" rows={ig ? 8 : 10} value={body} onChange={(e) => { setBody(e.target.value); setOk(false); }} spellCheck />
      <span className={(ig ? body.length > IG_MAX : bytes > YT_DESC_BYTES) ? "chip bad" : "mu"}>{ig ? `${body.length.toLocaleString()} of ${IG_MAX.toLocaleString()} characters` : `${bytes.toLocaleString()} of ${YT_DESC_BYTES.toLocaleString()} bytes`}</span>
      {!ig && (<><label htmlFor={`${id}-g`}>Tags (separated by commas)</label><input id={`${id}-g`} className="field" value={tags} onChange={(e) => { setTags(e.target.value); setOk(false); }} /></>)}
      <div className="row">
        <button className="btn p" disabled={busy || !dirty} aria-busy={busy} onClick={() => void save()}>{busy ? "Saving…" : `Save the ${ig ? "caption" : "YouTube text"}`}</button>
        {dirty && !busy && <button className="btn g" onClick={() => { setBody(savedBody); setTitle(savedTitle); setTags(savedTags); }}>Discard changes</button>}
        {ok && !dirty && <span className="mu" role="status">Saved{ig ? ". Approve the caption again: the approval is for the exact words." : ""}</span>}
      </div>
      {err && <p role="alert" className="mu">{err}</p>}
    </div>
  );
}

export function TextEditors({ d, done }: { d: SongDetail; done: Done }) {
  const shown = FILES.filter(([n]) => n in d.text);
  const known = new Set([...FILES.map(([n]) => n), "youtube.json", "shots.json"]);
  const other = Object.keys(d.text ?? {}).filter((n) => !known.has(n)).sort();   // every other text file the server lets you edit, as the classic Text tab did
  if (!shown.length && !other.length && !parseYt(d.text?.["youtube.json"])) return null;
  return (
    <section className="sec" aria-labelledby="tx-h">
      <div className="sh"><h2 id="tx-h">Words and settings</h2></div>
      {shown.map(([n, l]) => <FileEditor key={`${d.slug}${n}`} slug={d.slug} name={n} label={l} saved={d.text[n]} done={done} />)}
      {parseYt(d.text?.["youtube.json"]) && <details className="card stack"><summary><b>YouTube title, description and tags</b></summary><PostTextEditor d={d} kind="youtube" done={done} /></details>}
      {other.length > 0 && <details className="card stack"><summary><b>Other files</b> <span className="mu">{other.length}</span></summary>{other.map((n) => <FileEditor key={`${d.slug}${n}`} slug={d.slug} name={n} label={n} saved={d.text[n]} done={done} />)}</details>}
    </section>
  );
}

type Shot = { label: string; start: number; end: number; image: string; camera: string; focus: [number, number]; scene: string; lyric: string };

export function ShotsEditor({ d, done }: { d: SongDetail; done: Done }) {
  const raw = d.text["shots.json"];
  const parsed = (() => { try { return raw ? JSON.parse(raw) as { shots: Shot[]; notes?: string } : null; } catch { return null; } })();   // expected: a half-written file shows nothing
  const [shots, setShots] = useState<Shot[]>(parsed?.shots ?? []);
  const [notes, setNotes] = useState(parsed?.notes ?? "");
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false); const [ok, setOk] = useState(false);
  const dirty = JSON.stringify({ shots, notes }) !== JSON.stringify({ shots: parsed?.shots ?? [], notes: parsed?.notes ?? "" });
  useEffect(() => {
    if (!dirty) return;
    const h = (e: BeforeUnloadEvent) => { e.preventDefault(); };
    window.addEventListener("beforeunload", h); return () => window.removeEventListener("beforeunload", h);
  }, [dirty]);
  if (!parsed) return null;
  const set = (i: number, p: Partial<Shot>) => { setOk(false); setShots(shots.map((s, j) => (j === i ? { ...s, ...p } : s))); };
  const save = async (approve = false) => {
    setBusy(true); setErr(""); setOk(false);
    try { await postJSON("/api/shots/save", { slug: d.slug, shots, notes }); if (approve) await postJSON("/api/approve", { slug: d.slug, gate: "shots" }); await done(); setOk(true); }
    catch (e) { setErr(errText(e)); } finally { setBusy(false); }
  };
  return (
    <section className="sec" aria-labelledby="sh-h">
      <div className="sh"><h2 id="sh-h">Shot list</h2><span className="n">{shots.length}</span></div>
      <div className="card stack">
        {shots.map((s, i) => (
          <fieldset key={i} className="stack">
            <legend>Shot {i + 1}{s.label ? ` · ${s.label}` : ""}</legend>
            {s.image && <img src={`/media/${d.slug}/images~${encodeURIComponent(s.image.split("/").pop() ?? "")}`} alt="" width={110} height={62} style={{ objectFit: "cover", borderRadius: 6 }} />}
            <div className="row">
              <label htmlFor={`s${i}a`}>Start (s)</label><input id={`s${i}a`} className="field" type="number" step="0.1" min="0" value={s.start} onChange={(e) => set(i, { start: Number(e.target.value) })} />
              <label htmlFor={`s${i}b`}>End (s)</label><input id={`s${i}b`} className="field" type="number" step="0.1" min="0" value={s.end} onChange={(e) => set(i, { end: Number(e.target.value) })} />
            </div>
            <label htmlFor={`s${i}i`}>Picture</label>
            <select id={`s${i}i`} className="field" value={s.image} onChange={(e) => set(i, { image: e.target.value })}>
              {!(d.images ?? []).some((x) => `images/${x}` === s.image) && <option value={s.image}>{s.image}</option>}
              {(d.images ?? []).map((x) => <option key={x} value={`images/${x}`}>{x}</option>)}
            </select>
            <label htmlFor={`s${i}c`}>Camera move</label>
            <select id={`s${i}c`} className="field" value={s.camera} onChange={(e) => set(i, { camera: e.target.value })}>
              {(d.cameras ?? []).map((x) => <option key={x} value={x}>{x.replace("_", " ")}</option>)}
            </select>
            <label htmlFor={`s${i}l`}>Label</label><input id={`s${i}l`} className="field" maxLength={60} value={s.label} onChange={(e) => set(i, { label: e.target.value })} />
            <label htmlFor={`s${i}n`}>What the viewer should feel</label><input id={`s${i}n`} className="field" maxLength={300} value={s.scene} onChange={(e) => set(i, { scene: e.target.value })} />
            {s.lyric && <p className="mu">{s.lyric}</p>}
            <button className="btn g" type="button" disabled={busy || shots.length < 2} onClick={() => { setOk(false); setShots(shots.filter((_, j) => j !== i)); }}>Remove shot {i + 1}</button>
          </fieldset>
        ))}
        <label htmlFor="shots-notes">Notes</label>
        <textarea id="shots-notes" className="field" rows={2} maxLength={600} value={notes} onChange={(e) => { setNotes(e.target.value); setOk(false); }} />
        <div className="row">
          <button className="btn p" disabled={busy || !dirty} onClick={() => void save()}>Save shot list</button>
          {d.next.type === "gate" && d.next.gate === "shots" && <button className="btn" disabled={busy} onClick={() => void save(true)}>Save and approve</button>}
          {dirty && <span className="chip wn">Unsaved changes</span>}
          {ok && !dirty && <span className="mu" role="status">Saved</span>}
        </div>
        {err && <p role="alert" className="mu">{err}</p>}
      </div>
    </section>
  );
}

export function NarrationCard({ d, done }: { d: SongDetail; done: Done }) {
  const [audio, setAudio] = useState<File | null>(null); const [srt, setSrt] = useState<File | null>(null); const [text, setText] = useState("");
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  const has = Object.keys(d.files ?? {}).some((f) => f.startsWith("narration"));
  const n = d.narrate; const [voice, setVoice] = useState(n?.voice ?? "suno1");
  const [pace, setPace] = useState(n?.pace ?? "slow");
  const [script, setScript] = useState(n?.script ?? ""); const [seen, setSeen] = useState(n?.script ?? "");
  if ((n?.script ?? "") !== seen) { setSeen(n?.script ?? ""); setScript(n?.script ?? ""); }   // the server's script changed (a new pace, a reset): show it
  const saveScript = async (text: string) => { setBusy(true); setErr(""); try { await postJSON("/api/narration/script", { slug: d.slug, text }); await done(); } catch (e) { setErr(errText(e)); } finally { setBusy(false); } };
  const eleven = async (on: boolean) => { setBusy(true); setErr(""); try { await postJSON("/api/narration/eleven", { slug: d.slug, on, voice, pace }); await done(); } catch (e) { setErr(errText(e)); } finally { setBusy(false); } };
  const upload = async () => {
    if (!audio) return setErr("Pick the narration audio first.");
    if (audio.size > MAX_AUDIO_BYTES) return setErr("That file is over 20 MB.");
    setBusy(true); setErr("");
    try { await postJSON("/api/narration/upload", { slug: d.slug, audio_name: audio.name, audio: await fileB64(audio), srt: srt ? await srt.text() : "", text }); setAudio(null); setSrt(null); setText(""); await done(); }
    catch (e) { setErr(errText(e)); } finally { setBusy(false); }
  };
  const remove = async () => { setBusy(true); setErr(""); try { await postJSON("/api/narration/remove", { slug: d.slug }); await done(); } catch (e) { setErr(errText(e)); } finally { setBusy(false); } };
  return (
    <section className="card stack" aria-labelledby="nr-h">
      <h2 id="nr-h">Narration</h2>
      {n && (
        <div className="stack" role="group" aria-label="Narrate with ElevenLabs">
          {n.from_suno && <p className="mu" role="status">The voice of this short is the Suno song's own sound. Narrating with ElevenLabs below is the backup: it replaces that voice.</p>}
          <h3>{n.from_suno ? "Backup: narrate the quote with ElevenLabs" : "Narrate the quote with ElevenLabs"}</h3>
          <p className="mu">Speaks the quote only (not the author). It is a standard step of every inspiration, and the spend is approved before it runs. You can skip it for one short.</p>
          <label htmlFor="nr-v">Voice</label>
          <select id="nr-v" className="field" value={voice} disabled={busy} onChange={(e) => setVoice(e.target.value)}>{Object.entries(n.voices).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
          <label htmlFor="nr-pace">Pace</label>
          <select id="nr-pace" className="field" value={pace} disabled={busy} onChange={(e) => setPace(e.target.value)}>{Object.entries(n.paces ?? { slow: "Slow (reflective)", calm: "Calm", normal: "Normal" }).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
          <label htmlFor="nr-script">Spoken script (what ElevenLabs reads)</label>
          <textarea id="nr-script" className="field" rows={7} value={script} disabled={busy} onChange={(e) => setScript(e.target.value)} />
          <p className="mu">Words in [brackets] set the tone ([warmly], [softly], [slowly]); … and [pause] make it slow down. Capital letters add stress on a word. None of this shows on screen. {n.script_custom ? "This is your edited script." : "This is the suggestion for the pace above."}</p>
          <div className="row">
            <button className="btn p" disabled={busy || !script.trim() || script.trim() === (n.script ?? "").trim()} onClick={() => void saveScript(script)}>Save the script</button>
            {n.script_custom && <button className="btn g" disabled={busy} onClick={() => void saveScript("")}>Back to the suggestion</button>}
          </div>
          <p className="mu">About {Math.round(n.estimate_s)} seconds of narration. This month {n.used_s} of {n.cap_s} seconds used.{!n.key && " Paste an ElevenLabs key in Settings first."}</p>
          <div className="row">
            <button className="btn p" disabled={busy || !n.key || n.estimate_s <= 0} onClick={() => void eleven(true)}>{n.on ? "Save the voice" : "Turn narration on"}</button>
            {n.on && <button className="btn g" disabled={busy} onClick={() => void eleven(false)}>Skip narration for this short</button>}
          </div>
          {n.on ? <p className="mu" role="status">On: the "Narrate the quote" step runs with {n.voices[n.voice] ?? n.voice}.</p> : <p className="mu" role="status">Skipped: this short has music and text only.</p>}
          <hr />
        </div>
      )}
      <p className="mu">Your own voice recording for this short. With a timed .srt the timing is known; without it, write the words one line per row.</p>
      <label htmlFor="nr-a">Audio (mp3, wav, m4a or aac)</label>
      <input id="nr-a" className="field" type="file" accept="audio/*,.mp3,.wav,.m4a,.aac" disabled={busy} onChange={(e) => setAudio(e.target.files?.[0] ?? null)} />
      <label htmlFor="nr-s">Subtitles (.srt, optional)</label>
      <input id="nr-s" className="field" type="file" accept=".srt" disabled={busy} onChange={(e) => setSrt(e.target.files?.[0] ?? null)} />
      {!srt && <><label htmlFor="nr-t">Words, one line per row</label><textarea id="nr-t" className="field" rows={4} value={text} onChange={(e) => setText(e.target.value)} /></>}
      <div className="row">
        <button className="btn p" disabled={busy} onClick={() => void upload()}>Attach narration</button>
        {has && <button className="btn g" disabled={busy} onClick={() => void remove()}>Remove narration</button>}
      </div>
      {err && <p role="alert" className="mu">{err}</p>}
    </section>
  );
}

// The owner's own track under the voice. Free tracks (for example from pixabay.com/music, under its Content License) work; the licence of each track is the owner's to check. ffmpeg fits it to the video and the renderer keeps it quiet under the voice.
export function MusicCard({ d, done }: { d: SongDetail; done: Done }) {
  const [file, setFile] = useState<File | null>(null); const [err, setErr] = useState(""); const [note, setNote] = useState(""); const [busy, setBusy] = useState(false);
  const m = d.music;
  const send = async (path: string, body: Record<string, unknown>) => { setBusy(true); setErr(""); setNote(""); try { const r = await postJSON<{ redo?: string }>(path, { slug: d.slug, ...body }); setFile(null); if (r?.redo) setNote(`The video is approved, so it keeps its old sound. To use this, Redo "${r.redo}" in the steps.`); await done(); } catch (e) { setErr(errText(e)); } finally { setBusy(false); } };
  const upload = async () => {
    if (!file) return setErr("Pick the music file first.");
    if (file.size > MAX_AUDIO_BYTES) return setErr("That file is over 20 MB.");
    await send("/api/music/upload", { name: file.name, audio: await fileB64(file) });
  };
  return (
    <section className="card stack" aria-labelledby="bm-h">
      <h2 id="bm-h">Background music</h2>
      <p className="mu">A quiet track under the voice. ffmpeg trims it to the length of the video, fades it in and out and levels it; the voice stays on top. Use a track you may use: free tracks from pixabay.com/music work under its Content License, and the licence of each track is yours to check.</p>
      {m ? (
        <div className="stack" role="status"><p>Using <b>{m.name}</b> ({Math.round(m.seconds)} s). It is trimmed to the video.</p><div className="row"><button className="btn g" disabled={busy} onClick={() => void send("/api/music/remove", {})}>Remove the music</button></div></div>
      ) : <p className="mu" role="status">No background music: the short has the voice and the text only.</p>}
      <label htmlFor="bm-f">{m ? "Use a different track" : "Music file (mp3, wav, m4a, aac, flac or ogg)"}</label>
      <input id="bm-f" className="field" type="file" accept="audio/*,.mp3,.wav,.m4a,.aac,.flac,.ogg" disabled={busy} onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      <div className="row"><button className="btn p" disabled={busy || !file} onClick={() => void upload()}>{m ? "Replace the music" : "Add the music"}</button></div>
      {note && <p className="mu" role="status">{note}</p>}
      {err && <p role="alert" className="mu">{err}</p>}
    </section>
  );
}

// The made files, playable. A file archived to the bucket and cleaned locally is fetched back by the server when it is first played.
export function MediaCard({ d }: { d: SongDetail }) {
  const names = Object.keys(d.files ?? {});
  const audio = names.filter((n) => n.endsWith(".mp3")); const video = names.filter((n) => n.endsWith(".mp4"));
  const archived = d.cloud && !audio.length && !isShort(d.meta.type);
  if (!audio.length && !video.length && !archived) return null;
  const url = (n: string) => `/media/${d.slug}/${n}`;
  return (
    <section className="sec" aria-labelledby="md-h">
      <div className="sh"><h2 id="md-h">Made files</h2></div>
      <div className="card stack">
        {archived && <><p className="mu">The audio is archived in the bucket. Playing it brings it back (the first play can take a moment).</p><audio controls preload="none" src={url("final.mp3")} aria-label="final.mp3" /></>}
        {audio.map((n) => <div key={n} className="stack"><span>{n}</span><audio controls preload="none" src={url(n)} aria-label={n} /><a href={url(n)} target="_blank" rel="noreferrer">Open {n}</a></div>)}
        {video.map((n) => <div key={n} className="stack"><span>{n.replace("clips~", "clip ")}</span><video controls preload="none" playsInline style={{ maxWidth: "100%" }} src={url(n)} aria-label={n} /><a href={url(n)} target="_blank" rel="noreferrer">Open {n}</a></div>)}
      </div>
    </section>
  );
}

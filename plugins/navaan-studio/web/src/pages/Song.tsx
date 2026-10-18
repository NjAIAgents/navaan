import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Equaliser } from "../components/Equaliser";
import { KeepCard } from "../components/KeepCard";
import { ShareCard } from "../components/ShareCard";
import { Icon } from "../components/Icon";
import { PipelineRail } from "../components/PipelineRail";
import { StepDetail } from "../components/StepDetail";
import { StepStatus } from "../components/StepStatus";
import { useMobile } from "../components/useMobile";
import type { SetGate } from "../components/GateSwitch";
import { ShotsPreview } from "../components/ShotsPreview";
import { MoodCard } from "../components/MoodCard";
import { PosterCard } from "../components/PosterCard";
import { VisualsCard } from "../components/VisualsCard";
import { SongAnalytics } from "../components/SongAnalytics";
import { ScheduleCard } from "../components/SchedulePanel";
import { MediaCard, MusicCard, NarrationCard, PostTextEditor, ShotsEditor, TextEditors } from "../components/SongEditors";
import { usePlayer } from "../lib/player";
import { getJSON, postJSON, type Question, type SongDetail } from "../lib/api";
import { fmtCentral } from "../lib/datetime";
import { fileB64, MAX_AUDIO_BYTES } from "../lib/files";
import { GATE_ASK, GATE_FILE, RISKY, gateTitle, stepLabel } from "../lib/gates";
import { classic, errText, nextAction } from "../lib/songs";
import { Loading } from "../components/Loading";

type Act = (path: string, body: Record<string, unknown>) => Promise<boolean>;

// The videos at "Review the videos", in the order they are looked at, with what each is called and what it is for. The key is what the server calls it when feedback is about that one video.
const VIDEOS: [string, string, string][] = [["final_16x9.mp4", "full", "Full video"], ["final_reel_9x16.mp4", "reel", "Reel without lyrics"], ["final_reel_9x16_cap.mp4", "reel_lyrics", "Reel with lyrics"]];

function GateCard({ d, gate, act, busy, running = false, stopping = false, onStop, reload }: { d: SongDetail; gate: string; act: Act; busy: boolean; running?: boolean; stopping?: boolean; onStop?: () => void; reload?: () => Promise<unknown> | void }) {
  const [confirm, setConfirm] = useState(false);
  const [changing, setChanging] = useState(false);
  const [note, setNote] = useState("");
  const [about, setAbout] = useState(""); const [nudge, setNudge] = useState("");
  const file = GATE_FILE[gate];
  const at = d.steps.find((x) => x.gate_before === gate && x.scheduled_for)?.scheduled_for ?? "";   // a publish step with a time: approving it now does not publish now
  // What you are approving is shown here, not a tab away: the videos for "Review the videos", the song for "Listen". The size in the address stops a browser from playing an older file with the same name.
  const names = Object.keys(d.files ?? {}); const url = (n: string) => `/media/${d.slug}/${n}?v=${d.files[n]}`;
  const rank = (n: string) => { const i = VIDEOS.findIndex(([f]) => f === n); return i < 0 ? 9 : i; };
  const videos = gate === "media" ? names.filter((n) => n.endsWith(".mp4") && !n.startsWith("clips~")).sort((x, y) => rank(x) - rank(y)) : [];
  const named = d.meta.type !== "inspiration" ? VIDEOS.filter(([f]) => videos.includes(f)) : [];   // songs: feedback names one of these; an inspiration has a single video
  const hasLyricReel = videos.includes("final_reel_9x16_cap.mp4"); const lyricsOn = d.reel_lyrics?.on !== false;
  const songs = gate === "listen" ? names.filter((n) => n === "final.mp3") : [];
  const spends = gate === "credits" ? d.steps.filter((x) => x.spends && !x.done && x.spends_what).map((x) => x.spends_what as string) : [];
  const shown = file ? d.text[file] : "";
  const ok = async (path: string, body: Record<string, unknown>) => { if (await act(path, { slug: d.slug, gate, ...body })) { setConfirm(false); setChanging(false); setNote(""); setAbout(""); setNudge(""); } };
  const needAbout = named.length > 1;   // with several videos the note must say which one, so only that one is made again
  return (
    <section className="card gate" aria-labelledby="gate-h">
      <span className="chip wn"><span className="dot" />Waiting for you</span>
      <h2 id="gate-h">{gateTitle(gate)}</h2>
      {gate === "credits" && spends.length ? (
        <><p>I approve spending on exactly this:</p><ul className="spend-list">{spends.map((t) => <li key={t}>{t}</li>)}</ul></>
      ) : <p>{at ? SCHEDULED_ASK[gate]?.(fmtCentral(at)) ?? GATE_ASK[gate] : GATE_ASK[gate] ?? "Approve to move this song forward."}</p>}
      <p className="mu">{running ? "A run is waiting for this approval. Stop it if you need to change something earlier." : "Nothing is running: it is paused here until you decide. To change something first, use Redo on a step in the list."}</p>
      <div className="actbar">
        {changing ? (
          <form className="stack" onSubmit={(e) => { e.preventDefault(); void ok("/api/request-changes", { note, ...(needAbout ? { video: about, ...(about === "reel_lyrics" && nudge.trim() ? { offset: Number(nudge) } : {}) } : {}) }); }}>
            {needAbout && (
              <fieldset className="stack" style={{ border: 0, padding: 0, margin: 0 }}>
                <legend><b>Which video is this about?</b></legend>
                <span className="mu">Only that video is made again.</span>
                {named.map(([, k, label]) => <label key={k} className="row" style={{ gap: 8 }}><input type="radio" name="about" value={k} checked={about === k} onChange={() => setAbout(k)} /> {label}</label>)}
              </fieldset>
            )}
            {about === "reel_lyrics" && (
              <><label htmlFor="nudge">Lyrics early or late? Move them by (seconds: + later, − earlier; leave empty to keep)</label>
              <input id="nudge" className="field" type="number" step="0.1" min={-10} max={10} value={nudge} onChange={(e) => setNudge(e.target.value)} style={{ maxWidth: 160 }} /></>
            )}
            <label htmlFor="note">What should change?</label>
            <textarea id="note" className="field" rows={3} required value={note} onChange={(e) => setNote(e.target.value)} />
            <div className="row">
              <button className="btn p" type="submit" disabled={busy || !note.trim() || (needAbout && !about)}>{needAbout ? "Send back and make that video again" : "Send back"}</button>
              <button className="btn g" type="button" onClick={() => setChanging(false)}>Cancel</button>
            </div>
          </form>
        ) : confirm ? (
          <div className="stack" role="group" aria-label="Confirm approval">
            <p className="mu">This {gate === "credits" || gate === "suno_download" || gate === "captions_setup" ? "spends credits or downloads tools" : "reaches the outside world or cannot be undone"}. Approve it?</p>
            <div className="row">
              <button className="btn p" disabled={busy} onClick={() => void ok("/api/approve", {})}>Yes, approve</button>
              <button className="btn g" onClick={() => setConfirm(false)}>Not yet</button>
            </div>
          </div>
        ) : (
          <>
          {hasLyricReel && (
            <fieldset className="stack" style={{ border: 0, padding: 0, margin: 0 }}>
              <legend><b>Instagram reel</b></legend>
              <label className="row" style={{ gap: 8 }}><input type="radio" name="iglyrics" checked={lyricsOn} disabled={busy} onChange={() => void act("/api/reel/lyrics", { on: true })} /> With lyrics</label>
              <label className="row" style={{ gap: 8 }}><input type="radio" name="iglyrics" checked={!lyricsOn} disabled={busy} onChange={() => void act("/api/reel/lyrics", { on: false })} /> Without lyrics <span className="mu">(use this while the lyrics are out of sync)</span></label>
            </fieldset>
          )}
          <div className="row">
            <button className="btn p" disabled={busy} onClick={() => (RISKY.has(gate) ? setConfirm(true) : void ok("/api/approve", {}))}>Approve</button>
            <button className="btn" disabled={busy} onClick={() => setChanging(true)}>Request changes</button>
            {running && onStop && <button className="btn g" disabled={busy || stopping} onClick={onStop}>{stopping ? "Stopping…" : "Stop the run"}</button>}
          </div>
          </>
        )}
      </div>
      {(gate === "quote" || gate === "media") && d.meta.type === "inspiration" && d.narrate && !d.narrate.on && !Object.keys(d.files ?? {}).some((f) => f.startsWith("voiceover")) && (
        <p className="mu" role="note">There is no narration on this short, so the video has music and text only. To add a voice, use the Narration card below.</p>
      )}
      {videos.length > 0 && (
        <div className="vrow" aria-label="The videos, side by side">
          {videos.map((n) => { const label = VIDEOS.find(([f]) => f === n)?.[2] ?? n; return <figure key={n} className={`stack vfig${n.includes("16x9") ? " wide" : ""}`}><video controls playsInline preload="metadata" src={url(n)} aria-label={label} /><figcaption><b>{label}</b> <span className="mu">{n}</span></figcaption></figure>; })}
        </div>
      )}
      {songs.map((n) => <audio key={n} controls preload="none" src={url(n)} aria-label={n} />)}
      {gate === "shots" && <ShotsPreview d={d} />}
      {gate === "instagram_caption" && <PostTextEditor d={d} kind="instagram" done={reload ?? (() => undefined)} />}
      {gate === "publish_youtube" && <PostTextEditor d={d} kind="youtube" done={reload ?? (() => undefined)} />}
      {gate === "shots" && shown ? <details><summary>The raw shot list</summary><pre className="art" tabIndex={0} aria-label="shots.json, what you are approving">{shown}</pre></details> : file && gate !== "instagram_caption" && (shown ? (Readable[gate]?.(shown) ?? <pre className="art" tabIndex={0} aria-label={`${file}, what you are approving`}>{shown}</pre>) : <p className="mu">{file} is not there yet. Run its step first.</p>)}
    </section>
  );
}

// The agent asked a question and waits. Some answers need the text box (a file name, a note); the server checks that and says so.
function QuestionCard({ q, act, busy }: { q: Question; act: Act; busy: boolean }) {
  const [text, setText] = useState("");
  const [err, setErr] = useState("");
  const flagged = q.options.some((o) => o.text);
  const answer = async (choice: string | null, needsText: boolean) => {
    if (needsText && !text.trim()) return setErr("Type the answer in the box first.");
    setErr(""); await act("/api/answer", { choice, text });
  };
  return (
    <section className="card stack" aria-labelledby="q-h">
      <h2 id="q-h">The agent is asking you</h2>
      <p>{q.text}</p>
      {(q.allow_text || flagged) && <><label htmlFor="q-text">Your answer</label><textarea id="q-text" className="field" rows={2} value={text} onChange={(e) => setText(e.target.value)} /></>}
      <div className="row">
        {q.options.length ? q.options.map((o) => <button key={o.id} className="btn" disabled={busy} onClick={() => void answer(o.id, o.text)}>{o.label}</button>)
          : <button className="btn p" disabled={busy} onClick={() => void answer(null, true)}>Send answer</button>}
      </div>
      {err && <p role="alert" className="mu">{err}</p>}
    </section>
  );
}

// Suno gave the server a file it could not read: the MP3 can be uploaded here and the import carries on.
function SunoUpload({ why, act, busy }: { why: string; act: Act; busy: boolean }) {
  const [err, setErr] = useState("");
  const pick = async (f: File | undefined) => {
    if (!f) return;
    if (f.size > MAX_AUDIO_BYTES) return setErr("That file is over 22 MB.");
    setErr(""); await act("/api/suno/audio", { name: f.name, data: await fileB64(f) });
  };
  return (
    <section className="card stack" aria-labelledby="su-h">
      <h2 id="su-h">Upload the song's MP3</h2>
      <p>Suno gave the server a file it cannot read. Download the MP3 from Suno while signed in, then pick it here. The import carries on by itself.</p>
      {why && <p className="mu">{why}</p>}
      <label htmlFor="su-file">MP3 file (up to 22 MB)</label>
      <input id="su-file" className="field" type="file" accept="audio/*,.mp3,.m4a,.wav,.flac" disabled={busy} onChange={(e) => void pick(e.target.files?.[0])} />
      {err && <p role="alert" className="mu">{err}</p>}
    </section>
  );
}

// What you have approved, with a way to take an approval back. The gate opens again and the history records who and when.
function Approvals({ d, act, busy }: { d: SongDetail; act: Act; busy: boolean }) {
  const [asking, setAsking] = useState<string | null>(null);
  const given = Object.entries(d.approvals);
  if (!given.length) return null;
  return (
    <section className="sec" aria-labelledby="ap-h">
      <div className="sh"><h2 id="ap-h">Approved</h2><span className="n">{given.length}</span></div>
      <ul className="card hist">
        {given.map(([g, a]) => (
          <li key={g} className="stp">
            <span className="tx"><b>{gateTitle(g)}</b><span className="mu"> · {a.via.replace(/^ui:/, "")} · {new Date(a.at).toLocaleString()}</span></span>
            {asking === g
              ? <span className="row" role="group" aria-label={`Confirm revoking ${gateTitle(g)}`}><button className="btn p" disabled={busy} onClick={() => void act("/api/revoke", { gate: g }).then(() => setAsking(null))}>Yes, revoke</button><button className="btn g" onClick={() => setAsking(null)}>Keep</button></span>
              : <button className="btn g" disabled={busy} onClick={() => setAsking(g)} aria-label={`Revoke approval of ${gateTitle(g)}`}>Revoke</button>}
          </li>
        ))}
      </ul>
    </section>
  );
}

// A history line is "<time> <text>", or, in songs from before the move, an object with at, event and note.
const when = (h: NonNullable<SongDetail["meta"]["history"]>[number]) => {
  if (typeof h !== "string") {
    const ms = Date.parse(String(h?.at ?? ""));
    const text = [String(h?.event ?? "").replace(/_/g, " "), h?.note ? String(h.note) : ""].filter(Boolean).join(": ");
    return { at: Number.isNaN(ms) ? "" : new Date(ms).toLocaleString(), text: text || "event" };
  }
  const [t, ...rest] = h.split(" "); const ms = Date.parse(t);
  return Number.isNaN(ms) ? { at: "", text: h } : { at: new Date(ms).toLocaleString(), text: rest.join(" ") };
};

// Delete an item that is not published: asked twice, and said in words what happens (its files are moved, not erased). A published item shows why it cannot be deleted instead.
function DeleteItem({ d, act, busy, onGone }: { d: SongDetail; act: Act; busy: boolean; onGone: () => void }) {
  const [ask, setAsk] = useState(false);
  const del = d.deletable;
  if (!del) return null;
  if (!del.ok) return <p className="mu" role="note">Cannot be deleted. {del.why}</p>;
  return ask ? (
    <div className="stack" role="alertdialog" aria-label={`Confirm deleting ${d.slug}`}>
      <p>Delete {d.slug}? It disappears from the list and nothing runs for it any more. Its files are moved to a _deleted folder inside songs, not erased, but the app has no way to bring it back.</p>
      <div className="row">
        <button className="btn p" disabled={busy} onClick={() => void act("/api/delete", {}).then((ok) => { if (ok) onGone(); })}>Yes, delete {d.slug}</button>
        <button className="btn g" onClick={() => setAsk(false)}>Keep it</button>
      </div>
    </div>
  ) : <div className="row"><button className="btn" disabled={busy} onClick={() => setAsk(true)}>Delete this {d.meta.type === "inspiration" ? "inspiration" : "song"}</button></div>;
}

// What an approval card shows, as words a person reads rather than the file behind it. The raw file stays one click away.
const parse = (t: string): Record<string, unknown> | null => { try { const v = JSON.parse(t); return v && typeof v === "object" ? v as Record<string, unknown> : null; } catch { return null; } };   // expected: not JSON shows the raw file
const RawFile = ({ text, name }: { text: string; name: string }) => <details><summary>The raw file</summary><pre className="art" tabIndex={0} aria-label={name}>{text}</pre></details>;
const Readable: Record<string, (text: string) => React.ReactNode | null> = {
  quote: (t) => { const q = parse(t); if (!q) return null; const lines = Array.isArray(q.lines) && q.lines.length ? q.lines as string[] : [String(q.text ?? "")];
    return <div className="stack"><blockquote className="quote-view">{lines.map((l, i) => <span key={i}>{l}</span>)}</blockquote><p className="mu">{q.author ? `By ${q.author}` : "Original line"}{q.language ? ` · ${String(q.language).toUpperCase()}` : ""}{q.notes ? ` · ${q.notes}` : ""}</p><RawFile text={t} name="quote.json" /></div>; },
  originality: (t) => { const o = parse(t); if (!o) return null; const clear = o.verdict === "clear" || o.safe_to_publish === true; const m = Array.isArray(o.matches) ? o.matches as { url?: string; title?: string; note?: string }[] : [];
    return <div className="stack"><p><span className={`chip ${clear ? "ok" : "wn"}`}><span className="dot" />{clear ? "Clear: no earlier use of these words found" : "Check this: similar wording found"}</span></p>{o.recommendation ? <p>{String(o.recommendation)}</p> : null}
      {m.length > 0 && <ul className="matches">{m.map((x, i) => <li key={i}><a href={x.url} target="_blank" rel="noreferrer">{x.title || x.url}</a>{x.note && <span className="mu"> · {x.note}</span>}</li>)}</ul>}<RawFile text={t} name="originality.json" /></div>; },
};

// What a publish approval says when the step has a time: it is approved now and goes out then, never "now".
const SCHEDULED_ASK: Record<string, (when: string) => string> = {
  go_public: (w) => `Make the YouTube video and Short public ${w}, as scheduled. Approving now does not publish now.`,
  publish_instagram: (w) => `Post the Reel to Instagram ${w}, as scheduled. Approving now does not post now.`,
};

// The item's state in plain words, not the pipeline's internal names (media_ready, quote_ok).
const STATE_WORDS: Record<string, string> = { drafted: "Started", lyrics_ok: "Lyrics approved", accepted: "Song approved", quote_ok: "Quote approved", media_ready: "Video ready for review", approved: "Videos approved", published: "Published" };

// Top right of the page: when it goes out. A time (Central), "Published", or "When it finishes" with a way to set a time.
function GoesOut({ d, onChange }: { d: SongDetail; onChange: () => void }) {
  const s = d.meta.schedule; const at = [s?.youtube_at, s?.instagram_at].filter(Boolean) as string[];
  const both = !!(s?.youtube_at && s?.instagram_at); const where = both ? "YouTube + Instagram" : s?.youtube_at ? "YouTube" : "Instagram";
  if (d.meta.state === "published" && (!s || s.done)) return <div className="goes ok" role="status"><span className="k">Published</span>{" "}<span className="v">YouTube and Instagram</span></div>;
  if (s && !s.done && at.length) {
    const first = at.slice().sort()[0];
    return <button type="button" className="goes" onClick={onChange}><span className="k">Goes out</span>{" "}<span className="v">{fmtCentral(first).replace(/^today/, "Today")}</span>{" "}<span className="w">{where} · <b>Change</b></span></button>;
  }
  return <button type="button" className="goes off" onClick={onChange}><span className="k">Goes out</span>{" "}<span className="v">When it finishes</span>{" "}<span className="w"><b>Set a time</b></span></button>;
}

// Everything is approved and the rest waits for its publishing time: say so in one calm card, with both platforms and the links.
function AllSet({ d, onChange }: { d: SongDetail; onChange: () => void }) {
  const s = d.meta.schedule!; const yt = (d.meta.published?.youtube_items ?? []).find((x) => x.url);
  const at = [s.youtube_at, s.instagram_at].filter(Boolean).sort()[0] as string;
  return (
    <section className="card stack allset" aria-labelledby="allset-h">
      <span className="chip ok"><span className="dot" />All set</span>
      <h2 id="allset-h">Goes out {fmtCentral(at)}</h2>
      <p className="mu">Every approval is given. The studio publishes on its own at that time; you do not need to keep this page open.</p>
      <ul className="allset-p">
        {s.youtube_at && <li><b>YouTube</b><span className="mu">{yt ? "uploaded, private until then" : "uploads first, private"} · {fmtCentral(s.youtube_at)}</span>{yt?.url && <a href={yt.url} target="_blank" rel="noreferrer">{yt.url.replace(/^https?:\/\//, "")} <Icon name="external" /></a>}</li>}
        {s.instagram_at && <li><b>Instagram</b><span className="mu">the Reel posts {fmtCentral(s.instagram_at)}</span></li>}
      </ul>
      <div className="row"><button className="btn" onClick={onChange}>Change the time</button></div>
    </section>
  );
}

const LANE_TITLE: Record<string, string> = { youtube: "YouTube", instagram: "Instagram" };

// After the videos are approved, YouTube and Instagram each have a lane of their own: each shows its own next step or approval, and neither waits for the other.
function LanesView({ d, act, busy, pending, running, stopping, onStop, reload }: { d: SongDetail; act: Act; busy: boolean; pending: boolean; running: boolean; stopping: boolean; onStop: () => void; reload: () => Promise<unknown> | void }) {
  const lanes = d.lanes ?? {};
  // The approval cards get `pending` (a request in flight), not `busy`: a run waiting at an approval counts as running, and it must not lock the button it is waiting for.
  return (
    <div className="lanes" aria-label="Publishing lanes">
      {(["youtube", "instagram"] as const).filter((l) => lanes[l]).map((l) => {
        const nx = lanes[l]; const mine = d.steps.filter((x) => x.lane === l); const done = mine.filter((x) => x.done && x.status === "done").length;
        return (
          <section key={l} className="stack lane" aria-labelledby={`lane-${l}`}>
            <div className="row"><h2 id={`lane-${l}`}>{LANE_TITLE[l]}</h2><span className="n">{done}/{mine.length}</span></div>
            {nx.type === "gate" && nx.gate
              ? <GateCard key={`${l}-${nx.gate}`} d={d} gate={nx.gate} act={act} busy={pending} running={running} stopping={stopping} onStop={onStop} reload={reload} />
              : <section className="card stack live"><StepStatus kind={running ? "later" : "next"} /><h3>{stepLabel(nx.step)}</h3>
                  <div className="row"><button className="btn p" disabled={busy} onClick={() => void act("/api/run", { step: nx.step })}>Run {stepLabel(nx.step)}</button></div>
                  <p className="mu">Only this lane moves. The {l === "youtube" ? "Instagram" : "YouTube"} lane keeps its own place.</p></section>}
          </section>
        );
      })}
    </div>
  );
}

// What a click said it would do, in words, while it is being done and once it is done. Shown as a status message so no button press goes unanswered.
const sayFor = (path: string, b: Record<string, unknown>): [string, string] => {
  const st = stepLabel(String(b.step ?? "")); const g = gateTitle(String(b.gate ?? ""));
  switch (path) {
    case "/api/approve": return ["Approving…", `Approved: ${g}.`];
    case "/api/request-changes": return ["Sending it back…", b.video ? "Sent back. That video is being made again." : "Sent back with your note. Nothing runs until you press Run."];
    case "/api/redo": return [`Starting the redo of ${st}…`, `Redo started: ${st}.`];
    case "/api/restart": return [`Restarting from ${st}…`, `Restarting from ${st}.`];
    case "/api/run": return ["Starting…", b.all ? "Running to the next approval." : "Running one step."];
    case "/api/delete": return ["Deleting…", `Deleted ${String(b.slug ?? "")}.`];
    case "/api/stop": return ["Stopping…", "Stop requested. The step ends in a moment."];
    case "/api/revoke": return ["Taking the approval back…", `Approval taken back: ${g}.`];
    case "/api/answer": return ["Sending your answer…", "Answer sent. The run carries on."];
    case "/api/reel/lyrics": return ["Saving…", "Saved."];
    default: return ["Working…", "Done."];
  }
};
const STARTS = new Set(["/api/run", "/api/redo", "/api/restart"]);

export default function Song() {
  const { slug = "" } = useParams();
  const go = useNavigate();
  const [sp, setSp] = useSearchParams();
  const [d, setD] = useState<SongDetail | null>(null);
  const [err, setErr] = useState("");
  const [pending, setPending] = useState(false);
  const pl = usePlayer();
  const load = useCallback(() => getJSON<SongDetail>(`/api/song/${slug}`).then((x) => { setD(x); setErr(""); }).catch((e) => setErr(errText(e))), [slug]);
  useEffect(() => { void load(); }, [load]);
  const running = !!(d?.job.running || d?.job.queued);
  const making = !!(d?.try?.running || d?.vertical?.running || d?.poster?.running);   // a test or 9:16 picture is being made by a background thread
  useEffect(() => { if (!running && !making) return; const t = setInterval(() => void load(), 3000); return () => clearInterval(t); }, [running, making, load]);

  const stepParam = sp.get("step");
  useEffect(() => { if (stepParam) document.getElementById("sd-h")?.scrollIntoView?.({ block: "nearest" }); }, [stepParam]);   // a hook, so it sits above the early returns: a step was opened, bring its detail into view (on a phone it is above the list)
  const [notice, setNotice] = useState("");
  useEffect(() => { if (!notice || /…$/.test(notice)) return; const t = setTimeout(() => setNotice(""), 8000); return () => clearTimeout(t); }, [notice]);   // a finished message goes away by itself; one still being done stays
  const [stopping, setStopping] = useState(false);
  const mobile = useMobile(); const [pane, setPane] = useState<"now" | "steps">("now");   // a phone shows what needs you or the steps, not both stacked into one long page
  useEffect(() => { if (!running) setStopping(false); }, [running]);   // the run really ended: the button goes back to normal
  const stop = async () => { setStopping(true); if (!(await act("/api/stop", {}))) setStopping(false); };
  const act: Act = async (path, body) => {
    const [doing, did] = sayFor(path, { slug, ...body });
    setPending(true); setNotice(doing);
    try {
      const r = await postJSON<{ started?: boolean }>(path, { slug, ...body }); setErr(""); await load();
      setNotice(STARTS.has(path) && r?.started === false ? "Nothing started: a run is already going. Press Stop first if you want to change it." : did); return true;
    }
    catch (e) { setErr(errText(e)); setNotice(""); return false; }
    finally { setPending(false); }
  };

  if (!d) return err ? <div className="card" role="alert"><h2>Could not load this song</h2><p className="mu">{err}</p><Link className="btn" to="/studio/songs">Back to Songs</Link></div> : <Loading />;

  const title = d.text["title.txt"]?.trim() || slug;
  const insp = d.meta.type === "inspiration"; const list = insp ? "/studio/inspiration" : "/studio/songs";
  const coverFile = insp ? "thumb_9x16.jpg" : "cover_1x1.png"; const cover = (d.files ?? {})[coverFile] ? `/media/${slug}/${coverFile}?w=160&v=${d.files[coverFile]}` : "";   // the song's cover (an inspiration: its reel's first frame) beside the title
  const gate = d.next.type === "gate" ? d.next.gate : undefined;
  const busy = pending || running;
  const history = [...(d.meta.history ?? [])].reverse().slice(0, 30);
  const published = d.meta.type !== "inspiration" && d.meta.state === "published";
  const needsYou = !!(gate || d.question || d.needs_you || d.failure);
  const selId = d.steps.some((x) => x.id === sp.get("step")) ? (sp.get("step") as string) : "";   // a step opened from the list
  const pick = (id: string) => { const n = new URLSearchParams(sp); if (n.get("step") === id) n.delete("step"); else n.set("step", id); setSp(n, { replace: true }); };
  const eventsFor = (id: string) => { const st = d.steps.find((x) => x.id === id); const gs = [st?.gate_before, st?.gate_after].filter(Boolean); return history.map(when).filter((w) => w.text.includes(`step ${id} `) || w.text.includes(`step ${id}`) && /\b(done|failed)\b/.test(w.text) || gs.some((g) => w.text.includes(`gate ${g} `))); };

  const runStep = d.run?.step || (d.next.type === "run" ? d.next.step ?? "" : "");   // the step that is running, from the run itself (the status text can lag a step behind)
  const ranBefore = (id: string) => eventsFor(id).find((e) => e.text.includes(`step ${id} done`))?.at ?? "";
  const setGate: SetGate = async (g, on) => { setPending(true); setNotice("Saving…"); try { await postJSON("/api/settings/gates_save", { gates: { [g]: on } }); setErr(""); await load(); setNotice(on ? `${gateTitle(g)} will ask you again.` : `${gateTitle(g)} will approve itself from now on.`); return true; } catch (e) { setErr(errText(e)); setNotice(""); return false; } finally { setPending(false); } };   // the same switch as Settings, Approvals that approve themselves: it applies to every song

  // The one thing that needs you now: exactly one card, never an approval and a "Running" chip side by side.
  const sch = d.meta.schedule; const timed = (id?: string) => !!id && !!d.steps.find((x) => x.id === id)?.scheduled_for;
  const allSet = !!sch && !sch.done && !gate && !running && !d.question && !d.needs_you && (d.lanes && Object.keys(d.lanes).length ? Object.values(d.lanes).every((l) => l.type === "run" && timed(l.step)) : d.next.type === "run" && timed(d.next.step));   // nothing left but the publishing time
  const hasLanes = !allSet && !!d.lanes && Object.keys(d.lanes).length > 0;   // the videos are approved: the publishing steps run in their own lanes, shown under a failure card too, so a waiting approval is never hidden
  const runCard = (
    <section className="card stack live" aria-labelledby="run-h">
      <StepStatus kind="running" run={d.run} usual={d.meta.step_seconds?.[runStep]} />
      <h2 id="run-h">{runStep ? stepLabel(runStep) : d.status_text || "Working…"}</h2>
      <div className="row"><button className="btn" disabled={stopping} onClick={() => void stop()}>{stopping ? "Stopping…" : "Stop"}</button></div>
    </section>
  );
  const now = d.failure ? (
    <section className="card fail stack live" role="alert" aria-labelledby="fail-h">
      <span className="chip bad"><span className="dot" />Failed</span>
      <h2 id="fail-h">{stepLabel(d.failure.step) || "A step"} failed</h2>
      <p>{d.failure.plain || d.failure.error || "It did not finish."}</p>
      <div className="row">
        {d.failure.step
          ? <button className="btn p" disabled={busy} onClick={() => void act("/api/redo", { step: d.failure!.step })}>Retry {stepLabel(d.failure.step)}</button>
          : <button className="btn p" disabled={busy} onClick={() => void act("/api/run", { all: true })}>Run again{d.next.type === "run" && d.next.step ? `: ${stepLabel(d.next.step)}` : ""}</button>}   {/* the run was stopped (a restart) before any step was named: carry on from the next step */}
        <a className="btn g" href={classic(slug)}>Full log in the classic view <Icon name="external" /></a>
      </div>
      <DeleteItem d={d} act={act} busy={busy} onGone={() => go(list)} />
      <details><summary>The raw error, for the log</summary>
        {d.failure.error && <pre className="art" tabIndex={0}>{d.failure.error}</pre>}
        <p className="mu">Log reference <code>{d.failure.ref}</code> (search it in the app log as <code>job_id</code>).</p>
      </details>
    </section>
  ) : d.question ? <QuestionCard key={d.question.id} q={d.question} act={act} busy={busy} />
  : d.needs_you ? <section className="card" role="status"><h2>Waiting for you</h2><p>{d.needs_you}</p><a className="btn" href={classic(slug)}>Open in the classic view <Icon name="external" /></a></section>
  : d.meta.source === "suno_import" && d.meta.suno?.auto_failed && !(d.files ?? {})["final.mp3"] ? <SunoUpload why={d.meta.suno.auto_failed} act={act} busy={busy} />
  : allSet ? <AllSet d={d} onChange={() => setSp({ tab: "publish" }, { replace: true })} />
  : hasLanes ? (running && !d.status_text?.startsWith("waiting for you") ? runCard : null)   // a run waiting at an approval shows that approval, not a spinner saying Running
  : running && !gate ? runCard : gate === "visuals_mode" ? <VisualsCard d={d} done={load} />
  : gate ? <GateCard key={gate} d={d} gate={gate} act={act} busy={pending} running={running} stopping={stopping} onStop={() => void stop()} reload={load} />
  : d.next.type === "run" ? (
    <section className="card stack live"><StepStatus kind={ranBefore(d.next.step ?? "") ? "stale" : "next"} /><h2>{stepLabel(d.next.step ?? "")}</h2>
      {ranBefore(d.next.step ?? "") && <p className="mu">It ran before ({ranBefore(d.next.step ?? "")}). Something it depends on changed, so it will run again.</p>}
      <div className="row"><button className="btn p" disabled={busy} onClick={() => void act("/api/run", { all: true })}>Run to the next approval</button><button className="btn" disabled={busy} onClick={() => void act("/api/run", { all: false })}>Run one step</button></div>
    </section>
  ) : d.next.type === "done" ? <section className="card"><h2>All steps are done</h2></section> : null;

  const TABS = [["pipeline", "Pipeline"], ["content", "Content"], ["media", "Media"], ["publish", "Publish"], ["activity", "Activity"]] as const;
  type Tab = (typeof TABS)[number][0];
  const asked = sp.get("tab"); const tab: Tab = TABS.some(([k]) => k === asked) ? (asked as Tab) : "pipeline";
  return (
    <>
      <div className="ph hd">
        {cover && <img className="ph-cover" src={cover} alt="" width={insp ? 54 : 96} height={96} />}
        <div className="ph-tx">
          <Link className="back" to={list}><Icon name="chevron" />{insp ? "Inspiration" : "Songs"}</Link>
          <h1 className="disp">{title}{pl.slug === slug && pl.playing && <> <Equaliser /></>}</h1>
          <p>{STATE_WORDS[d.meta.state ?? ""] ?? "New"} · {nextAction({ status: gate ? "approval" : d.next.type === "done" ? "done" : "production", next: d.next, published: false })} · <span className="mu">{slug}</span></p>
        </div>
        <GoesOut d={d} onChange={() => setSp({ tab: "publish" }, { replace: true })} />
      </div>
      {notice && <div className="toast" role="status" aria-live="polite">{/…$/.test(notice) && <span className="spin" aria-hidden="true" />}<span>{notice}</span></div>}
      {err && <div className="card" role="alert"><h2>That did not work</h2><p className="mu">{err}</p></div>}
      <div className="tabs" role="tablist" aria-label="Sections">
        {TABS.map(([k, l]) => (
          <button key={k} role="tab" id={`tab-${k}`} aria-selected={tab === k} aria-controls={`panel-${k}`} onClick={() => setSp(k === "pipeline" ? {} : { tab: k }, { replace: true })}>
            {l}{k === "pipeline" && needsYou && <span className="dot" role="img" aria-label="needs you" />}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} className="stack">
        {tab === "pipeline" && (d.notes ?? []).map((n) => <section key={n} className="card row" role="note"><p style={{ margin: 0, flex: "1 1 260px" }}>{n}</p><button className="btn" onClick={() => setSp({ tab: "content" }, { replace: true })}>Open Content</button></section>)}
        {tab === "pipeline" && (
          <div className="pl-grid">
            {mobile && (
              <div className="seg pane" role="group" aria-label="Show">
                <button aria-pressed={pane === "now"} onClick={() => setPane("now")}>Now</button>
                <button aria-pressed={pane === "steps"} onClick={() => setPane("steps")}>Steps <span className="mu">{d.steps.filter((x) => x.done).length}/{d.steps.length}</span></button>
              </div>
            )}
            {(!mobile || pane === "steps") && <PipelineRail d={d} act={act} busy={busy} selected={selId} onSelect={(id) => { pick(id); if (mobile) setPane("now"); }} />}
            {(!mobile || pane === "now") && <div className="pl-now stack">{now}{hasLanes && <LanesView d={d} act={act} busy={busy} pending={pending} reload={load} running={running} stopping={stopping} onStop={() => void stop()} />}{selId && <StepDetail d={d} id={selId} events={eventsFor(selId)} onBack={() => pick(selId)} done={load} setGate={setGate} busy={busy} />}</div>}
          </div>
        )}
        {tab === "content" && (<>
          <TextEditors d={d} done={load} />
          <ShotsEditor key={slug} d={d} done={load} />
          {insp && <NarrationCard d={d} done={load} />}
          {insp && <MusicCard d={d} done={load} />}
        </>)}
        {tab === "media" && (<>
          <MediaCard d={d} />
          <PosterCard d={d} done={load} />
          {d.meta.type !== "inspiration" && <MoodCard d={d} done={load} />}
        </>)}
        {tab === "publish" && (<>
          {published && (
            <section className="card row" aria-label="Play">
              <button className="btn p" onClick={() => void pl.toggle(slug, title)}>{pl.slug === slug && pl.playing ? "Pause" : "Play"}<span className="sr"> {title}</span></button>
              <span className="mu">Plays straight from the bucket.</span>
            </section>
          )}
          {published && <KeepCard slug={slug} />}
          {published && <ShareCard slug={slug} />}
          {!(d.meta.published?.instagram && !d.meta.schedule) && !(d.next.type === "done" && !d.meta.schedule) && <ScheduleCard slug={slug} type={d.meta.type ?? "music"} schedule={d.meta.schedule} done={load} />}
          {published && <SongAnalytics slug={slug} />}
        </>)}
        {tab === "activity" && (<>
          <Approvals d={d} act={act} busy={busy} />
          <section className="sec" aria-labelledby="del-h"><div className="sh"><h2 id="del-h">Delete</h2></div><div className="card stack"><DeleteItem d={d} act={act} busy={busy} onGone={() => go(list)} /></div></section>
          <section className="sec" aria-labelledby="hist-h">
            <div className="sh"><h2 id="hist-h">History</h2></div>
            <ul className="card hist">
              {history.length ? history.map((h, i) => { const w = when(h); return <li key={i}><span className="mu">{w.at}</span> {w.text}</li>; }) : <li className="mu">Nothing yet.</li>}
            </ul>
          </section>
        </>)}
      </div>
    </>
  );
}

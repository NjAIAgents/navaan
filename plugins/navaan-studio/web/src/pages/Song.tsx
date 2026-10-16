import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Equaliser } from "../components/Equaliser";
import { KeepCard } from "../components/KeepCard";
import { ShareCard } from "../components/ShareCard";
import { Icon } from "../components/Icon";
import { VisualsCard } from "../components/VisualsCard";
import { MediaCard, NarrationCard, ShotsEditor, TextEditors } from "../components/SongEditors";
import { usePlayer } from "../lib/player";
import { getJSON, postJSON, type Question, type SongDetail, type Step } from "../lib/api";
import { fileB64, MAX_AUDIO_BYTES } from "../lib/files";
import { GATE_ASK, GATE_FILE, RISKY, gateTitle, stepLabel } from "../lib/gates";
import { classic, errText, nextAction } from "../lib/songs";

type Act = (path: string, body: Record<string, unknown>) => Promise<boolean>;

function GateCard({ d, gate, act, busy }: { d: SongDetail; gate: string; act: Act; busy: boolean }) {
  const [confirm, setConfirm] = useState(false);
  const [changing, setChanging] = useState(false);
  const [note, setNote] = useState("");
  const file = GATE_FILE[gate];
  const shown = file ? d.text[file] : "";
  const ok = async (path: string, body: Record<string, unknown>) => { if (await act(path, { slug: d.slug, gate, ...body })) { setConfirm(false); setChanging(false); setNote(""); } };
  return (
    <section className="card gate" aria-labelledby="gate-h">
      <span className="chip wn"><span className="dot" />Waiting for you</span>
      <h2 id="gate-h">{gateTitle(gate)}</h2>
      <p>{GATE_ASK[gate] ?? "Approve to move this song forward."}</p>
      {file && (shown ? <pre className="art" tabIndex={0} aria-label={`${file}, what you are approving`}>{shown}</pre> : <p className="mu">{file} is not there yet. Run its step first.</p>)}
      {changing ? (
        <form className="stack" onSubmit={(e) => { e.preventDefault(); void ok("/api/request-changes", { note }); }}>
          <label htmlFor="note">What should change?</label>
          <textarea id="note" className="field" rows={3} required value={note} onChange={(e) => setNote(e.target.value)} />
          <div className="row">
            <button className="btn p" type="submit" disabled={busy || !note.trim()}>Send back</button>
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
        <div className="row">
          <button className="btn p" disabled={busy} onClick={() => (RISKY.has(gate) ? setConfirm(true) : void ok("/api/approve", {}))}>Approve</button>
          <button className="btn" disabled={busy} onClick={() => setChanging(true)}>Request changes</button>
        </div>
      )}
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

function StepRow({ s, failed }: { s: Step; failed: boolean }) {
  const chip = failed ? <span className="chip bad">Failed</span> : s.status === "done" ? <span className="chip ok"><Icon name="check" />Done</span> : s.status === "waiting for approval" ? <span className="chip wn">Needs approval</span> : <span className="chip">{s.status === "ready" ? "Ready" : "Later"}</span>;
  return <li className="stp"><span className="tx">{stepLabel(s.id)}{s.spends && <span className="mu"> · spends credits</span>}</span>{chip}</li>;
}

const when = (h: string) => {
  const [t, ...rest] = h.split(" "); const ms = Date.parse(t);
  return Number.isNaN(ms) ? { at: "", text: h } : { at: new Date(ms).toLocaleString(), text: rest.join(" ") };
};

export default function Song() {
  const { slug = "" } = useParams();
  const [d, setD] = useState<SongDetail | null>(null);
  const [err, setErr] = useState("");
  const [pending, setPending] = useState(false);
  const pl = usePlayer();
  const load = useCallback(() => getJSON<SongDetail>(`/api/song/${slug}`).then((x) => { setD(x); setErr(""); }).catch((e) => setErr(errText(e))), [slug]);
  useEffect(() => { void load(); }, [load]);
  const running = !!(d?.job.running || d?.job.queued);
  const making = !!(d?.try?.running || d?.vertical?.running);   // a test or 9:16 picture is being made by a background thread
  useEffect(() => { if (!running && !making) return; const t = setInterval(() => void load(), 3000); return () => clearInterval(t); }, [running, making, load]);

  const act: Act = async (path, body) => {
    setPending(true);
    try { await postJSON(path, { slug, ...body }); setErr(""); await load(); return true; }
    catch (e) { setErr(errText(e)); return false; }
    finally { setPending(false); }
  };

  if (!d) return err ? <div className="card" role="alert"><h2>Could not load this song</h2><p className="mu">{err}</p><Link className="btn" to="/studio/songs">Back to Songs</Link></div> : <p className="mu" role="status">Loading…</p>;

  const title = d.text["title.txt"]?.trim() || slug;
  const insp = d.meta.type === "inspiration"; const list = insp ? "/studio/inspiration" : "/studio/songs";
  const gate = d.next.type === "gate" ? d.next.gate : undefined;
  const busy = pending || running;
  const history = [...(d.meta.history ?? [])].reverse().slice(0, 30);
  return (
    <>
      <div className="ph">
        <Link className="back" to={list}><Icon name="chevron" />{insp ? "Inspiration" : "Songs"}</Link>
        <h1 className="disp">{title}{pl.slug === slug && pl.playing && <> <Equaliser /></>}</h1>
        <p>{slug} · {d.meta.state ?? "new"} · {nextAction({ status: gate ? "approval" : d.next.type === "done" ? "done" : "production", next: d.next, published: false })}</p>
      </div>
      {err && <div className="card" role="alert"><h2>That did not work</h2><p className="mu">{err}</p></div>}
      {d.failure && (
        <section className="card fail" role="alert" aria-labelledby="fail-h">
          <h2 id="fail-h">{stepLabel(d.failure.step) || "A step"} failed</h2>
          {d.failure.error && <p>{d.failure.error}</p>}
          <p className="mu">Log reference <code>{d.failure.ref}</code> (search it in the app log as <code>job_id</code>).</p>
          <div className="row">
            <button className="btn p" disabled={busy || !d.failure.step} onClick={() => void act("/api/redo", { step: d.failure!.step })}>Retry {stepLabel(d.failure.step)}</button>
            <a className="btn g" href={classic(slug)}>Full log in the classic view <Icon name="external" /></a>
          </div>
        </section>
      )}
      {d.question && <QuestionCard key={d.question.id} q={d.question} act={act} busy={busy} />}
      {!d.question && d.needs_you && <section className="card" role="status"><h2>Waiting for you</h2><p>{d.needs_you}</p><a className="btn" href={classic(slug)}>Open in the classic view <Icon name="external" /></a></section>}
      {d.meta.source === "suno_import" && d.meta.suno?.auto_failed && !(d.files ?? {})["final.mp3"] && <SunoUpload why={d.meta.suno.auto_failed} act={act} busy={busy} />}
      {running ? (
        <section className="card" role="status"><span className="chip ac"><span className="dot" />Running</span><p>{d.status_text || "Working…"}</p><button className="btn" onClick={() => void act("/api/stop", {})}>Stop</button></section>
      ) : gate === "visuals_mode" ? (
        <VisualsCard d={d} done={load} />
      ) : gate ? (
        <GateCard key={gate} d={d} gate={gate} act={act} busy={busy} />
      ) : d.next.type === "run" && !d.failure ? (
        <section className="card"><h2>Next: {stepLabel(d.next.step ?? "")}</h2>
          <div className="row"><button className="btn p" disabled={busy} onClick={() => void act("/api/run", { all: true })}>Run to the next approval</button><button className="btn" disabled={busy} onClick={() => void act("/api/run", { all: false })}>Run one step</button></div>
        </section>
      ) : null}
      {d.meta.type !== "inspiration" && d.meta.state === "published" && (
        <section className="card row" aria-label="Play">
          <button className="btn p" onClick={() => void pl.toggle(slug, title)}>{pl.slug === slug && pl.playing ? "Pause" : "Play"}<span className="sr"> {title}</span></button>
          <span className="mu">Plays straight from the bucket.</span>
        </section>
      )}
      {d.meta.type !== "inspiration" && d.meta.state === "published" && <KeepCard slug={slug} />}
      {d.meta.type !== "inspiration" && d.meta.state === "published" && <ShareCard slug={slug} />}
      <MediaCard d={d} />
      <TextEditors d={d} done={load} />
      <ShotsEditor key={slug} d={d} done={load} />
      {insp && <NarrationCard d={d} done={load} />}
      <section className="sec" aria-labelledby="steps-h">
        <div className="sh"><h2 id="steps-h">Steps</h2><span className="n">{d.steps.filter((s) => s.done).length}/{d.steps.length}</span></div>
        <ol className="card steps">{d.steps.map((s) => <StepRow key={s.id} s={s} failed={d.failure?.step === s.id} />)}</ol>
      </section>
      <Approvals d={d} act={act} busy={busy} />
      <section className="sec" aria-labelledby="hist-h">
        <div className="sh"><h2 id="hist-h">History</h2></div>
        <ul className="card hist">
          {history.length ? history.map((h, i) => { const w = when(h); return <li key={i}><span className="mu">{w.at}</span> {w.text}</li>; }) : <li className="mu">Nothing yet.</li>}
        </ul>
      </section>
    </>
  );
}

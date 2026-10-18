import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Icon } from "./Icon";
import { ApiError, postJSON } from "../lib/api";
import { errText } from "../lib/songs";

type Reaction = "up" | "down" | "love";
const KEY = (slug: string) => `navaan-react:${slug}`;
const remembered = (slug: string): Reaction | null => { try { const v = localStorage.getItem(KEY(slug)); return v === "up" || v === "down" || v === "love" ? v : null; } catch { return null; } };   // expected: storage can be blocked
const remember = (slug: string, r: Reaction | null) => { try { if (r) localStorage.setItem(KEY(slug), r); else localStorage.removeItem(KEY(slug)); } catch { /* expected: storage can be blocked */ } };

function B({ r, mine, press, label, children }: { r: Reaction; mine: Reaction | null; press: (r: Reaction) => Promise<void>; label: string; children: React.ReactNode }) {
  return <button className={"btn" + (mine === r ? " p" : "")} aria-pressed={mine === r} onClick={() => void press(r)} aria-label={label}>{children}</button>;
}

// Thumbs up, thumbs down, and double thumbs up ("Love it") on a song, and a way to write to us. Pressing the same one again takes it back. Only counts reach the server, nothing about the visitor;
// the choice is remembered in the browser so the button stays pressed. Nobody sees the totals here: they are for the owner.
export function SongFeedback({ slug, title, bare = false, onForm }: { slug: string; title: string; bare?: boolean; onForm?: () => void }) {   // bare: inside a sheet; onForm: the sheet opens the message form itself, so two dialogs never stack
  const [mine, setMine] = useState<Reaction | null>(() => remembered(slug)); const [err, setErr] = useState(""); const [form, setForm] = useState(false); const [hint, setHint] = useState(false);
  const openForm = () => (onForm ? onForm() : setForm(true));
  useEffect(() => { setMine(remembered(slug)); setHint(false); }, [slug]);
  const press = async (r: Reaction) => {
    setErr(""); const next = mine === r ? null : r;
    try {
      await postJSON("/api/site/react", { slug, reaction: next, previous: mine ?? undefined });   // taking one back sends no new reaction: the old count goes down
      remember(slug, next); setMine(next); setHint(next === "down");
    } catch (e) { setErr(e instanceof ApiError ? e.message : errText(e)); }
  };
  return (
    <div className={bare ? "stack" : "card stack"} {...(bare ? {} : { role: "region", "aria-labelledby": "fb-h" })}>
      {!bare && <h2 id="fb-h">What did you think?</h2>}
      <div className="row" role="group" aria-label={`React to ${title}`}>
        <B r="up" mine={mine} press={press} label="Thumbs up"><Icon name="thumb" /></B>
        <B r="love" mine={mine} press={press} label="Love it (double thumbs up)"><span className="dbl" aria-hidden="true"><Icon name="thumb" /><Icon name="thumb" /></span></B>
        <B r="down" mine={mine} press={press} label="Thumbs down"><span style={{ display: "flex", transform: "scaleY(-1)" }}><Icon name="thumb" /></span></B>
        <button className="btn g" onClick={openForm}><Icon name="mail" /> Send feedback</button>
      </div>
      {hint && <p className="mu" role="status">Sorry it missed. <button className="linkish" onClick={openForm}>Tell us what to improve</button> (optional).</p>}
      {err && <p role="alert" className="mu">{err}</p>}
      {form && <FeedbackForm slug={slug} title={title} onClose={() => setForm(false)} />}
    </div>
  );
}

// A message to the owner. The email is optional, only for a reply. Nothing else is asked or kept.
export function FeedbackForm({ slug, title, onClose }: { slug?: string; title?: string; onClose: () => void }) {
  const [message, setMessage] = useState(""); const [email, setEmail] = useState(""); const [hp, setHp] = useState(""); const [busy, setBusy] = useState(false); const [err, setErr] = useState(""); const [sent, setSent] = useState(false);
  const x = useRef<HTMLButtonElement>(null);
  useEffect(() => { x.current?.focus(); const k = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); }; document.addEventListener("keydown", k); return () => document.removeEventListener("keydown", k); }, [onClose]);
  const send = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setErr("");
    try { await postJSON("/api/site/feedback", { slug, message, email: email.trim() || undefined, website: hp }); setSent(true); } catch (x2) { setErr(errText(x2)); } finally { setBusy(false); }
  };
  return createPortal(
    <>
      <div className="scrim" onClick={onClose} />
      <div className="card dlg stack" role="dialog" aria-modal="true" aria-labelledby="ff-h">
        <div className="row"><h2 id="ff-h" style={{ flex: 1 }}>{title ? `Feedback on ${title}` : "Send feedback"}</h2><button ref={x} className="btn g sq" onClick={onClose} aria-label="Close"><Icon name="close" /></button></div>
        {sent ? <><p role="status">Thank you. It has been sent.</p><div className="row"><button className="btn p" onClick={onClose}>Close</button></div></> : (
          <form className="stack" onSubmit={(e) => void send(e)}>
            <label htmlFor="ff-msg">Your message</label>
            <textarea id="ff-msg" className="field" rows={5} value={message} onChange={(e) => setMessage(e.target.value)} maxLength={2000} placeholder="What did you like? What would you change?" required />
            <label htmlFor="ff-email">Your email <span className="mu">(optional, only if you want a reply)</span></label>
            <input id="ff-email" className="field" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} maxLength={254} />
            <div aria-hidden="true" style={{ position: "absolute", left: -9999, height: 0, overflow: "hidden" }}><label>Website<input tabIndex={-1} autoComplete="off" value={hp} onChange={(e) => setHp(e.target.value)} /></label></div>
            <p className="mu">We keep your message, and your email if you give one, only to read it and reply. Ask us to delete it any time.</p>
            {err && <p role="alert" className="mu">{err}</p>}
            <div className="row"><button className="btn p" type="submit" disabled={busy || !message.trim()}>{busy ? "Sending…" : "Send"}</button><button className="btn g" type="button" onClick={onClose}>Cancel</button></div>
          </form>
        )}
      </div>
    </>,
    document.body,
  );
}

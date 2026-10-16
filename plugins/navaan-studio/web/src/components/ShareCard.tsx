import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Icon } from "./Icon";
import { postJSON } from "../lib/api";
import { errText } from "../lib/songs";
import { useMe } from "../lib/me";

type Link = { token: string; url: string };

/** Where a link can be sent. Each opens that service's own share page in a new tab. */
export const targets = (title: string, url: string): { name: string; href: string }[] => {
  const t = encodeURIComponent(`${title} on NAVAAN`), u = encodeURIComponent(url), both = encodeURIComponent(`${title} on NAVAAN ${url}`);
  return [
    { name: "WhatsApp", href: `https://wa.me/?text=${both}` },
    { name: "X", href: `https://twitter.com/intent/tweet?text=${t}&url=${u}` },
    { name: "Facebook", href: `https://www.facebook.com/sharer/sharer.php?u=${u}` },
    { name: "Threads", href: `https://www.threads.net/intent/post?text=${both}` },
    { name: "Telegram", href: `https://t.me/share/url?url=${u}&text=${t}` },
    { name: "LinkedIn", href: `https://www.linkedin.com/sharing/share-offsite/?url=${u}` },
    { name: "Reddit", href: `https://www.reddit.com/submit?url=${u}&title=${t}` },
    { name: "Email", href: `mailto:?subject=${t}&body=${both}` },
  ];
};

// The platforms, the phone's own share sheet where there is one, and copy.
export function ShareLinks({ title, url }: { title: string; url: string }) {
  const [copied, setCopied] = useState(false);
  const native = typeof navigator !== "undefined" && typeof navigator.share === "function";
  const copy = async () => { try { await navigator.clipboard.writeText(url); setCopied(true); } catch { setCopied(false); } };   // expected: clipboard can be blocked; the box below still selects the link
  return (
    <div className="stack">
      <label htmlFor="share-url" className="mu">{url.includes("/s/") ? "Anyone with this link hears a 30 second preview." : "Anyone with this link can listen."}</label>
      <input id="share-url" className="field" readOnly value={url} onFocus={(e) => e.currentTarget.select()} />
      <ul className="targets" aria-label="Share on">
        {native && <li><button className="btn p" onClick={() => void navigator.share({ title, text: `${title} on NAVAAN`, url }).catch(() => undefined)}><Icon name="share" /> Share…</button></li>}
        {targets(title, url).map((x) => <li key={x.name}><a className="btn" href={x.href} target="_blank" rel="noreferrer noopener">{x.name}<span className="sr"> (opens in a new tab)</span></a></li>)}
        <li><button className="btn" onClick={() => void copy()}>{copied ? "Copied" : "Copy link"}</button></li>
      </ul>
    </div>
  );
}

// A link anyone can open to hear a 30 second preview. Only a published song with a confirmed licence can have one; the server says so if not.
export function ShareCard({ slug, title = "" }: { slug: string; title?: string }) {
  const [link, setLink] = useState<Link | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const make = async () => { setBusy(true); setMsg(""); try { setLink(await postJSON<Link>("/api/share", { slug })); } catch (e) { setMsg(errText(e)); } finally { setBusy(false); } };
  const stop = async () => { if (!link) return; setBusy(true); try { await postJSON("/api/share/revoke", { token: link.token }); setLink(null); setMsg("That link no longer works."); } catch (e) { setMsg(errText(e)); } finally { setBusy(false); } };
  return (
    <section className="card stack" aria-labelledby="share-h">
      <h2 id="share-h">Share</h2>
      {link ? (
        <>
          <ShareLinks title={title || slug} url={link.url} />
          <div className="row"><a className="btn g" href={link.url} target="_blank" rel="noreferrer">Preview <Icon name="external" /></a><button className="btn g" disabled={busy} onClick={() => void stop()}>Stop sharing</button></div>
        </>
      ) : <div className="row"><button className="btn" disabled={busy} onClick={() => void make()}>Create a share link</button></div>}
      {msg && <p role="status" className="mu">{msg}</p>}
    </section>
  );
}

// The Share button on a song: opens a sheet that makes the link and offers the platforms at once.
export function ShareDialog({ slug, title, onClose }: { slug: string; title: string; onClose: () => void }) {
  const [link, setLink] = useState<Link | null>(null); const [err, setErr] = useState(""); const [stopped, setStopped] = useState(false);
  const x = useRef<HTMLButtonElement>(null);
  const { guest } = useMe();
  useEffect(() => { if (guest) { setLink({ token: "", url: `${location.origin}/app/song/${slug}` }); return; }   // a visitor shares the page itself
    postJSON<Link>("/api/share", { slug }).then(setLink).catch((e) => setErr(errText(e))); }, [slug, guest]);
  useEffect(() => {
    x.current?.focus(); const key = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", key); return () => document.removeEventListener("keydown", key);
  }, [onClose]);
  const stop = async () => { if (!link) return; try { await postJSON("/api/share/revoke", { token: link.token }); setLink(null); setStopped(true); } catch (e) { setErr(errText(e)); } };
  return createPortal(
    <>
      <div className="scrim" onClick={onClose} />
      <div className="card dlg stack" role="dialog" aria-modal="true" aria-labelledby="sd-h">
        <div className="row"><h2 id="sd-h" style={{ flex: 1 }}>Share {title}</h2><button ref={x} className="btn g sq" onClick={onClose} aria-label="Close"><Icon name="close" /></button></div>
        {link && <ShareLinks title={title} url={link.url} />}
        {!link && !err && !stopped && <p className="mu" role="status">Making your link…</p>}
        {stopped && <p className="mu" role="status">That link no longer works.</p>}
        {err && <p role="alert" className="mu">{err}</p>}
        {link && link.token && <button className="btn g" onClick={() => void stop()}>Stop sharing</button>}
      </div>
    </>,
    document.body,   // a portal: the page has its own stacking order, which would put the Now playing bar over the sheet
  );
}

import { useState } from "react";
import { Icon } from "./Icon";
import { postJSON } from "../lib/api";
import { errText } from "../lib/songs";

// A link anyone can open to hear a 30 second preview. Only a published song with a confirmed licence can have one; the server says so if not.
export function ShareCard({ slug }: { slug: string }) {
  const [link, setLink] = useState<{ token: string; url: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const make = async () => { setBusy(true); setMsg(""); try { setLink(await postJSON<{ token: string; url: string }>("/api/share", { slug })); } catch (e) { setMsg(errText(e)); } finally { setBusy(false); } };
  const stop = async () => { if (!link) return; setBusy(true); try { await postJSON("/api/share/revoke", { token: link.token }); setLink(null); setMsg("That link no longer works."); } catch (e) { setMsg(errText(e)); } finally { setBusy(false); } };
  return (
    <section className="card stack" aria-labelledby="share-h">
      <h2 id="share-h">Share</h2>
      {link ? (
        <>
          <label htmlFor="share-url" className="mu">Anyone with this link hears a 30 second preview.</label>
          <input id="share-url" className="field" readOnly value={link.url} onFocus={(e) => e.currentTarget.select()} />
          <div className="row"><button className="btn p" onClick={() => void navigator.clipboard?.writeText(link.url)}>Copy link</button><a className="btn" href={link.url} target="_blank" rel="noreferrer">Open <Icon name="external" /></a><button className="btn g" disabled={busy} onClick={() => void stop()}>Stop sharing</button></div>
        </>
      ) : <div className="row"><button className="btn" disabled={busy} onClick={() => void make()}>Create a share link</button></div>}
      {msg && <p role="status" className="mu">{msg}</p>}
    </section>
  );
}

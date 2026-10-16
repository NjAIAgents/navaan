import { useCallback, useEffect, useState } from "react";
import { getJSON, postJSON, type Reply } from "../../lib/api";
import { errText } from "../../lib/songs";

function Item({ c, platform, done }: { c: Reply; platform: string; done: () => void }) {
  const [text, setText] = useState(c.reply?.draft ?? "");
  const [busy, setBusy] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [err, setErr] = useState(c.reply?.error ?? "");
  const act = async (name: "draft" | "edit" | "skip" | "send") => {
    setBusy(name); setErr("");
    try {
      const r = await postJSON<{ reply: { draft: string | null } | null }>(`/api/replies/${name}`, { platform, comment_id: c.comment_id, ...(name === "edit" || name === "send" ? { text } : {}) });
      if (name === "draft") setText(r.reply?.draft ?? "");
      if (name === "skip" || name === "send") done();
    } catch (e) { setErr(errText(e)); } finally { setBusy(""); setConfirm(false); }
  };
  return (
    <article className="card rec" aria-label={`Comment from ${c.username}`}>
      <p className="mu"><b>{c.username}</b> on <a href={c.link} target="_blank" rel="noreferrer">{c.post}</a> · {new Date(c.posted_at).toLocaleDateString([], { day: "numeric", month: "short" })}</p>
      <blockquote>{c.text}</blockquote>
      {err && <p role="alert" className="mu">{err}</p>}
      <label htmlFor={`t-${c.comment_id}`}>Your reply</label>
      <textarea id={`t-${c.comment_id}`} className="field" rows={3} value={text} onChange={(e) => setText(e.target.value)} placeholder="Write a reply, or draft one with Claude" />
      {confirm ? (
        <div className="stack" role="group" aria-label="Confirm sending"><p className="mu">This posts the reply publicly on {platform === "youtube" ? "YouTube" : "Instagram"} as your account.</p>
          <div className="row"><button className="btn p" disabled={!!busy} onClick={() => void act("send")}>Yes, send</button><button className="btn g" onClick={() => setConfirm(false)}>Not yet</button></div></div>
      ) : (
        <div className="row">
          <button className="btn p" disabled={!!busy || !text.trim()} onClick={() => setConfirm(true)}>Approve and send</button>
          <button className="btn" disabled={!!busy || !text.trim()} onClick={() => void act("edit")}>{busy === "edit" ? "Saving…" : "Save draft"}</button>
          <button className="btn" disabled={!!busy} onClick={() => void act("draft")}>{busy === "draft" ? "Drafting…" : text ? "Redraft with Claude" : "Draft with Claude"}</button>
          <button className="btn g" disabled={!!busy} onClick={() => void act("skip")}>Skip</button>
        </div>
      )}
    </article>
  );
}

// Unreplied comments. Claude only drafts when asked; nothing is posted until Approve and send is pressed and confirmed for that one comment.
export default function Interactions({ platform }: { platform: "instagram" | "youtube" }) {
  const [items, setItems] = useState<Reply[] | null>(null);
  const [err, setErr] = useState("");
  const load = useCallback(() => getJSON<{ items: Reply[] }>(`/api/replies?platform=${platform}`).then((r) => { setItems(r.items); setErr(""); }).catch((e) => setErr(errText(e))), [platform]);
  useEffect(() => { setItems(null); void load(); }, [load]);
  return (
    <>
      {err && <div className="card" role="alert"><h2>Could not load comments</h2><p className="mu">{err}</p></div>}
      {!items && !err && <p className="mu" role="status">Loading…</p>}
      {items && !items.length && <div className="card"><p className="empty">No comments are waiting for a reply.</p></div>}
      {items?.map((c) => <Item key={c.comment_id} c={c} platform={platform} done={() => void load()} />)}
    </>
  );
}

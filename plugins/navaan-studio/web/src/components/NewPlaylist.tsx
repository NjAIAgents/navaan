import { useState } from "react";
import { Link } from "react-router-dom";
import { Icon } from "./Icon";
import { ApiError, postJSON } from "../lib/api";
import { errText } from "../lib/songs";

export const VISIBILITY: { value: "private" | "unlisted" | "public"; label: string; hint: string }[] = [
  { value: "private", label: "Private", hint: "Only you can see it." },
  { value: "unlisted", label: "Unlisted", hint: "Anyone with the link can open it. It is not listed anywhere." },
  { value: "public", label: "Public", hint: "Anyone can find and open it." },
];

// Make a playlist: its name, what it is for, and who can see it. The plan's limit is the server's to say; the message and the way to the plans are shown as they come.
export function NewPlaylist({ onCreated, compact = false }: { onCreated: (id: string, name: string) => void; compact?: boolean }) {
  const [f, setF] = useState({ name: "", description: "", visibility: "private" as "private" | "unlisted" | "public" });
  const [busy, setBusy] = useState(false); const [err, setErr] = useState(""); const [limit, setLimit] = useState("");
  const hint = VISIBILITY.find((v) => v.value === f.visibility)!.hint;
  const create = async (e: React.FormEvent) => {
    e.preventDefault(); if (!f.name.trim()) return;
    setBusy(true); setErr(""); setLimit("");
    try { const r = await postJSON<{ id: string }>("/api/playlists/create", { name: f.name.trim(), description: f.description.trim(), visibility: f.visibility }); const n = f.name.trim(); setF({ name: "", description: "", visibility: "private" }); onCreated(r.id, n); }
    catch (x) { if (x instanceof ApiError && x.status === 403) setLimit(x.message); else setErr(errText(x)); }
    finally { setBusy(false); }
  };
  return (
    <form className="stack" onSubmit={(e) => void create(e)} aria-label="New playlist">
      <label htmlFor={compact ? "np-name-c" : "np-name"}>Name</label>
      <input id={compact ? "np-name-c" : "np-name"} className="field" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="Evening drive" maxLength={100} autoComplete="off" />
      <label htmlFor={compact ? "np-desc-c" : "np-desc"}>What is it for? <span className="mu">(optional)</span></label>
      <textarea id={compact ? "np-desc-c" : "np-desc"} className="field" rows={2} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} maxLength={300} />
      <label htmlFor={compact ? "np-vis-c" : "np-vis"}>Who can see it</label>
      <select id={compact ? "np-vis-c" : "np-vis"} className="field" value={f.visibility} onChange={(e) => setF({ ...f, visibility: e.target.value as typeof f.visibility })}>{VISIBILITY.map((v) => <option key={v.value} value={v.value}>{v.label}</option>)}</select>
      <p className="mu">{hint}</p>
      {limit && <div role="alert" className="stack"><p>{limit}</p><Link className="btn p" to="/plans"><Icon name="star" />See the plans</Link></div>}
      {err && <p role="alert" className="mu">{err}</p>}
      <div className="row"><button className="btn p" type="submit" disabled={busy || !f.name.trim()}>Create playlist</button></div>
    </form>
  );
}

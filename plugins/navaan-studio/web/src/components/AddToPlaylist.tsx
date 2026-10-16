import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Icon } from "./Icon";
import { NewPlaylist } from "./NewPlaylist";
import { getJSON, postJSON, type PlaylistRow } from "../lib/api";
import { errText } from "../lib/songs";
import { useMe } from "../lib/me";
import { PITCH } from "./GuestPitch";

// "Add to playlist" from wherever a song is listed: pick one of your playlists, or make a new one right there. The server decides what is allowed (a duplicate, the plan's limit); its message is shown as it is.
export function AddToPlaylist({ slug, title }: { slug: string; title: string }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button className="btn g sq" onClick={() => setOpen(true)} aria-label={`Add ${title} to a playlist`} aria-haspopup="dialog"><Icon name="plus" /></button>
      {open && <Sheet slug={slug} title={title} onClose={() => setOpen(false)} />}
    </>
  );
}

function Sheet({ slug, title, onClose }: { slug: string; title: string; onClose: () => void }) {
  const { guest } = useMe();
  const [lists, setLists] = useState<PlaylistRow[] | null>(null); const [msg, setMsg] = useState(""); const [err, setErr] = useState(""); const [making, setMaking] = useState(false);
  const x = useRef<HTMLButtonElement>(null);
  const load = () => getJSON<PlaylistRow[]>("/api/playlists").then(setLists).catch((e) => setErr(errText(e)));
  useEffect(() => { if (!guest) void load(); }, [guest]);
  useEffect(() => { x.current?.focus(); const k = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); }; document.addEventListener("keydown", k); return () => document.removeEventListener("keydown", k); }, [onClose]);
  const add = async (id: string, name: string) => { setErr(""); setMsg(""); try { await postJSON("/api/playlists/add", { id, slug }); setMsg(`Added to "${name}".`); void load(); } catch (e) { setErr(errText(e)); } };
  return createPortal(
    <>
      <div className="scrim" onClick={onClose} />
      <div className="card dlg stack" role="dialog" aria-modal="true" aria-labelledby="atp-h">
        <div className="row"><h2 id="atp-h" style={{ flex: 1 }}>Add {title} to a playlist</h2><button ref={x} className="btn g sq" onClick={onClose} aria-label="Close"><Icon name="close" /></button></div>
        {guest && <p role="status">{PITCH}</p>}
        {msg && <p role="status">{msg}</p>}{err && <p role="alert" className="mu">{err}</p>}
        {!guest && !lists && !err && <p className="mu" role="status">Loading…</p>}
        {lists && lists.length > 0 && <ul className="hist" aria-label="Your playlists">{lists.map((p) => (
          <li key={p.id} className="stp"><span className="tx"><b>{p.name}</b><span className="mu"> · {p.tracks} song{p.tracks === 1 ? "" : "s"} · {p.visibility}</span></span><button className="btn" onClick={() => void add(p.id, p.name)} aria-label={`Add to ${p.name}`}>Add</button></li>
        ))}</ul>}
        {lists && !lists.length && !making && <p className="mu">You have no playlists yet.</p>}
        {guest ? null : making ? <NewPlaylist compact onCreated={(id, name) => { setMaking(false); void add(id, name); }} /> : <button className="btn p" onClick={() => setMaking(true)}><Icon name="plus" /> New playlist</button>}
      </div>
    </>,
    document.body,
  );
}

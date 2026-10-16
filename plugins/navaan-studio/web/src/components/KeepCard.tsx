import { useEffect, useState } from "react";
import { getJSON, postJSON, type LibraryData, type PlaylistRow } from "../lib/api";
import { errText } from "../lib/songs";
import { useMe } from "../lib/me";
import { PITCH } from "./GuestPitch";

// Keep a published song: save it, or put it in one of your playlists. The server decides what is allowed (a playlist, a duplicate); its message is shown as it is.
export function KeepCard({ slug }: { slug: string }) {
  const { guest } = useMe();
  if (guest) return <GuestKeep />;
  const [saved, setSaved] = useState<boolean | null>(null);
  const [lists, setLists] = useState<PlaylistRow[]>([]);
  const [pick, setPick] = useState("");
  const [msg, setMsg] = useState("");
  useEffect(() => {
    getJSON<LibraryData>("/api/library").then((l) => setSaved(l.tracks.some((t) => t.slug === slug))).catch(() => setSaved(null));
    getJSON<PlaylistRow[]>("/api/playlists").then((p) => { setLists(p); setPick(p[0]?.id ?? ""); }).catch(() => setLists([]));
  }, [slug]);
  const save = async () => { try { await postJSON("/api/library/save", { kind: "track", slug, on: !saved }); setSaved(!saved); setMsg(""); } catch (e) { setMsg(errText(e)); } };
  const add = async () => { try { await postJSON("/api/playlists/add", { id: pick, slug }); setMsg(`Added to "${lists.find((l) => l.id === pick)?.name}".`); } catch (e) { setMsg(errText(e)); } };
  return (
    <section className="card stack" aria-label="Keep this song">
      <div className="row">
        <button className="btn" aria-pressed={!!saved} onClick={() => void save()}>{saved ? "Saved" : "Save song"}</button>
        {lists.length > 0 && <>
          <label className="sr" htmlFor="add-pl">Playlist</label>
          <select id="add-pl" className="field sel" value={pick} onChange={(e) => setPick(e.target.value)}>{lists.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}</select>
          <button className="btn" onClick={() => void add()}>Add to playlist</button>
        </>}
      </div>
      {msg && <p role="status" className="mu">{msg}</p>}
    </section>
  );
}

// Someone not signed in sees the same buttons; pressing one says what an account will give them.
function GuestKeep() {
  const [msg, setMsg] = useState("");
  return (
    <section className="card stack" aria-label="Keep this song">
      <div className="row"><button className="btn" onClick={() => setMsg(PITCH)}>Save song</button><button className="btn" onClick={() => setMsg(PITCH)}>Add to playlist</button></div>
      {msg && <p role="status" className="mu">{msg}</p>}
    </section>
  );
}

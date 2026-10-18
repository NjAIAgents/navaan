import { useEffect, useState } from "react";
import { getJSON, postJSON, type LibraryData, type PlaylistRow } from "../lib/api";
import { errText } from "../lib/songs";
import { useMe } from "../lib/me";
import { ClipCard } from "./ClipCard";
import { Icon } from "./Icon";
import { PITCH } from "./GuestPitch";
import { Sheet } from "./Sheet";
import { FeedbackForm, SongFeedback } from "./SongFeedback";

type Open = null | "playlist" | "clip" | "feedback" | "form";

// What a listener can do with a song, as one row of icons at the top of its page instead of a card each: save it, add it to a playlist, make and share a clip, say what you think.
// Save is a toggle at once; the others open a sheet. Someone not signed in presses the same icons and is told what an account will give them.
export function SongTools({ slug, title, position, duration }: { slug: string; title: string; position: number | null; duration: number }) {
  const { guest } = useMe();
  const [open, setOpen] = useState<Open>(null); const [msg, setMsg] = useState("");
  const [saved, setSaved] = useState<boolean | null>(null); const [lists, setLists] = useState<PlaylistRow[]>([]); const [pick, setPick] = useState("");
  useEffect(() => {
    if (guest) return;
    getJSON<LibraryData>("/api/library").then((l) => setSaved(l.tracks.some((t) => t.slug === slug))).catch(() => setSaved(null));   // expected: a failed lookup leaves the heart unfilled
    getJSON<PlaylistRow[]>("/api/playlists").then((p) => { setLists(p); setPick(p[0]?.id ?? ""); }).catch(() => setLists([]));   // expected: no playlists to offer
  }, [slug, guest]);
  const save = async () => {
    if (guest) return setMsg(PITCH);
    try { await postJSON("/api/library/save", { kind: "track", slug, on: !saved }); setSaved(!saved); setMsg(""); } catch (e) { setMsg(errText(e)); }
  };
  const add = async () => { try { await postJSON("/api/playlists/add", { id: pick, slug }); setMsg(`Added to "${lists.find((l) => l.id === pick)?.name}".`); } catch (e) { setMsg(errText(e)); } };
  const close = () => setOpen(null);
  return (
    <>
      <div className="row tools" role="group" aria-label={`Do more with ${title}`}>
        <button className={"btn sq" + (saved ? " p" : "")} aria-pressed={!!saved} aria-label={saved ? "Saved" : "Save song"} onClick={() => void save()}><Icon name="heart" filled={!!saved} /></button>
        <button className="btn sq" aria-label="Add to a playlist" onClick={() => { setMsg(""); guest ? setMsg(PITCH) : setOpen("playlist"); }}><Icon name="playlist" /></button>
        <button className="btn sq" aria-label="Share a clip" onClick={() => setOpen("clip")}><Icon name="scissors" /></button>
        <button className="btn sq" aria-label="What did you think?" onClick={() => setOpen("feedback")}><Icon name="thumb" /></button>
      </div>
      {msg && open !== "playlist" && <p role="status" className="mu">{msg}</p>}
      {open === "playlist" && (
        <Sheet title="Add to a playlist" onClose={close}>
          {lists.length ? (
            <div className="row">
              <label className="sr" htmlFor="add-pl">Playlist</label>
              <select id="add-pl" className="field sel" value={pick} onChange={(e) => setPick(e.target.value)}>{lists.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}</select>
              <button className="btn p" onClick={() => void add()}>Add to playlist</button>
            </div>
          ) : <p className="mu">You have no playlists yet. Make one in your Library, then add songs to it here.</p>}
          {msg && <p role="status" className="mu">{msg}</p>}
        </Sheet>
      )}
      {open === "clip" && <Sheet title="Share a clip" onClose={close}><ClipCard bare slug={slug} title={title} position={position} duration={duration} /></Sheet>}
      {open === "feedback" && <Sheet title="What did you think?" onClose={close}><SongFeedback bare slug={slug} title={title} onForm={() => setOpen("form")} /></Sheet>}
      {open === "form" && <FeedbackForm slug={slug} title={title} onClose={close} />}
    </>
  );
}

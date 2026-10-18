import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getJSON, postJSON, type LibraryData, type PlaylistRow } from "../lib/api";
import { errText } from "../lib/songs";
import { useMe } from "../lib/me";
import { ClipCard } from "./ClipCard";
import { Icon } from "./Icon";
import { PITCH } from "./GuestPitch";
import { Sheet } from "./Sheet";
import { FeedbackForm, SongFeedback } from "./SongFeedback";

type Open = null | "playlist" | "clip" | "feedback" | "form" | "join";

// What a listener can do with a song, as one row of icons at the top of its page instead of a card each: save it, add it to a playlist, make and share a clip, say what you think.
// Save is a toggle at once; the others open a sheet. Someone not signed in presses the same icons and is told what an account will give them.
export function SongTools({ slug, title, position, duration, lyrics, onLyrics }: { slug: string; title: string; position: number | null; duration: number; lyrics?: boolean; onLyrics?: () => void }) {
  const { guest } = useMe();
  const [open, setOpen] = useState<Open>(null); const [msg, setMsg] = useState("");
  const [saved, setSaved] = useState<boolean | null>(null); const [lists, setLists] = useState<PlaylistRow[]>([]); const [pick, setPick] = useState("");
  useEffect(() => {
    if (guest) return;
    getJSON<LibraryData>("/api/library").then((l) => setSaved(l.tracks.some((t) => t.slug === slug))).catch(() => setSaved(null));   // expected: a failed lookup leaves the heart unfilled
    getJSON<PlaylistRow[]>("/api/playlists").then((p) => { setLists(p); setPick(p[0]?.id ?? ""); }).catch(() => setLists([]));   // expected: no playlists to offer
  }, [slug, guest]);
  const save = async () => {
    if (guest) return setOpen("join");
    try { await postJSON("/api/library/save", { kind: "track", slug, on: !saved }); setSaved(!saved); setMsg(""); } catch (e) { setMsg(errText(e)); }
  };
  const add = async () => { try { await postJSON("/api/playlists/add", { id: pick, slug }); setMsg(`Added to "${lists.find((l) => l.id === pick)?.name}".`); } catch (e) { setMsg(errText(e)); } };
  const close = () => setOpen(null);
  return (
    <>
      <div className="row tools" role="group" aria-label={`Do more with ${title}`}>   {/* each icon carries its word under it, so Save is not read as a second like */}
        <span className="tool"><button className={"btn sq" + (saved ? " p" : "")} aria-pressed={!!saved} aria-label={saved ? "Saved" : "Save song"} onClick={() => void save()}><Icon name="bookmark" filled={!!saved} /></button><span aria-hidden="true">{saved ? "Saved" : "Save"}</span></span>
        <span className="tool"><button className="btn sq" aria-label="Add to a playlist" onClick={() => { setMsg(""); setOpen(guest ? "join" : "playlist"); }}><Icon name="playlist" /></button><span aria-hidden="true">Playlist</span></span>
        <span className="tool"><button className="btn sq" aria-label="Share a clip" onClick={() => setOpen("clip")}><Icon name="scissors" /></button><span aria-hidden="true">Clip</span></span>
        <span className="tool"><button className="btn sq" aria-label="What did you think?" onClick={() => setOpen("feedback")}><Icon name="thumb" /></button><span aria-hidden="true">Feedback</span></span>
        {onLyrics && <span className="tool"><button className={"btn sq" + (lyrics ? " p" : "")} aria-pressed={!!lyrics} aria-label="Lyrics" onClick={onLyrics}><Icon name="lyrics" /></button><span aria-hidden="true">Lyrics</span></span>}
      </div>
      {msg && open !== "playlist" && <p role="status" className="mu">{msg}</p>}
      {open === "join" && (
        <Sheet title="Create your account" onClose={close}>
          <p>{PITCH.replace("Accounts are coming soon. ", "")} With an account you save songs and make your own playlists.</p>
          <div className="row"><Link className="btn p" to="/join">Create account</Link><button className="btn g" onClick={close}>Not now</button></div>
        </Sheet>
      )}
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

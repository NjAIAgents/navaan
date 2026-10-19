import { useState } from "react";
import { postJSON, type SongDetail } from "../lib/api";
import { MAX_VIDEO_BYTES, uploadVideo } from "../lib/files";
import { errText } from "../lib/songs";

// A reel with no footage yet (the upload at creation did not finish, or was skipped): choose the video again. It goes up as it is, the server shrinks it, and the pipeline starts.
export function ReelFootage({ d, done }: { d: SongDetail; done: () => void }) {
  const [file, setFile] = useState<File | null>(null); const [pct, setPct] = useState(0); const [busy, setBusy] = useState(false); const [err, setErr] = useState("");
  const send = async (e: React.FormEvent) => {
    e.preventDefault(); setErr("");
    if (!file) return setErr("Choose your video first.");
    if (file.size > MAX_VIDEO_BYTES) return setErr("That video is over 2 GB.");
    setBusy(true);
    try { await uploadVideo(d.slug, file, (a, b) => setPct(Math.round((100 * a) / Math.max(1, b)))); await postJSON("/api/run", { slug: d.slug, all: true }); done(); } catch (x) { setErr(errText(x)); } finally { setBusy(false); }
  };
  return (
    <section className="card stack alert" aria-labelledby="rf-h">
      <h2 id="rf-h">This reel has no footage yet</h2>
      <p>Choose your video (mp4 or mov, up to 2 GB). It is shrunk to a small working copy and the big original is deleted once that copy is checked.</p>
      <form className="stack" onSubmit={(e) => void send(e)}>
        <label htmlFor="rf-file">Your video</label>
        <input id="rf-file" className="field" type="file" accept="video/*,.mp4,.mov,.m4v,.mkv,.webm,.mpg,.mpeg" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        {busy && <progress max={100} value={pct} aria-label="Upload progress" />}
        <div className="row"><button className="btn p" type="submit" disabled={busy}>{busy ? `Uploading ${pct}%` : "Upload and start"}</button></div>
      </form>
      {err && <p role="alert" className="mu">{err}</p>}
    </section>
  );
}

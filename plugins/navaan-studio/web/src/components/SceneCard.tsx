import { useState } from "react";
import { postJSON, type SongDetail } from "../lib/api";
import { MAX_VIDEO_BYTES, uploadVideo } from "../lib/files";
import { errText } from "../lib/songs";

// How the scene was fitted to the short, in plain words.
const fitText = (f: NonNullable<NonNullable<SongDetail["scene"]>["fit"]>) =>
  f.cut ? `The scene (${f.src_seconds.toFixed(0)} s) is longer than the short and is cut at its end.`
    : f.stretch > 1 ? `The scene (${f.src_seconds.toFixed(0)} s) plays ${f.stretch.toFixed(1)} times slower${f.hold > 0.1 ? ` and its last frame is held ${f.hold.toFixed(1)} s` : ""}, so the credit page ends the short.`
      : f.hold > 0.1 ? `The scene (${f.src_seconds.toFixed(0)} s) plays at normal speed and its last frame is held ${f.hold.toFixed(1)} s, so the credit page ends the short.` : "The scene fits the short exactly.";

// An inspiration's own scene video: used instead of a generated background picture. Added or taken away until the short is rendered.
export function SceneCard({ d, done }: { d: SongDetail; done: () => void }) {
  const [file, setFile] = useState<File | null>(null); const [pct, setPct] = useState(0); const [busy, setBusy] = useState(false); const [err, setErr] = useState("");
  if (d.meta.type !== "inspiration" || (d.files ?? {})["final_reel_9x16.mp4"]) return null;   // only an inspiration, and only before its video exists
  const has = !!(d.scene?.ready || d.scene?.pending);
  const send = async (e: React.FormEvent) => {
    e.preventDefault(); setErr("");
    if (!file) return setErr("Choose a video first.");
    if (file.size > MAX_VIDEO_BYTES) return setErr("That video is over 2 GB.");
    setBusy(true);
    try { await uploadVideo(d.slug, file, (a, b) => setPct(Math.round((100 * a) / Math.max(1, b)))); setFile(null); done(); } catch (x) { setErr(errText(x)); } finally { setBusy(false); }
  };
  const remove = async () => { setErr(""); setBusy(true); try { await postJSON("/api/scene/remove", { slug: d.slug }); done(); } catch (x) { setErr(errText(x)); } finally { setBusy(false); } };
  return (
    <section className="card stack" aria-labelledby="sc-h">
      <h2 id="sc-h">Scene video</h2>
      {has
        ? <p>{d.scene?.pending && !d.scene?.ready ? "Your scene video is uploaded and waits to be prepared." : "Your scene video is ready."} No background picture is made; the video plays behind the words with the song's sound. {d.scene?.fit ? fitText(d.scene.fit) : ""}</p>
        : <p className="mu">Optional. Use a video of your own instead of a generated background picture: nothing is spent on a picture, the video plays behind the words with the song's sound, and the credit page ends the short. Without one, nothing changes.</p>}
      <form className="stack" onSubmit={(e) => void send(e)}>
        <label htmlFor="sc-file">{has ? "Replace it with another video" : "Your scene video (mp4 or mov, up to 2 GB)"}</label>
        <input id="sc-file" className="field" type="file" accept="video/*,.mp4,.mov,.m4v,.mkv,.webm,.mpg,.mpeg" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        {busy && file && <progress max={100} value={pct} aria-label="Upload progress" />}
        <div className="row">
          <button className="btn p" type="submit" disabled={busy}>{busy && file ? `Uploading ${pct}%` : has ? "Replace" : "Upload"}</button>
          {has && <button className="btn" type="button" disabled={busy} onClick={() => void remove()}>Remove the scene video</button>}
        </div>
      </form>
      {err && <p role="alert" className="mu">{err}</p>}
    </section>
  );
}

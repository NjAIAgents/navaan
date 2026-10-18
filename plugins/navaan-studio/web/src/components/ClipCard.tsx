import { useEffect, useState } from "react";
import { getJSON, postJSON } from "../lib/api";
import { errText } from "../lib/songs";
import { mmss } from "../lib/lyrics";
import { usePlayer, usePosition } from "../lib/player";

type Made = { url: string; page: string };
const MIN_LEN = 5; const MAX_LEN = 90;   // seconds; the server accepts the same
// What travels with a shared clip: the song, the way back to the full song, and the tag that makes the next person find it.
export const clipCaption = (title: string, page: string) => `${title} on NAVAAN 🎧\nHear the full song: ${page}\n\n#NAVAAN #NewMusic #IndieMusic #NowPlaying`;

// A clip of the song to share: 5 to 90 seconds between the two points you choose, as a vertical video with the cover, the title and "Hear the full song". It is shared (the phone's share sheet, so Instagram and WhatsApp are there), not handed over as a download, and it carries the way back to the whole song.
export function ClipCard({ slug, title, position, duration: playing, bare = false }: { slug: string; title: string; position: number | null; duration: number; bare?: boolean }) {   // bare: inside a sheet, which has its own frame and title
  // The song's length: from the player when the song is loaded there, else read from the audio file's header without playing it, so the sliders are there before the song has been played.
  const [read, setRead] = useState(0); const duration = playing > 20 ? playing : read;
  useEffect(() => {
    if (playing > 20) return; let live = true; const a = new Audio(); a.preload = "metadata";
    getJSON<{ url?: string }>(`/api/play?slug=${encodeURIComponent(slug)}`).then((r) => { if (!live || typeof r?.url !== "string") return; a.onloadedmetadata = () => { if (live && Number.isFinite(a.duration)) setRead(a.duration); }; a.src = r.url; }).catch(() => undefined);   // expected: without it the start and end are typed
    return () => { live = false; a.onloadedmetadata = null; a.removeAttribute("src"); };
  }, [slug, playing]);
  const [start, setStart] = useState(0); const [end, setEnd] = useState(30);
  const [made, setMade] = useState<Made | null>(null); const [busy, setBusy] = useState(false); const [err, setErr] = useState(""); const [note, setNote] = useState("");
  const known = duration > 20; const whole = known ? Math.floor(duration) : 3600;   // the length is unknown until the song has loaded: then numbers are typed instead of dragged
  const length = end - start;
  // The two points keep to 5 to 90 seconds apart and inside the song: moving one pushes the other.
  const moveStart = (v: number) => { const a = Math.max(0, Math.min(whole - MIN_LEN, Math.floor(v) || 0)); setStart(a); setEnd(Math.max(a + MIN_LEN, Math.min(end, a + MAX_LEN, whole))); };
  const moveEnd = (v: number) => { const b = Math.max(MIN_LEN, Math.min(whole, Math.floor(v) || 0)); setEnd(b); setStart(Math.min(b - MIN_LEN, Math.max(start, b - MAX_LEN, 0))); };
  const slide = (a: number, b: number) => { setMade(null); setStart(a); setEnd(b); };
  // Hear exactly the part that will be cut: the song plays from the first point and stops at the second.
  const pl = usePlayer(); const pos = usePosition().position; const [hearing, setHearing] = useState(false);
  useEffect(() => { if (hearing && pl.slug === slug && pos >= end) { setHearing(false); if (pl.playing) void pl.toggle(slug, title); } }, [hearing, pos, end, pl, slug, title]);
  const hear = async () => { setHearing(true); if (pl.slug !== slug || !pl.playing) await pl.toggle(slug, title); pl.seek(start); };
  const make = async () => { setBusy(true); setErr(""); setNote(""); setMade(null); try { setMade(await postJSON<Made>("/api/clip", { slug, start, length: end - start })); } catch (e) { setErr(errText(e)); } finally { setBusy(false); } };
  const copyText = async (text: string, ok: string) => { try { await navigator.clipboard.writeText(text); setNote(ok); } catch { setNote("Copy failed. Select the text by hand."); } };   // expected: clipboard can be blocked
  const copy = () => copyText(made!.page, "Link copied.");
  const phone = typeof navigator !== "undefined" && typeof navigator.canShare === "function";   // a phone's share sheet takes the video itself; a computer does not
  // The clip is fetched as soon as it is made, not when Share is pressed: an iPhone only opens the share sheet from inside the tap itself, and waiting for a download first made it refuse.
  const [file, setFile] = useState<File | null | "failed">(null);
  useEffect(() => {
    if (!made) return; setFile(null); let live = true;
    fetch(made.url).then((r) => r.blob()).then((b) => { if (live) setFile(new File([b], `${slug}-clip.mp4`, { type: "video/mp4" })); }).catch(() => { if (live) setFile("failed"); });   // expected: without the file Share sends the link instead
    return () => { live = false; };
  }, [made, slug]);
  const failed = (e: unknown) => { if ((e as { name?: string }).name !== "AbortError") setNote("Could not open the share sheet. Copy the link instead."); };
  const share = () => {   // nothing is awaited before navigator.share: it must be called inside the tap
    if (!made) return; setNote("");
    const text = clipCaption(title, made.page); const f = file instanceof File ? file : null;
    void navigator.clipboard?.writeText(text).then(() => setNote("Caption with the link and hashtags copied: paste it into the post.")).catch(() => undefined);   // Instagram drops text handed to it with a video, so the caption is on the clipboard to paste; expected: clipboard can be blocked
    try {
      if (f && navigator.canShare?.({ files: [f] })) void navigator.share({ files: [f], text }).catch(failed);
      else if (navigator.share) void navigator.share({ title, text: `${title} on NAVAAN`, url: made.page }).catch(failed);
      else void copy();
    } catch (e) { failed(e); }
  };
  return (
    <Frame bare={bare}>
      <p className="mu">Drag the two handles to choose the part of the song, up to 90 seconds. It becomes a video with the cover and a way back to the full song.</p>
      {known ? (
        <div className="clipbar">   {/* one bar with a handle at each end of the clip */}
          <div className="trk" aria-hidden="true"><span className="sel" style={{ left: `${(start / whole) * 100}%`, right: `${100 - (end / whole) * 100}%` }} /></div>
          <label className="sr" htmlFor="clip-start">Start at (seconds)</label>
          <input id="clip-start" type="range" min={0} max={whole} step={1} value={start} aria-valuetext={mmss(start)} onChange={(e) => { moveStart(Number(e.target.value)); setMade(null); }} />
          <label className="sr" htmlFor="clip-end">End at (seconds)</label>
          <input id="clip-end" type="range" min={0} max={whole} step={1} value={end} aria-valuetext={mmss(end)} onChange={(e) => { moveEnd(Number(e.target.value)); setMade(null); }} />
        </div>
      ) : (
        <div className="row" style={{ flexWrap: "wrap" }}>
          <div><label htmlFor="clip-start">Start at (seconds)</label><br /><input id="clip-start" className="field sel" type="number" min={0} max={whole} value={start} onChange={(e) => moveStart(Number(e.target.value))} /></div>
          <div><label htmlFor="clip-end">End at (seconds)</label><br /><input id="clip-end" className="field sel" type="number" min={MIN_LEN} max={whole} value={end} onChange={(e) => moveEnd(Number(e.target.value))} /></div>
        </div>
      )}
      <output className="mu" role="status">Clip from {mmss(start)} to {mmss(end)}, {length} seconds{known ? ` of ${mmss(duration)}` : ""}</output>
      <div className="row" style={{ flexWrap: "wrap" }}>
        {position != null && <button className="btn g" onClick={() => { const a = Math.floor(position); slide(Math.max(0, Math.min(whole - MIN_LEN, a)), Math.max(MIN_LEN, Math.min(whole, a + length))); }}>Start where it is now ({mmss(position)})</button>}
        <button className="btn g" onClick={() => void hear()} aria-pressed={hearing}>{hearing ? "Playing the part…" : "Hear this part"}</button>
      </div>
      <div className="row"><button className="btn p" disabled={busy} onClick={() => void make()}>{busy ? "Making the clip…" : "Make the clip"}</button></div>
      {made && (
        <div className="stack">
          <video controls playsInline preload="metadata" src={made.url} style={{ width: "min(280px, 100%)", borderRadius: 12 }} aria-label={`Clip of ${title}`} />
          <div className="row"><button className="btn p" disabled={file === null} onClick={share}>Share the clip</button><a className="btn" href={made.url} download={`${slug}-clip.mp4`}>Download the clip</a></div>
          <div className="row"><button className="btn" onClick={() => void copyText(clipCaption(title, made.page), "Caption copied.")}>Copy caption</button><button className="btn" onClick={() => void copy()}>Copy link</button></div>
          {file === null && <p className="mu" role="status">Getting the clip ready so it opens straight in the share sheet…</p>}
          {!phone && <p className="mu">On a computer: download the clip, then post it from the Instagram app on your phone, with the caption and link copied here.</p>}
        </div>
      )}
      {note && <p role="status" className="mu">{note}</p>}
      {err && <p role="alert" style={{ color: "var(--bad)" }}>{err}</p>}
    </Frame>
  );
}

const Frame = ({ bare, children }: { bare: boolean; children: React.ReactNode }) => bare ? <div className="stack">{children}</div> : <section className="card stack" aria-labelledby="clip-h"><h2 id="clip-h">Share a clip</h2>{children}</section>;

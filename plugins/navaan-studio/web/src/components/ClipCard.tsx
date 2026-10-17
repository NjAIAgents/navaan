import { useState } from "react";
import { postJSON } from "../lib/api";
import { errText } from "../lib/songs";
import { mmss } from "../lib/lyrics";

type Made = { url: string; page: string };
// What travels with a shared clip: the song, the way back to the full song, and the tag that makes the next person find it.
export const clipCaption = (title: string, page: string) => `${title} on NAVAAN. Hear the full song: ${page} #NAVAAN #NewMusic`;

// A clip of the song to share: 15 or 30 seconds from where you choose, as a vertical video with the cover, the title and "Hear the full song". It is shared (the phone's share sheet, so Instagram and WhatsApp are there), not handed over as a download, and it carries the way back to the whole song.
export function ClipCard({ slug, title, position, duration }: { slug: string; title: string; position: number | null; duration: number }) {
  const [start, setStart] = useState(0); const [length, setLength] = useState<15 | 30>(15);
  const [made, setMade] = useState<Made | null>(null); const [busy, setBusy] = useState(false); const [err, setErr] = useState(""); const [note, setNote] = useState("");
  const max = duration > 20 ? Math.floor(duration) - 2 : 3600;
  const make = async () => { setBusy(true); setErr(""); setNote(""); setMade(null); try { setMade(await postJSON<Made>("/api/clip", { slug, start, length })); } catch (e) { setErr(errText(e)); } finally { setBusy(false); } };
  const copyText = async (text: string, ok: string) => { try { await navigator.clipboard.writeText(text); setNote(ok); } catch { setNote("Copy failed. Select the text by hand."); } };   // expected: clipboard can be blocked
  const copy = () => copyText(made!.page, "Link copied.");
  const phone = typeof navigator !== "undefined" && typeof navigator.canShare === "function";   // a phone's share sheet takes the video itself; a computer does not
  const share = async () => {
    if (!made) return; setNote("");
    try {
      const blob = await (await fetch(made.url)).blob(); const file = new File([blob], `${slug}-clip.mp4`, { type: "video/mp4" });
      const text = clipCaption(title, made.page);
      if (navigator.canShare?.({ files: [file] })) { await navigator.share({ files: [file], text }); return; }
      if (navigator.share) { await navigator.share({ title, text: `${title} on NAVAAN`, url: made.page }); return; }
      await copy();
    } catch (e) { if ((e as { name?: string }).name !== "AbortError") setNote("Could not open the share sheet. Copy the link instead."); }
  };
  return (
    <section className="card stack" aria-labelledby="clip-h">
      <h2 id="clip-h">Share a clip</h2>
      <p className="mu">Pick where the clip starts and how long it is. It is a video with the cover and a way back to the full song.</p>
      <div className="row" style={{ flexWrap: "wrap", alignItems: "flex-end" }}>
        <div style={{ flex: "1 1 260px", minWidth: 0 }}>
          <label htmlFor="clip-start">Start at (seconds)</label><br />
          {duration > 20 ? (   // the song's length is known: drag to where the clip should begin
            <>
              <input id="clip-start" type="range" min={0} max={max} step={1} value={start} aria-valuetext={mmss(start)} style={{ width: "100%" }} onChange={(e) => setStart(Math.max(0, Math.min(max, Number(e.target.value) || 0)))} />
              <output htmlFor="clip-start" className="mu">Starts at {mmss(start)}, ends at {mmss(Math.min(start + length, duration))} of {mmss(duration)}</output>
            </>
          ) : <input id="clip-start" className="field sel" type="number" min={0} max={max} value={start} onChange={(e) => setStart(Math.max(0, Math.min(max, Number(e.target.value) || 0)))} />}
        </div>
        {position != null && <button className="btn g" onClick={() => setStart(Math.min(max, Math.floor(position)))}>Use where it is now ({mmss(position)})</button>}
      </div>
      <div className="seg" role="group" aria-label="Length" style={{ alignSelf: "flex-start" }}>
        {([15, 30] as const).map((n) => <button key={n} aria-pressed={length === n} onClick={() => setLength(n)}>{n} seconds</button>)}
      </div>
      <div className="row"><button className="btn p" disabled={busy} onClick={() => void make()}>{busy ? "Making the clip…" : "Make the clip"}</button></div>
      {made && (
        <div className="stack">
          <video controls playsInline preload="metadata" src={made.url} style={{ width: "min(280px, 100%)", borderRadius: 12 }} aria-label={`Clip of ${title}`} />
          <div className="row"><button className="btn p" onClick={() => void share()}>Share the clip</button><a className="btn" href={made.url} download={`${slug}-clip.mp4`}>Download the clip</a></div>
          <div className="row"><button className="btn" onClick={() => void copyText(clipCaption(title, made.page), "Caption copied.")}>Copy caption</button><button className="btn" onClick={() => void copy()}>Copy link</button></div>
          {!phone && <p className="mu">On a computer: download the clip, then post it from the Instagram app on your phone, with the caption and link copied here.</p>}
        </div>
      )}
      {note && <p role="status" className="mu">{note}</p>}
      {err && <p role="alert" style={{ color: "var(--bad)" }}>{err}</p>}
    </section>
  );
}

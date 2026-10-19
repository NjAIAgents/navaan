import { useEffect, useState } from "react";
import { getJSON, postJSON, type CloudData, type SongDetail } from "../lib/api";
import { errText, isShort } from "../lib/songs";

// The song's Media tab, as the classic page had it (NAV-29): where it is published, what is in the archive, the stills, and the picture tools after the look is chosen.

type Yt = { id?: string; url?: string; file?: string; privacy?: string };

// What is out there: the YouTube video and Short (thumbnail, privacy, a way into YouTube Studio when private) and the Instagram Reel (embedded).
export function PublishedCard({ d }: { d: SongDetail }) {
  const P = (d.meta.published ?? {}) as { youtube_items?: Yt[]; youtube_short?: Yt; instagram?: unknown };
  const yt = [...(P.youtube_items ?? [])]; if (P.youtube_short?.id && !yt.some((x) => x.id === P.youtube_short!.id)) yt.push(P.youtube_short);
  const short = (x: Yt) => (x.url ?? "").includes("/shorts/") || /reel|short/i.test(x.file ?? "") || x.id === P.youtube_short?.id;
  const ig = typeof P.instagram === "string" && P.instagram.startsWith("http") ? P.instagram : ""; const igId = /\/(?:reel|p|tv)\/([^/?#]+)/.exec(ig)?.[1];
  if (!yt.length && !ig) return null;
  return (
    <section className="sec" aria-labelledby="pub-h">
      <div className="sh"><h2 id="pub-h">Where it is published</h2></div>
      <div className="card row" style={{ flexWrap: "wrap", alignItems: "flex-start", gap: 20 }}>
        {yt.filter((x) => x.id).map((x) => { const sh = short(x), url = x.url || `https://youtu.be/${x.id}`; return (
          <figure key={x.id} className="stack" style={{ margin: 0, gap: 6, width: sh ? 180 : 360, maxWidth: "100%" }}>
            <figcaption className="row"><b>{sh ? "Short" : "Full video"}</b><span className={"chip " + (x.privacy === "public" ? "ok" : "wn")}>{x.privacy ?? "uploaded"}</span></figcaption>
            <a href={url} target="_blank" rel="noreferrer"><img src={`https://i.ytimg.com/vi/${x.id}/${sh ? "oardefault" : "hqdefault"}.jpg`} alt={`${sh ? "Short" : "Video"} on YouTube`} style={{ width: "100%", aspectRatio: sh ? "9 / 16" : "16 / 9", objectFit: "cover", borderRadius: 10 }} /></a>
            <span className="row"><a href={url} target="_blank" rel="noreferrer">Open on YouTube</a>{x.privacy !== "public" && <a href={`https://studio.youtube.com/video/${x.id}/edit`} target="_blank" rel="noreferrer">Open in YouTube Studio</a>}</span>
          </figure>); })}
        {ig && (
          <figure className="stack" style={{ margin: 0, gap: 6 }}>
            <figcaption className="row"><b>Instagram Reel</b><span className="chip ok">Posted</span><a href={ig} target="_blank" rel="noreferrer">Open on Instagram</a></figcaption>
            {igId && <iframe title="The Reel on Instagram" src={`https://www.instagram.com/reel/${igId}/embed`} width={300} height={540} style={{ border: 0, borderRadius: 10, maxWidth: "100%" }} loading="lazy" />}
          </figure>
        )}
      </div>
    </section>
  );
}

const kindOf = (n: string) => (/\.(mp3|wav|m4a)$/i.test(n) ? "audio" : /\.(mp4|mov|webm)$/i.test(n) ? "video" : /\.(png|jpe?g|webp)$/i.test(n) ? "image" : "");
const size = (b: number) => (b > 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${Math.round(b / 1e3)} KB`);

// This song's files in the cloud archive, each previewed through a one-hour link from the bucket.
export function ArchiveCard({ slug }: { slug: string }) {
  const [c, setC] = useState<CloudData | null>(null); const [open, setOpen] = useState<Record<string, string>>({}); const [err, setErr] = useState("");
  useEffect(() => { getJSON<CloudData>("/api/cloud").then(setC).catch(() => setC(null)); }, []);   // expected: no cloud, no card
  if (!c?.configured) return null;
  const s = (c.songs ?? []).find((x) => x.slug === slug);
  const files = (s?.files ?? []).filter((f) => kindOf(f.name));
  const show = async (key: string) => { setErr(""); try { const r = await postJSON<{ url: string }>("/api/cloud/link", { key }); setOpen((o) => ({ ...o, [key]: r.url })); } catch (e) { setErr(errText(e)); } };
  return (
    <section className="sec" aria-labelledby="arc-h">
      <div className="sh"><h2 id="arc-h">Cloud archive</h2>{s && <span className={"chip " + (s.verified === false ? "wn" : "ok")}>{s.verified === false ? "Out of date" : "Verified"}</span>}</div>
      <div className="card stack">
        {!s ? <p className="mu">Not archived yet. Run the archive step, then its media shows here.</p> : !files.length ? <p className="mu">The archive has no media files.</p>
          : files.map((f) => { const k = kindOf(f.name), u = open[f.key]; return (
            <div key={f.key} className="stack" style={{ gap: 6 }}>
              <div className="row"><code style={{ overflowWrap: "anywhere", flex: 1 }}>{f.name}</code><span className="mu">{size(f.size)}</span>{!u && <button className="btn g" onClick={() => void show(f.key)} aria-label={`Preview ${f.name}`}>Preview</button>}</div>
              {u && (k === "audio" ? <audio controls src={u} aria-label={f.name} /> : k === "video" ? <video controls playsInline src={u} aria-label={f.name} style={{ maxWidth: "100%", maxHeight: 360 }} /> : <img src={u} alt={f.name} style={{ maxWidth: "100%", maxHeight: 240, borderRadius: 8 }} />)}
            </div>); })}
        {s && <p className="mu">Links last one hour and come straight from the bucket.</p>}
        {err && <p role="alert" className="mu">{err}</p>}
      </div>
    </section>
  );
}

// The local stills (covers, thumbnails, background) while the review copy is still here.
export function StillsCard({ d }: { d: SongDetail }) {
  const f = d.files ?? {}; const li = ["cover_1x1.png", "cover_16x9.png", "thumb_16x9.jpg", "background.jpg", "background.png", "thumb_9x16.jpg"].filter((n) => f[n]);
  if (d.meta.cleanup || !li.length) return null;
  return (
    <section className="sec" aria-labelledby="st-h">
      <div className="sh"><h2 id="st-h">Stills</h2></div>
      <div className="card row" style={{ flexWrap: "wrap" }}>{li.map((n) => <figure key={n} className="stack" style={{ margin: 0, gap: 4 }}><figcaption className="mu">{n}</figcaption><a href={`/media/${d.slug}/${n}?v=${f[n]}`} target="_blank" rel="noreferrer"><img src={`/media/${d.slug}/${n}?w=360&v=${f[n]}`} alt={n} style={{ maxHeight: 180, maxWidth: "100%", borderRadius: 8 }} /></a></figure>)}</div>
    </section>
  );
}

// The song's pictures after the look is chosen: open one full size, redraw one as a true 9:16 picture, or try two more from the prompts (OpenAI pictures).
export function PicturesCard({ d, done }: { d: SongDetail; done: () => void }) {
  const [busy, setBusy] = useState(""); const [err, setErr] = useState("");
  const imgs = d.images ?? []; const vert = d.vertical ?? {}; const t = d.try ?? {};
  if (d.meta.cleanup || isShort(d.meta.type) || (!imgs.length && !(d.openai_pictures && d.prompt_pack))) return null;
  const run = async (what: string, f: () => Promise<unknown>) => { setBusy(what); setErr(""); try { await f(); done(); } catch (e) { setErr(errText(e)); } finally { setBusy(""); } };
  return (
    <section className="sec" aria-labelledby="pics-h">
      <div className="sh"><h2 id="pics-h">Pictures</h2><span className="n">{imgs.length}</span></div>
      <div className="card stack">
        <p className="mu">The stills of this song. The reel and the Short crop each 16:9 picture for free; Make 9:16 redraws one as a true vertical picture.</p>
        <ul className="row" style={{ listStyle: "none", padding: 0, flexWrap: "wrap" }} aria-label="Pictures">
          {imgs.map((f, i) => { const m = /pic_(\d+)/.exec(f); const k = m ? Number(m[1]) : null; return (
            <li key={f} className="stack" style={{ width: 150, gap: 4 }}>
              <a href={`/media/${d.slug}/images~${encodeURIComponent(f)}`} target="_blank" rel="noreferrer"><img src={`/media/${d.slug}/images~${encodeURIComponent(f)}?w=320`} alt={`Picture ${i + 1}`} style={{ width: "100%", aspectRatio: "16 / 9", objectFit: "cover", borderRadius: 6 }} /></a>
              {d.openai_pictures && k != null && ((vert.done ?? []).includes(k) ? <span className="mu">9:16 ready</span>
                : <button className="btn g" disabled={!!busy || !!vert.running} onClick={() => void run("Making 9:16…", () => postJSON("/api/visuals/vertical", { slug: d.slug, pics: [k] }))}>{vert.running ? "Making…" : "Make 9:16"}{" "}<span className="sr">of picture {i + 1}</span></button>)}
            </li>); })}
        </ul>
        {d.openai_pictures && d.prompt_pack && <div className="row"><button className="btn" disabled={!!busy || !!t.running} aria-busy={!!t.running} onClick={() => void run("Making 2 pictures…", () => postJSON("/api/visuals/try", { slug: d.slug }))}>{t.running ? "Making 2 pictures…" : "Try the first 2 pictures (about 10 cents)"}</button></div>}
        {(t.files ?? []).length > 0 && <div className="row">{(t.files ?? []).map((n) => <a key={n} href={`/media/${d.slug}/${n}?v=${t.v ?? 0}`} target="_blank" rel="noreferrer"><img src={`/media/${d.slug}/${n}?w=320&v=${t.v ?? 0}`} alt={`Try ${n}`} style={{ maxHeight: 120, borderRadius: 6 }} /></a>)}</div>}
        {(vert.error || t.error || err) && <p role="alert" className="mu">{vert.error || t.error || err}</p>}
      </div>
    </section>
  );
}

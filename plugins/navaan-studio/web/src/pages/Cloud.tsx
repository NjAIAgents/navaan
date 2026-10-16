import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Icon } from "../components/Icon";
import { getJSON, postJSON, type CloudData, type CloudSong } from "../lib/api";
import { errText } from "../lib/songs";

const mb = (n: number) => (n >= 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);
type Kind = "audio" | "video" | "image" | "edit" | "file";
const EDITABLE = new Set(["title.txt", "lyrics.txt", "style.txt", "instagram.txt", "quote.json", "tags.json", "brief.md"]);
// What a file can be opened as inside the app. Anything else can only be downloaded.
const kindOf = (name: string): Kind => {
  const n = name.toLowerCase();
  if (/\.(mp3|m4a|wav|aac|flac)$/.test(n)) return "audio";
  if (/\.(mp4|mov|m4v|webm)$/.test(n)) return "video";
  if (/\.(png|jpe?g|webp|gif|avif)$/.test(n)) return "image";
  if (EDITABLE.has(n)) return "edit";
  return "file";
};

function FileRow({ s, f, busy, link, err, onLink, onClose }: { s: CloudSong; f: CloudSong["files"][number]; busy: boolean; link?: string; err?: string; onLink: (key: string, then: "show" | "download") => void; onClose: (key: string) => void }) {
  const kind = kindOf(f.name); const label = f.name.replace(/^.*\//, "");
  return (
    <li className="cl-file">
      <span className="cl-name"><b>{label}</b>{f.name.includes("/") && <span className="mu"> {f.name.slice(0, f.name.lastIndexOf("/"))}</span>} <span className="mu">{mb(f.size)}</span></span>
      <span className="cl-act">
        {kind === "edit" && <Link className="btn g" to={`/studio/${s.slug.startsWith("insp") ? "inspiration" : "songs"}/${s.slug}`} aria-label={`Edit ${label} of ${s.slug}`}>Edit</Link>}
        {(kind === "audio" || kind === "video" || kind === "image") && (link
          ? <button className="btn g" onClick={() => onClose(f.key)} aria-label={`Close ${label} of ${s.slug}`}>Close</button>
          : <button className="btn g" disabled={busy} onClick={() => onLink(f.key, "show")} aria-label={`${kind === "audio" ? "Play" : kind === "video" ? "Watch" : "View"} ${label} of ${s.slug}`}>{kind === "audio" ? "Play" : kind === "video" ? "Watch" : "View"}</button>)}
        <button className="btn g" disabled={busy} onClick={() => onLink(f.key, "download")} aria-label={`Download ${label} of ${s.slug}`}><Icon name="download" /> Download</button>
      </span>
      {link && kind === "audio" && <audio className="cl-view" controls autoPlay src={link} aria-label={label} />}
      {link && kind === "video" && <video className="cl-view" controls autoPlay playsInline src={link} aria-label={label} />}
      {link && kind === "image" && <img className="cl-view" src={link} alt={label} />}
      {err && <span role="alert" className="mu cl-view">{err}</span>}
    </li>
  );
}

// What is archived in the bucket. Audio, video and pictures open inside the app through a short-lived link; the words open in the song's editor; anything can be downloaded.
export default function Cloud() {
  const [d, setD] = useState<CloudData | null>(null); const [err, setErr] = useState(""); const [busy, setBusy] = useState("");
  const [links, setLinks] = useState<Record<string, string>>({}); const [fileErr, setFileErr] = useState<Record<string, string>>({});
  const load = useCallback((fresh = false) => getJSON<CloudData>(`/api/cloud${fresh ? "?refresh=1" : ""}`).then((x) => { setD(x); setErr(""); }).catch((e) => setErr(errText(e))), []);
  useEffect(() => { void load(); }, [load]);
  const onLink = async (key: string, then: "show" | "download") => {
    setBusy(key); setFileErr((m) => ({ ...m, [key]: "" }));
    try {
      const r = await postJSON<{ url: string }>("/api/cloud/link", { key });
      if (then === "show") setLinks((m) => ({ ...m, [key]: r.url })); else window.open(r.url, "_blank", "noopener");
    } catch (e) { setFileErr((m) => ({ ...m, [key]: errText(e) })); } finally { setBusy(""); }
  };
  const onClose = (key: string) => setLinks((m) => { const n = { ...m }; delete n[key]; return n; });
  if (!d) return err ? <div className="card" role="alert"><h2>Could not load Cloud</h2><p className="mu">{err}</p></div> : <p className="mu" role="status">Loading…</p>;
  return (
    <>
      <div className="ph"><h1 className="disp">Cloud</h1><p>What is archived in the bucket.</p></div>
      {err && <div className="card" role="alert"><h2>That did not work</h2><p className="mu">{err}</p></div>}
      {!d.configured ? <div className="card"><p>No cloud storage is set up. Songs stay on this computer. <Link to="/studio/settings">Open Settings</Link></p></div>
        : d.error ? <div className="card" role="alert"><h2>The bucket could not be reached</h2><p className="mu">{d.error}</p><button className="btn" onClick={() => void load(true)}>Try again</button></div>
        : (
          <>
            <div className="row" style={{ flexWrap: "wrap" }}><p className="mu" style={{ flex: 1 }}>{d.provider} · bucket {d.bucket}{d.region ? ` · ${d.region}` : ""} · {(d.songs ?? []).length} songs</p><button className="btn g" onClick={() => void load(true)}>Refresh</button></div>
            {!(d.songs ?? []).length && <div className="card"><p className="empty">Nothing is archived yet.</p></div>}
            {(d.songs ?? []).map((s) => (
              <details key={s.slug} className="card cl">
                <summary>
                  <span className="cl-sum"><b>{s.title || s.slug}</b><span className="mu">{s.slug} · {s.files.length} files · {mb(s.bytes)}</span></span>
                  <span className="cl-chips">
                    {s.verified === false ? <span className="chip wn">Out of date</span> : s.uploaded_at ? <span className="chip ok">Verified</span> : null}
                    {s.cleaned && <span className="chip">Local copy cleaned</span>}
                  </span>
                </summary>
                <ul className="cl-files">{s.files.map((f) => <FileRow key={f.key} s={s} f={f} busy={busy === f.key} link={links[f.key]} err={fileErr[f.key]} onLink={(k, t) => void onLink(k, t)} onClose={onClose} />)}</ul>
              </details>
            ))}
          </>
        )}
    </>
  );
}

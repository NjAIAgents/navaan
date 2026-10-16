import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getJSON, postJSON, type CloudData } from "../lib/api";
import { errText } from "../lib/songs";

const mb = (n: number) => (n >= 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);

// What is archived in the bucket. A file opens through a short-lived link made on demand.
export default function Cloud() {
  const [d, setD] = useState<CloudData | null>(null); const [err, setErr] = useState(""); const [busy, setBusy] = useState("");
  const load = useCallback((fresh = false) => getJSON<CloudData>(`/api/cloud${fresh ? "?refresh=1" : ""}`).then((x) => { setD(x); setErr(""); }).catch((e) => setErr(errText(e))), []);
  useEffect(() => { void load(); }, [load]);
  const open = async (key: string) => {
    setBusy(key); setErr("");
    try { const r = await postJSON<{ url: string }>("/api/cloud/link", { key }); window.open(r.url, "_blank", "noopener"); }
    catch (e) { setErr(errText(e)); } finally { setBusy(""); }
  };
  if (!d) return err ? <div className="card" role="alert"><h2>Could not load Cloud</h2><p className="mu">{err}</p></div> : <p className="mu" role="status">Loading…</p>;
  return (
    <>
      <div className="ph"><h1 className="disp">Cloud</h1><p>What is archived in the bucket.</p></div>
      {err && <div className="card" role="alert"><h2>That did not work</h2><p className="mu">{err}</p></div>}
      {!d.configured ? <div className="card"><p>No cloud storage is set up. Songs stay on this computer. <Link to="/studio/settings">Open Settings</Link></p></div>
        : d.error ? <div className="card" role="alert"><h2>The bucket could not be reached</h2><p className="mu">{d.error}</p><button className="btn" onClick={() => void load(true)}>Try again</button></div>
        : (
          <>
            <div className="row"><p className="mu">{d.provider} · bucket {d.bucket}{d.region ? ` · ${d.region}` : ""} · {(d.songs ?? []).length} songs</p><button className="btn g" onClick={() => void load(true)}>Refresh</button></div>
            {!(d.songs ?? []).length && <div className="card"><p className="empty">Nothing is archived yet.</p></div>}
            {(d.songs ?? []).map((s) => (
              <details key={s.slug} className="card stack">
                <summary><b>{s.title || s.slug}</b> <span className="mu">{s.slug} · {s.files.length} files · {mb(s.bytes)}</span>
                  {s.verified === false ? <span className="chip wn"> Out of date</span> : s.uploaded_at ? <span className="chip ok"> Verified</span> : null}
                  {s.cleaned && <span className="chip"> Local copy cleaned</span>}
                </summary>
                <ul className="hist">{s.files.map((f) => <li key={f.key} className="stp"><span className="tx">{f.name} <span className="mu">{mb(f.size)}</span></span><button className="btn g" disabled={busy === f.key} onClick={() => void open(f.key)} aria-label={`Open ${f.name} of ${s.slug}`}>Open</button></li>)}</ul>
              </details>
            ))}
          </>
        )}
    </>
  );
}

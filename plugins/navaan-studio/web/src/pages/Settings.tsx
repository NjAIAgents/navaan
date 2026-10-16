import { useCallback, useEffect, useState } from "react";
import { getJSON, postJSON, type LoginState, type SettingsAccount, type SettingsData } from "../lib/api";
import { RISKY, gateTitle } from "../lib/gates";
import { errText } from "../lib/songs";

type Do = (act: string, body: Record<string, unknown>) => Promise<boolean>;

function Login({ s, label }: { s: LoginState; label: string }) {
  if (!s.present) return <span className="chip">{label}: not set</span>;
  if (s.ok === false) return <span className="chip bad">{label}: {s.error || "not working"}</span>;
  const d = s.days_left;
  return <span className="chip ok">{label}: working{d != null ? `, ${d < 0 ? "expired" : `${d} days left`}` : s.expires === "never" ? ", no expiry" : ""}</span>;
}

function TokenForm({ id, label, act, busy, onSave }: { id: string; label: string; act: string; busy: boolean; onSave: (token: string) => Promise<boolean> }) {
  const [v, setV] = useState(""); void act;
  return (
    <form className="stack" onSubmit={async (e) => { e.preventDefault(); if (v.trim() && await onSave(v.trim())) setV(""); }}>
      <label htmlFor={id}>{label}</label>
      <input id={id} className="field" type="password" autoComplete="off" value={v} onChange={(e) => setV(e.target.value)} />
      <button className="btn" type="submit" disabled={busy || !v.trim()}>Save token</button>
    </form>
  );
}

function YouTube({ a, which, act, busy }: { a: SettingsAccount; which: "publish" | "analytics"; act: Do; busy: boolean }) {
  const [url, setUrl] = useState(""); const [opened, setOpened] = useState(""); const [err, setErr] = useState("");
  const st = which === "publish" ? a.yt : a.yt_analytics; const name = which === "publish" ? "YouTube publishing" : "YouTube analytics";
  const start = async () => {
    setErr("");
    try { const r = await postJSON<{ url: string }>("/api/settings/yt_oauth_start", { type: a.type, which }); window.open(r.url, "_blank", "noopener"); setOpened("Opened Google in a new tab. Finish there, then paste the address of the page you end on."); }
    catch (e) { setErr(errText(e)); }
  };
  return (
    <div className="stack">
      <Login s={st} label={name} />{st.channel && <span className="mu"> channel {st.channel}</span>}
      <div className="row"><button className="btn" disabled={busy} onClick={() => void start()}>{st.present && st.ok ? `Sign in again to ${name}` : `Sign in to ${name}`}</button></div>
      {opened && <p className="mu" role="status">{opened}</p>}
      {opened && (
        <form className="stack" onSubmit={async (e) => { e.preventDefault(); if (await act("yt_oauth_finish", { type: a.type, which, url })) { setUrl(""); setOpened(""); } }}>
          <label htmlFor={`yt-${a.type}-${which}`}>Address of the page Google sent you to</label>
          <input id={`yt-${a.type}-${which}`} className="field" value={url} onChange={(e) => setUrl(e.target.value)} />
          <button className="btn p" type="submit" disabled={busy || !url.trim()}>Finish sign in</button>
        </form>
      )}
      {err && <p role="alert" className="mu">{err}</p>}
    </div>
  );
}

function Account({ a, act, busy }: { a: SettingsAccount; act: Do; busy: boolean }) {
  return (
    <section className="card stack" aria-labelledby={`ac-${a.type}`}>
      <h3 id={`ac-${a.type}`}>{a.type.charAt(0).toUpperCase() + a.type.slice(1)} {a.handle && <span className="mu">@{a.handle.replace(/^@/, "")}</span>}</h3>
      <div className="row" style={{ flexWrap: "wrap" }}><Login s={a.ig} label="Instagram" /><Login s={a.market} label="Peer data (Facebook)" /></div>
      <div className="row">
        <button className="btn" disabled={busy || !a.ig.present} onClick={() => void act("ig_refresh", { type: a.type, kind: "login" })}>Refresh Instagram token</button>
      </div>
      <TokenForm id={`ig-${a.type}`} label="New Instagram token" act="ig_save" busy={busy} onSave={(token) => act("ig_save", { type: a.type, kind: "login", token })} />
      <TokenForm id={`mk-${a.type}`} label="New Facebook token for peer data (optional)" act="ig_save" busy={busy} onSave={(token) => act("ig_save", { type: a.type, kind: "market", token })} />
      <YouTube a={a} which="publish" act={act} busy={busy} />
      <YouTube a={a} which="analytics" act={act} busy={busy} />
    </section>
  );
}

function Gates({ d, act, busy }: { d: SettingsData; act: Do; busy: boolean }) {
  const [ask, setAsk] = useState<{ id: string; on: boolean } | null>(null);
  return (
    <section className="sec" aria-labelledby="gt-h">
      <div className="sh"><h2 id="gt-h">Approvals that approve themselves</h2></div>
      <p className="mu">On means it asks you. Off means it approves itself. Switch off only the ones you never want to see.</p>
      <ul className="card hist">
        {d.gates.map((g) => (
          <li key={g.id} className="stp">
            <span className="tx"><label htmlFor={`g-${g.id}`}><b>{gateTitle(g.id)}</b>{RISKY.has(g.id) && <span className="mu"> · spends credits, publishes or deletes</span>}</label></span>
            <input id={`g-${g.id}`} type="checkbox" role="switch" checked={g.on} disabled={busy} onChange={(e) => (!e.target.checked && RISKY.has(g.id) ? setAsk({ id: g.id, on: false }) : void act("gates_save", { gates: { [g.id]: e.target.checked } }))} />
          </li>
        ))}
      </ul>
      {ask && (
        <div className="card stack" role="alertdialog" aria-label={`Confirm switching off ${gateTitle(ask.id)}`}>
          <p>{gateTitle(ask.id)} will approve itself from now on, without asking you. It {ask.id === "local_cleanup" ? "deletes local media" : ask.id === "credits" || ask.id === "captions_setup" || ask.id === "suno_download" ? "spends credits or downloads tools" : "reaches the outside world"}. Switch it off?</p>
          <div className="row">
            <button className="btn p" disabled={busy} onClick={() => void act("gates_save", { gates: { [ask.id]: false } }).then(() => setAsk(null))}>Yes, approve it automatically</button>
            <button className="btn g" onClick={() => setAsk(null)}>Keep asking me</button>
          </div>
        </div>
      )}
    </section>
  );
}

function Media({ d, act, busy }: { d: SettingsData; act: Do; busy: boolean }) {
  const m = d.media; const [edit, setEdit] = useState<Record<string, string>>({});
  const names: [string, string][] = [["image_provider", "Pictures made by"], ["picture_director", "Picture plan written by"], ["image_model", "Picture model"], ["image_quality", "Picture quality"], ["image_size_landscape", "Landscape size"], ["image_size", "Vertical size"], ["narration_source", "Narration from"], ["voice", "Voice"], ["music", "Music"], ["motion", "Motion"]];
  return (
    <section className="sec" aria-labelledby="md-h2">
      <div className="sh"><h2 id="md-h2">Pictures, narration and music</h2></div>
      <div className="card stack">
        {names.filter(([k]) => m.choices[k]).map(([k, l]) => (
          <div key={k} className="stack">
            <label htmlFor={`m-${k}`}>{l}</label>
            <select id={`m-${k}`} className="field" value={edit[k] ?? String(m.settings[k] ?? "")} onChange={(e) => setEdit({ ...edit, [k]: e.target.value })}>
              {m.choices[k].map((c) => <option key={c} value={c}>{k === "voice" ? m.voices[c] ?? c : c}</option>)}
            </select>
          </div>
        ))}
        <p className="mu">This month: OpenAI ${Number(m.usage.openai_usd ?? 0).toFixed(2)}, ElevenLabs {Math.round(Number(m.usage.eleven_seconds ?? 0))} s.</p>
        <button className="btn p" disabled={busy || !Object.keys(edit).length} onClick={() => void act("media_save", { settings: edit }).then((ok) => ok && setEdit({}))}>Save these choices</button>
        {(["openai", "elevenlabs"] as const).map((p) => (
          <div key={p} className="stack">
            <span className={`chip ${m.keys[p] ? "ok" : ""}`}>{p === "openai" ? "OpenAI" : "ElevenLabs"} key: {m.keys[p] ? "saved" : "not set"}</span>
            <TokenForm id={`key-${p}`} label={`${p === "openai" ? "OpenAI" : "ElevenLabs"} key`} act="media_key" busy={busy} onSave={(token) => act("media_key", { provider: p, token })} />
          </div>
        ))}
      </div>
    </section>
  );
}

function AddAccount({ act, busy }: { act: Do; busy: boolean }) {
  const [t, setT] = useState(""); const [h, setH] = useState(""); const [c, setC] = useState("");
  return (
    <form className="stack" onSubmit={async (e) => { e.preventDefault(); if (await act("account", { type: t.trim(), handle: h.trim(), channel: c.trim() })) { setT(""); setH(""); setC(""); } }}>
      <h3>Add a content type with its own accounts</h3>
      <label htmlFor="na-t">Short name (for example inspiration)</label><input id="na-t" className="field" value={t} onChange={(e) => setT(e.target.value)} />
      <label htmlFor="na-h">Instagram handle</label><input id="na-h" className="field" value={h} onChange={(e) => setH(e.target.value)} />
      <label htmlFor="na-c">YouTube channel</label><input id="na-c" className="field" value={c} onChange={(e) => setC(e.target.value)} />
      <button className="btn" type="submit" disabled={busy || !t.trim()}>Add</button>
    </form>
  );
}

export default function Settings() {
  const [d, setD] = useState<SettingsData | null>(null); const [err, setErr] = useState(""); const [busy, setBusy] = useState(false); const [ok, setOk] = useState("");
  const load = useCallback((fresh = false) => getJSON<SettingsData>(`/api/settings${fresh ? "?refresh=1" : ""}`).then((x) => { setD(x); setErr(""); }).catch((e) => setErr(errText(e))), []);
  useEffect(() => { void load(); }, [load]);
  const act: Do = async (path, body) => {
    setBusy(true); setOk("");
    try { await postJSON(`/api/settings/${path}`, body); setErr(""); setOk("Saved."); await load(path.startsWith("ig_") || path.startsWith("yt_") || path === "claude_save"); return true; }
    catch (e) { setErr(errText(e)); return false; } finally { setBusy(false); }
  };
  if (!d) return err ? <div className="card" role="alert"><h2>Could not load Settings</h2><p className="mu">{err}</p></div> : <p className="mu" role="status">Checking the logins…</p>;
  return (
    <>
      <div className="ph"><h1 className="disp">Settings</h1><p>Connections, approvals that approve themselves, and the services that make pictures and narration.</p></div>
      {err && <div className="card" role="alert"><h2>That did not work</h2><p className="mu">{err}</p></div>}
      {ok && <p className="mu" role="status">{ok}</p>}
      <section className="sec" aria-labelledby="cn-h">
        <div className="sh"><h2 id="cn-h">Connections</h2><button className="btn g" disabled={busy} onClick={() => void load(true)}>Check again</button></div>
        <p className="mu">Checked {new Date(d.checked_at).toLocaleString()}. A token is never shown here after you save it.</p>
        {d.accounts.map((a) => <Account key={a.type} a={a} act={act} busy={busy} />)}
        <section className="card stack" aria-labelledby="cl-h">
          <h3 id="cl-h">Claude</h3>
          <span className={`chip ${d.claude.state === "ok" ? "ok" : "bad"}`}>{d.claude.state === "ok" ? `Working (${d.claude.credential || "signed in"})` : d.claude.state === "missing" ? "No token" : `Problem: ${d.claude.state}`}</span>
          <TokenForm id="claude-token" label="Claude token (run claude setup-token where Claude Code is signed in)" act="claude_save" busy={busy} onSave={(token) => act("claude_save", { token })} />
        </section>
      </section>
      <section className="card stack" aria-labelledby="ex-h">
        <h2 id="ex-h">YouTube app and extra accounts</h2>
        <span className={`chip ${d.secret_present ? "ok" : "bad"}`}>YouTube app file: {d.secret_present ? "saved" : "not set"}</span>
        <label htmlFor="yt-secret">YouTube client secret file (the JSON from Google Cloud)</label>
        <input id="yt-secret" className="field" type="file" accept=".json,application/json" disabled={busy} onChange={async (e) => { const f = e.target.files?.[0]; if (f) await act("yt_secret", { content: await f.text() }); }} />
        <AddAccount act={act} busy={busy} />
      </section>
      <Gates d={d} act={act} busy={busy} />
      <Media d={d} act={act} busy={busy} />
      <section className="sec" aria-labelledby="cs-h">
        <div className="sh"><h2 id="cs-h">Cloud storage</h2></div>
        <div className="card stack">
          <p>{d.cloud.provider === "none" ? "No cloud storage is set up." : <>Provider <b>{d.cloud.provider}</b>, bucket <b>{d.cloud.bucket || "not set"}</b>{d.cloud.region && <>, region <b>{d.cloud.region}</b></>}.</>}</p>
          <p className="mu">Where songs are archived is set in the project config. The Cloud page shows what is in the bucket and whether each copy is verified.</p>
        </div>
      </section>
    </>
  );
}

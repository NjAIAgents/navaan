import { useCallback, useEffect, useState } from "react";
import { getJSON, postJSON, type LoginState, type SettingsAccount, type SettingsData } from "../lib/api";
import { RISKY, gateTitle } from "../lib/gates";
import { errText } from "../lib/songs";

type Do = (act: string, body: Record<string, unknown>) => Promise<boolean>;
type Save = (act: string, body: Record<string, unknown>) => Promise<{ ok: boolean; message: string }>;
type Kind = "ok" | "wn" | "bad";
type Status = { kind: Kind; text: string };
type Tab = "accounts" | "ai" | "automation" | "storage";
const TABS: [Tab, string][] = [["accounts", "Accounts"], ["ai", "AI services"], ["automation", "Automation"], ["storage", "Storage"]];

// One line that says how a login is doing.
function loginStatus(s: LoginState, none = "Not set up"): Status {
  if (!s.present) return { kind: "wn", text: none };
  if (s.ok === false) return { kind: "bad", text: s.error || "Not working" };
  const d = s.days_left;
  if (d != null && d <= 7) return { kind: "wn", text: d < 0 ? "Expired" : `Works, expires in ${d} day${d === 1 ? "" : "s"}` };
  return { kind: "ok", text: d != null ? `Working, ${d} days left` : s.expires === "never" ? "Working, no expiry" : "Working" };
}

// A row that folds open: the name, how it is doing in one line, and what you can do. Closed rows keep the page short.
function Row({ id, name, status, action = "Change", open, onToggle, children }: { id: string; name: string; status: Status; action?: string; open: boolean; onToggle: () => void; children: React.ReactNode }) {
  return (
    <div className="card fold" id={`row-${id}`}>
      <button className="fold-head" aria-expanded={open} aria-controls={`body-${id}`} onClick={onToggle}>
        <b>{name}</b><span className={`chip ${status.kind === "ok" ? "ok" : status.kind}`}>{status.text}</span><span className="fold-act mu">{open ? "Close" : action}</span>
      </button>
      {open && <div className="fold-body stack" id={`body-${id}`}>{children}</div>}
    </div>
  );
}

type Saved = { ok: boolean; message: string };

// A secret is pasted here and never shown again. The answer (saved, or exactly why not) appears right under the box, where you are looking, not at the top of the page.
function TokenForm({ id, label, busy, onSave }: { id: string; label: string; act?: string; busy: boolean; onSave: (token: string) => Promise<Saved> }) {
  const [v, setV] = useState(""); const [res, setRes] = useState<Saved | null>(null); const [working, setWorking] = useState(false);
  return (
    <form className="stack" onSubmit={async (e) => { e.preventDefault(); if (!v.trim()) return; setWorking(true); setRes(null); const r = await onSave(v.trim()); setWorking(false); setRes(r); if (r.ok) setV(""); }}>
      <label htmlFor={id}>{label}</label>
      <input id={id} className="field" type="password" autoComplete="off" value={v} onChange={(e) => { setV(e.target.value); setRes(null); }} />
      <button className="btn" type="submit" disabled={busy || working || !v.trim()}>{working ? "Checking…" : "Save token"}</button>
      {res && <p role={res.ok ? "status" : "alert"} className={res.ok ? "mu" : ""} style={res.ok ? undefined : { color: "var(--bad)" }}>{res.message}</p>}
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
      {st.channel && <p className="mu">Channel {st.channel}</p>}
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

// Songs you publish are shown on the site only once their licence is confirmed. With this on they are confirmed for you, with your statement as the reason; off, you confirm each one.
function Licence({ d, act, busy }: { d: SettingsData; act: Do; busy: boolean }) {
  const l = d.licence; const [text, setText] = useState(l?.statement || l?.suggested || ""); const [err, setErr] = useState("");
  if (!l) return null;
  const set = async (auto: boolean) => { setErr(""); if (auto && !text.trim()) return setErr("Write the statement first."); await act("licence_save", { auto, statement: text }); };
  return (
    <section className="sec" aria-labelledby="lic-h">
      <div className="sh"><h2 id="lic-h">Licence of new songs</h2></div>
      <div className="card stack">
        <p className="mu">A song is shown to listeners only when its licence is confirmed. Switch this on and every song you publish is confirmed automatically, with the statement below recorded as the reason and "owner (auto-confirm setting)" as who decided. A song you marked not allowed is never changed. Off, you confirm each one yourself.</p>
        <label htmlFor="lic-text">Your statement (in your own words)</label>
        <textarea id="lic-text" className="field" rows={3} maxLength={400} value={text} disabled={busy} onChange={(e) => setText(e.target.value)} />
        <label className="row" style={{ gap: 10 }}><input type="checkbox" role="switch" checked={l.auto} disabled={busy} onChange={(e) => void set(e.target.checked)} /> Confirm the licence of songs I publish automatically</label>
        {l.auto && <p className="mu" role="status">On since {l.set_at ? new Date(l.set_at).toLocaleString() : "now"}{l.set_by ? ` by ${l.set_by}` : ""}.</p>}
        {err && <p role="alert" style={{ color: "var(--bad)" }}>{err}</p>}
      </div>
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


function AddAccount({ act, busy }: { act: Do; busy: boolean }) {
  const [t, setT] = useState(""); const [h, setH] = useState(""); const [c, setC] = useState("");
  return (
    <form className="stack" onSubmit={async (e) => { e.preventDefault(); if (await act("account", { type: t.trim(), handle: h.trim(), channel: c.trim() })) { setT(""); setH(""); setC(""); } }}>
      <h3>Add a content type</h3><p className="mu">A content type has its own Instagram and YouTube accounts, for example Inspiration.</p>
      <label htmlFor="na-t">Short name (for example inspiration)</label><input id="na-t" className="field" value={t} onChange={(e) => setT(e.target.value)} />
      <label htmlFor="na-h">Instagram handle</label><input id="na-h" className="field" value={h} onChange={(e) => setH(e.target.value)} />
      <label htmlFor="na-c">YouTube channel</label><input id="na-c" className="field" value={c} onChange={(e) => setC(e.target.value)} />
      <button className="btn" type="submit" disabled={busy || !t.trim()}>Add</button>
    </form>
  );
}



// What each service needs a person to do, worst first. A Fix button opens the right tab and folds the right row open.
// A channel that posts to YouTube only (The Aha-lorithm, NAV-67) has no Instagram login to show.
const YT_ONLY = new Set(["aha"]);
const accountName = (t: string) => (t === "aha" ? "The Aha-lorithm" : t.charAt(0).toUpperCase() + t.slice(1));
type Item = { id: string; tab: Tab; name: string; status: Status };
function overview(d: SettingsData): Item[] {
  const items: Item[] = [];
  for (const a of d.accounts) {
    const t = accountName(a.type);
    if (!YT_ONLY.has(a.type)) items.push({ id: `ig-${a.type}`, tab: "accounts", name: `${t}: Instagram`, status: loginStatus(a.ig) });
    items.push({ id: `yt-${a.type}`, tab: "accounts", name: `${t}: YouTube publishing`, status: loginStatus(a.yt) });
  }
  items.push({ id: "claude", tab: "ai", name: "Claude", status: d.claude.state === "ok" ? { kind: "ok", text: `Working (${d.claude.credential || "signed in"})` } : d.claude.state === "missing" ? { kind: "wn", text: "No token" } : { kind: "bad", text: `Problem: ${d.claude.state}` } });
  for (const p of ["openai", "elevenlabs"] as const) items.push({ id: p, tab: "ai", name: p === "openai" ? "OpenAI" : "ElevenLabs", status: d.media.keys[p] ? { kind: "ok", text: "Key saved" } : { kind: "wn", text: "No key" } });
  items.push({ id: "cloud", tab: "storage", name: "Cloud storage", status: d.cloud.provider === "none" ? { kind: "wn", text: "Not set up" } : { kind: "ok", text: d.cloud.bucket || d.cloud.provider } });
  const rank = { bad: 0, wn: 1, ok: 2 };
  return items.map((x, i) => ({ x, i })).sort((a, b) => rank[a.x.status.kind] - rank[b.x.status.kind] || a.i - b.i).map(({ x }) => x);
}

function Board({ items, go }: { items: Item[]; go: (i: Item) => void }) {
  const bad = items.filter((i) => i.status.kind !== "ok").length;
  return (
    <section className="sec" aria-labelledby="ov-h">
      <div className="sh"><h2 id="ov-h">At a glance</h2><span className="n">{bad ? `${bad} need${bad === 1 ? "s" : ""} you` : "All good"}</span></div>
      <ul className="card hist">
        {items.map((i) => (
          <li key={i.id} className="stp">
            <span className="tx"><b>{i.name}</b></span><span className={`chip ${i.status.kind === "ok" ? "ok" : i.status.kind}`}>{i.status.text}</span>
            {i.status.kind !== "ok" && <button className="btn" onClick={() => go(i)} aria-label={`Fix ${i.name}`}>Fix</button>}
          </li>
        ))}
      </ul>
    </section>
  );
}

function AccountsTab({ d, act, save, busy, open, toggle }: { d: SettingsData; act: Do; save: Save; busy: boolean; open: string; toggle: (id: string) => void }) {
  return (
    <div className="stack">
      {d.accounts.map((a) => {
        const t = accountName(a.type); const on = (id: string) => open === id; const tg = (id: string) => () => toggle(id); const ytOnly = YT_ONLY.has(a.type);
        return (
          <section key={a.type} className="stack" aria-label={t}>
            <h3>{t} {(ytOnly ? a.youtube_channel : a.handle) && <span className="mu">@{(ytOnly ? a.youtube_channel : a.handle).replace(/^@/, "")}</span>}</h3>
            {!ytOnly && <><Row id={`ig-${a.type}`} name="Instagram" status={loginStatus(a.ig)} open={on(`ig-${a.type}`)} onToggle={tg(`ig-${a.type}`)}>
              <div className="row"><button className="btn" disabled={busy || !a.ig.present} onClick={() => void act("ig_refresh", { type: a.type, kind: "login" })}>Refresh the token</button></div>
              <TokenForm id={`ig-tok-${a.type}`} label="New Instagram token" busy={busy} onSave={(token) => save("ig_save", { type: a.type, kind: "login", token })} />
            </Row>
            <Row id={`mk-${a.type}`} name="Competitor data (optional)" status={loginStatus(a.market, "Not set")} open={on(`mk-${a.type}`)} onToggle={tg(`mk-${a.type}`)}>
              <p className="mu">A Facebook token that lets the analytics compare you with other accounts. You can leave it empty.</p>
              <TokenForm id={`mk-tok-${a.type}`} label="New Facebook token for competitor data" busy={busy} onSave={(token) => save("ig_save", { type: a.type, kind: "market", token })} />
            </Row></>}
            <Row id={`yt-${a.type}`} name="YouTube publishing" status={loginStatus(a.yt)} action={a.yt.present ? "Change" : "Sign in"} open={on(`yt-${a.type}`)} onToggle={tg(`yt-${a.type}`)}><YouTube a={a} which="publish" act={act} busy={busy} /></Row>
            <Row id={`ya-${a.type}`} name="YouTube analytics" status={loginStatus(a.yt_analytics)} action={a.yt_analytics.present ? "Change" : "Sign in"} open={on(`ya-${a.type}`)} onToggle={tg(`ya-${a.type}`)}><YouTube a={a} which="analytics" act={act} busy={busy} /></Row>
          </section>
        );
      })}
      <section className="stack" aria-label="Advanced">
        <h3>Advanced</h3>
        <Row id="yt-app" name="YouTube app file" status={d.secret_present ? { kind: "ok", text: "Saved" } : { kind: "wn", text: "Not set" }} open={open === "yt-app"} onToggle={() => toggle("yt-app")}>
          <label htmlFor="yt-secret">The JSON file from Google Cloud (OAuth client)</label>
          <input id="yt-secret" className="field" type="file" accept=".json,application/json" disabled={busy} onChange={async (e) => { const f = e.target.files?.[0]; if (f) await act("yt_secret", { content: await f.text() }); }} />
        </Row>
        <Row id="add-type" name="Add a content type" status={{ kind: "ok", text: `${d.accounts.length} now` }} action="Add" open={open === "add-type"} onToggle={() => toggle("add-type")}><AddAccount act={act} busy={busy} /></Row>
      </section>
    </div>
  );
}

function AiTab({ d, save, act, busy, open, toggle }: { d: SettingsData; save: Save; act: Do; busy: boolean; open: string; toggle: (id: string) => void }) {
  const m = d.media; const [edit, setEdit] = useState<Record<string, string>>({});
  const groups: [string, [string, string][]][] = [
    ["Pictures", [["image_provider", "Made by"], ["picture_director", "Plan written by"], ["image_model", "Model"], ["image_quality", "Quality"], ["image_size_landscape", "Landscape size"], ["image_size", "Vertical size"]]],
    ["Narration, music and motion", [["narration_source", "Narration from"], ["voice", "Voice"], ["music", "Music"], ["motion", "Motion"]]],
  ];
  const claude = overview(d).find((i) => i.id === "claude")!.status;
  return (
    <div className="stack">
      <section className="stack" aria-label="Keys">
        <h3>Keys</h3>
        <Row id="claude" name="Claude" status={claude} open={open === "claude"} onToggle={() => toggle("claude")}>
          <TokenForm id="claude-token" label="Claude token (run claude setup-token where Claude Code is signed in)" busy={busy} onSave={(token) => save("claude_save", { token })} />
        </Row>
        {(["openai", "elevenlabs"] as const).map((p) => (
          <Row key={p} id={p} name={p === "openai" ? "OpenAI" : "ElevenLabs"} status={m.keys[p] ? { kind: "ok", text: "Key saved" } : { kind: "wn", text: "No key" }} open={open === p} onToggle={() => toggle(p)}>
            <p className="mu">{p === "openai" ? "Makes the pictures and posters." : "Makes the narration. The key needs Text to Speech."}</p>
            <TokenForm id={`key-${p}`} label={`${p === "openai" ? "OpenAI" : "ElevenLabs"} key`} busy={busy} onSave={(token) => save("media_key", { provider: p, token })} />
          </Row>
        ))}
        <p className="mu">This month: OpenAI ${Number(m.usage.openai_usd ?? 0).toFixed(2)}, ElevenLabs {Math.round(Number(m.usage.eleven_seconds ?? 0))} seconds.</p>
      </section>
      {groups.map(([title, names]) => (
        <section key={title} className="card stack" aria-label={title}>
          <h3>{title}</h3>
          {names.filter(([k]) => m.choices[k]).map(([k, l]) => (
            <div key={k} className="stack">
              <label htmlFor={`m-${k}`}>{l}</label>
              <select id={`m-${k}`} className="field" value={edit[k] ?? String(m.settings[k] ?? "")} onChange={(e) => setEdit({ ...edit, [k]: e.target.value })}>
                {m.choices[k].map((c) => <option key={c} value={c}>{k === "voice" ? m.voices[c] ?? c : c}</option>)}
              </select>
            </div>
          ))}
        </section>
      ))}
      <div className="row"><button className="btn p" disabled={busy || !Object.keys(edit).length} onClick={() => void act("media_save", { settings: edit }).then((ok) => ok && setEdit({}))}>Save these choices</button></div>
    </div>
  );
}

function StorageTab({ d }: { d: SettingsData }) {
  return (
    <section className="card stack" aria-label="Cloud storage">
      <h3>Cloud storage</h3>
      <p>{d.cloud.provider === "none" ? "No cloud storage is set up." : <>Provider <b>{d.cloud.provider}</b>, bucket <b>{d.cloud.bucket || "not set"}</b>{d.cloud.region && <>, region <b>{d.cloud.region}</b></>}.</>}</p>
      <p className="mu">Where songs are archived is set in the project config. The Cloud page shows what is in the bucket and whether each copy is verified.</p>
    </section>
  );
}

export default function Settings() {
  const [d, setD] = useState<SettingsData | null>(null); const [err, setErr] = useState(""); const [busy, setBusy] = useState(false); const [ok, setOk] = useState("");
  const [tab, setTab] = useState<Tab>("accounts"); const [open, setOpen] = useState("");
  const load = useCallback((fresh = false) => getJSON<SettingsData>(`/api/settings${fresh ? "?refresh=1" : ""}`).then((x) => { setD(x); setErr(""); }).catch((e) => setErr(errText(e))), []);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => { if (open) document.getElementById(`row-${open}`)?.scrollIntoView?.({ block: "nearest" }); }, [open, tab]);
  const act: Do = async (path, body) => {
    setBusy(true); setOk("");
    try { await postJSON(`/api/settings/${path}`, body); setErr(""); setOk("Saved."); await load(path.startsWith("ig_") || path.startsWith("yt_") || path === "claude_save"); return true; }
    catch (e) { setErr(errText(e)); return false; } finally { setBusy(false); }
  };
  const save: Save = async (path, body) => {   // a token: tested by the server first; the answer comes back to the box it was typed in
    setBusy(true);
    try { const r = await postJSON<{ note?: string }>(`/api/settings/${path}`, body); setErr(""); await load(path.startsWith("ig_") || path === "claude_save"); return { ok: true, message: r?.note || "Saved." }; }
    catch (e) { return { ok: false, message: errText(e) }; } finally { setBusy(false); }
  };
  if (!d) return err ? <div className="card" role="alert"><h2>Could not load Settings</h2><p className="mu">{err}</p></div> : <p className="mu" role="status">Checking the logins…</p>;
  const toggle = (id: string) => setOpen(open === id ? "" : id);
  return (
    <>
      <div className="ph"><h1 className="disp">Settings</h1><p>What is connected, what needs you, and how the studio makes pictures and narration.</p></div>
      {err && <div className="card" role="alert"><h2>That did not work</h2><p className="mu">{err}</p></div>}
      {ok && <p className="mu" role="status">{ok}</p>}
      <Board items={overview(d)} go={(i) => { setTab(i.tab); setOpen(i.id); }} />
      <p className="mu">Checked {new Date(d.checked_at).toLocaleString()}. A token is never shown here after you save it. <button className="btn g" disabled={busy} onClick={() => void load(true)}>Check again</button></p>
      <div className="seg" role="tablist" aria-label="Settings sections" style={{ alignSelf: "flex-start", flexWrap: "wrap" }}>
        {TABS.map(([k, label]) => <button key={k} role="tab" id={`st-${k}`} aria-selected={tab === k} aria-controls="st-panel" tabIndex={tab === k ? 0 : -1} onClick={() => { setTab(k); setOpen(""); }}>{label}</button>)}
      </div>
      <div id="st-panel" role="tabpanel" aria-labelledby={`st-${tab}`} className="stack">
        {tab === "accounts" && <AccountsTab d={d} act={act} save={save} busy={busy} open={open} toggle={toggle} />}
        {tab === "ai" && <AiTab d={d} act={act} save={save} busy={busy} open={open} toggle={toggle} />}
        {tab === "automation" && <><Gates d={d} act={act} busy={busy} /><Licence d={d} act={act} busy={busy} /></>}
        {tab === "storage" && <StorageTab d={d} />}
      </div>
    </>
  );
}

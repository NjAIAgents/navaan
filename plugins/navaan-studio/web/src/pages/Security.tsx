import { useCallback, useEffect, useState } from "react";
import { ApiError, getJSON, postJSON } from "../lib/api";
import { b2u, u2b } from "../lib/webauthn";
import { errText } from "../lib/songs";

type AuthState = { state?: string; user?: string; off?: boolean; idle_min?: number; recovery_left?: number; passkey_ok?: boolean; passkey_host_hint?: string; passkeys?: { id: string; name: string; added?: number }[] };

// How you sign in: password, recovery codes, passkeys. A wrong password step is refused by the server and counted by its lockout.
export default function Security() {
  const [s, setS] = useState<AuthState | null>(null);
  const [pw, setPw] = useState(""); const [next, setNext] = useState(""); const [codes, setCodes] = useState<string[] | null>(null);
  const [msg, setMsg] = useState(""); const [err, setErr] = useState(""); const [busy, setBusy] = useState(false); const [drop, setDrop] = useState<string | null>(null);
  const load = useCallback(() => getJSON<AuthState>("/auth/state").then(setS).catch((e) => setErr(errText(e))), []);
  useEffect(() => { void load(); }, [load]);
  const run = async (f: () => Promise<string>) => {
    setBusy(true); setErr(""); setMsg("");
    try { setMsg(await f()); } catch (e) { setErr(e instanceof ApiError ? e.message : errText(e)); } finally { setBusy(false); }
  };
  const changePw = () => run(async () => { await postJSON("/auth/password", { password: pw, new: next }); setPw(""); setNext(""); return "Password changed. Your other sessions are signed out."; });
  const renew = () => run(async () => { const r = await postJSON<{ recovery: string[] }>("/auth/recovery", { password: pw }); setCodes(r.recovery); setPw(""); await load(); return "New codes. The old ones no longer work."; });
  const remove = (id: string) => run(async () => { await postJSON("/auth/passkey/remove", { id }); setDrop(null); await load(); return "Passkey removed."; });
  const add = () => run(async () => {
    try {
      const o = await postJSON<{ ticket: string; publicKey: { challenge: string; rp: PublicKeyCredentialRpEntity; user: { id: string; name: string; displayName: string }; pubKeyCredParams: PublicKeyCredentialParameters[]; timeout?: number; authenticatorSelection?: AuthenticatorSelectionCriteria; excludeCredentials: { type: PublicKeyCredentialType; id: string }[] } }>("/auth/passkey/register-options");
      const k = o.publicKey;
      const c = await navigator.credentials.create({ publicKey: { challenge: u2b(k.challenge), rp: k.rp, user: { id: u2b(k.user.id), name: k.user.name, displayName: k.user.displayName }, pubKeyCredParams: k.pubKeyCredParams, timeout: k.timeout, attestation: "none", authenticatorSelection: k.authenticatorSelection, excludeCredentials: k.excludeCredentials.map((a) => ({ type: a.type, id: u2b(a.id) })) } }) as PublicKeyCredential | null;
      if (!c) return "Cancelled.";
      const r = c.response as AuthenticatorAttestationResponse;
      await postJSON("/auth/passkey/register", { ticket: o.ticket, clientDataJSON: b2u(r.clientDataJSON), attestationObject: b2u(r.attestationObject), name: `${navigator.platform || "This device"} passkey` });
      await load(); return "Passkey added.";
    } catch (e) { if (e instanceof ApiError) throw e; return `Passkey cancelled or failed: ${(e as Error).name || e}`; }
  });
  const signOut = async () => { try { await postJSON("/auth/logout"); } finally { location.reload(); } };
  if (!s) return err ? <div className="card" role="alert"><h2>Could not load</h2><p className="mu">{err}</p></div> : <p className="mu" role="status">Loading…</p>;
  if (s.off) return <div className="card"><h1 className="disp">Security</h1><p className="mu">Sign in is switched off for this run (NAVAAN_AUTH=off).</p></div>;
  return (
    <>
      <div className="ph"><h1 className="disp">Security</h1><p>Signed in as <b>{s.user}</b>. This browser stays signed in for {Math.round((s.idle_min ?? 0) / 1440)} days.</p></div>
      {err && <div className="card" role="alert"><h2>That did not work</h2><p className="mu">{err}</p></div>}
      {msg && <p className="mu" role="status">{msg}</p>}
      <section className="card stack" aria-labelledby="pw-h">
        <h2 id="pw-h">Password and recovery codes</h2>
        <label htmlFor="sc-pw">Current password</label><input id="sc-pw" className="field" type="password" autoComplete="current-password" value={pw} onChange={(e) => setPw(e.target.value)} />
        <label htmlFor="sc-new">New password (12 or more characters)</label><input id="sc-new" className="field" type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />
        <div className="row">
          <button className="btn p" disabled={busy || !pw || next.length < 12} onClick={() => void changePw()}>Change password</button>
          <button className="btn" disabled={busy || !pw} onClick={() => void renew()}>New recovery codes ({s.recovery_left ?? 0} left)</button>
        </div>
        {codes && <div className="stack" role="status"><p className="mu">Save these in a password manager. They are shown only now.</p><pre className="art" tabIndex={0} aria-label="New recovery codes">{codes.join("\n")}</pre></div>}
      </section>
      <section className="card stack" aria-labelledby="pk-h">
        <h2 id="pk-h">Passkeys</h2>
        {(s.passkeys ?? []).length ? (
          <ul className="hist">
            {(s.passkeys ?? []).map((p) => (
              <li key={p.id} className="stp">
                <span className="tx"><b>{p.name}</b>{p.added ? <span className="mu"> · {new Date(p.added * 1000).toLocaleDateString()}</span> : null}</span>
                {drop === p.id
                  ? <span className="row" role="group" aria-label={`Confirm removing ${p.name}`}><button className="btn p" disabled={busy} onClick={() => void remove(p.id)}>Yes, remove</button><button className="btn g" onClick={() => setDrop(null)}>Keep</button></span>
                  : <button className="btn g" disabled={busy} onClick={() => setDrop(p.id)} aria-label={`Remove ${p.name}`}>Remove</button>}
              </li>
            ))}
          </ul>
        ) : <p className="mu">No passkeys yet.</p>}
        {s.passkey_ok ? <button className="btn" disabled={busy} onClick={() => void add()}>Add a passkey (Touch ID or security key)</button> : <p className="mu">{s.passkey_host_hint || "Passkeys need the Python package cryptography."}</p>}
        <p className="mu">A passkey belongs to this web address. A new address needs a new passkey.</p>
      </section>
      <section className="card stack"><h2>This browser</h2><button className="btn" onClick={() => void signOut()}>Sign out</button></section>
    </>
  );
}

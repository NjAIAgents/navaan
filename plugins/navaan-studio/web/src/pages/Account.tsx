import { useState } from "react";
import { Link } from "react-router-dom";
import { Icon } from "../components/Icon";
import { postJSON } from "../lib/api";
import { useMe } from "../lib/me";
import { errText } from "../lib/songs";

// Your account: the plan you are on, a download of everything held about you, and deletion (typed, because it cannot be undone). The owner account cannot be deleted here.
export default function Account() {
  const me = useMe();
  const [typed, setTyped] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const remove = async () => {
    setBusy(true); setMsg("");
    try { await postJSON("/api/account/delete", { confirm: typed }); window.location.assign("/"); }
    catch (e) { setMsg(errText(e)); setBusy(false); }
  };
  return (
    <>
      <div className="ph"><h1 className="disp">Account</h1><p>Signed in as <b>{me.user}</b>.</p></div>
      <section className="card stack" aria-labelledby="ac-plan"><h2 id="ac-plan">Plan</h2><p className="mu">See what your plan includes.</p><div className="row"><Link className="btn" to="/plans"><Icon name="star" />Plans</Link></div></section>
      <section className="card stack" aria-labelledby="ac-exp"><h2 id="ac-exp">Your data</h2><p className="mu">Download everything held about you (your playlists, saved songs, plays and plan) as a file. What is kept and why is in the <a href="/privacy">privacy page</a>.</p>
        <div className="row"><a className="btn p" href="/api/account/export" download="navaan-account-export.json">Download my data</a></div></section>
      <section className="card stack" aria-labelledby="ac-del"><h2 id="ac-del">Delete my account</h2>
        <p className="mu">This removes your playlists, saved songs, plays, plan, links you shared and your sign-in. It cannot be undone.</p>
        <label htmlFor="ac-confirm">Type "delete my account" to confirm</label>
        <input id="ac-confirm" className="field" value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" />
        <div className="row"><button className="btn" disabled={busy || typed !== "delete my account"} onClick={() => void remove()}>Delete my account</button></div>
        {msg && <p role="alert" className="mu">{msg}</p>}
      </section>
    </>
  );
}

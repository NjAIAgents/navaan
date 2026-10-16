import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { getJSON, postJSON, type Filters } from "../lib/api";
import { useMe } from "../lib/me";
import { errText } from "../lib/songs";

const MOODS = ["Romantic", "Nostalgic", "Hopeful", "Reflective", "Calm", "Uplifting"];

function Chips({ label, all, on, set }: { label: string; all: string[]; on: string[]; set: (v: string[]) => void }) {
  return (
    <fieldset className="stack" style={{ border: 0, padding: 0, margin: 0 }}>
      <legend><b>{label}</b></legend>
      <div className="row" style={{ flexWrap: "wrap" }}>
        {all.map((x) => <button key={x} type="button" className={`btn${on.includes(x) ? " p" : ""}`} aria-pressed={on.includes(x)} onClick={() => set(on.includes(x) ? on.filter((y) => y !== x) : [...on, x])}>{x}</button>)}
      </div>
    </fieldset>
  );
}

// "I would like an account", from the free site: what they like (so their first playlist can start from it) and an optional email for when accounts open. Accounts are not open yet, so this says so and keeps the answers.
export default function Join() {
  const me = useMe();
  const [f, setF] = useState<Filters | null>(null);
  const [moods, setMoods] = useState<string[]>([]); const [genres, setGenres] = useState<string[]>([]); const [languages, setLanguages] = useState<string[]>([]);
  const [email, setEmail] = useState(""); const [trap, setTrap] = useState("");
  const [busy, setBusy] = useState(false); const [err, setErr] = useState(""); const [done, setDone] = useState(false);
  useEffect(() => { getJSON<Filters>("/api/catalog/filters").then(setF).catch(() => setF(null)); }, []);   // expected: without the lists the form still works with moods
  if (me.ready && !me.guest) return <Navigate to="/library" replace />;
  const send = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setErr("");
    try { await postJSON("/api/site/interest", { moods, genres, languages, email, website: trap }); setDone(true); } catch (x) { setErr(errText(x)); } finally { setBusy(false); }
  };
  if (done) return (
    <div className="card stack" style={{ maxWidth: 560 }} role="status">
      <h2>Thank you</h2>
      <p>Accounts open soon. We kept what you like{email.trim() ? ` and will write to ${email.trim()} when they do` : ""}, so your first playlist can start from it.</p>
      <div className="row"><Link className="btn p" to="/">Back to songs</Link></div>
    </div>
  );
  return (
    <>
      <div className="ph"><h1 className="disp">Create your account</h1><p>Accounts open soon. Tell us what you like and your first playlist can start from it.</p></div>
      <form className="card stack" style={{ maxWidth: 640 }} onSubmit={(e) => void send(e)}>
        <Chips label="Your mood" all={MOODS} on={moods} set={setMoods} />
        {(f?.genres.length ?? 0) > 0 && <Chips label="Genres" all={f!.genres} on={genres} set={setGenres} />}
        {(f?.languages.length ?? 0) > 0 && <Chips label="Languages" all={f!.languages} on={languages} set={setLanguages} />}
        <label htmlFor="join-email"><b>Email</b> <span className="mu">(optional, only to tell you when accounts open)</span></label>
        <input id="join-email" className="field" type="email" autoComplete="email" maxLength={254} value={email} onChange={(e) => setEmail(e.target.value)} />
        <div aria-hidden="true" style={{ position: "absolute", left: "-9999px" }}><label>Website<input tabIndex={-1} autoComplete="off" value={trap} onChange={(e) => setTrap(e.target.value)} /></label></div>
        {err && <p role="alert" style={{ color: "var(--bad)" }}>{err}</p>}
        <div className="row"><button className="btn p" type="submit" disabled={busy || !(moods.length || genres.length || languages.length || email.trim())}>{busy ? "Sending…" : "Create my account"}</button><Link className="btn g" to="/">Not now</Link></div>
      </form>
    </>
  );
}

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getJSON, postJSON, type FeedbackRow, type SongReactions } from "../../lib/api";
import { errText } from "../../lib/songs";
import { Loading } from "../../components/Loading";

// What visitors of the public site said: thumbs and "love it" per song, and the messages they sent (read, reply by email when they gave one, mark as read).
export default function Feedback() {
  const [days, setDays] = useState("30"); const [rx, setRx] = useState<SongReactions[] | null>(null); const [fb, setFb] = useState<FeedbackRow[] | null>(null); const [err, setErr] = useState(""); const [unread, setUnread] = useState(true);
  const load = useCallback(() => {
    getJSON<SongReactions[]>(`/api/site/reactions${days === "0" ? "" : `?days=${days}`}`).then(setRx).catch((e) => setErr(errText(e)));
    getJSON<FeedbackRow[]>(`/api/site/feedback?limit=100${unread ? "&unhandled=1" : ""}`).then(setFb).catch((e) => setErr(errText(e)));
  }, [days, unread]);
  useEffect(() => { load(); }, [load]);
  const mark = async (id: string, handled: boolean) => { try { await postJSON("/api/site/feedback/handle", { id, handled }); load(); } catch (e) { setErr(errText(e)); } };
  const total = (k: "up" | "down" | "love") => (rx ?? []).reduce((n, r) => n + r[k], 0);
  return (
    <>
      {err && <div className="card" role="alert"><h2>Could not load feedback</h2><p className="mu">{err}</p></div>}
      <section className="sec" aria-labelledby="rx-h">
        <div className="sh"><h2 id="rx-h">Reactions</h2><label className="sr" htmlFor="fb-days">Period</label>
          <select id="fb-days" className="field sel" value={days} onChange={(e) => setDays(e.target.value)}><option value="7">Last 7 days</option><option value="30">Last 30 days</option><option value="0">All time</option></select></div>
        {!rx ? <Loading /> : (
          <div className="card" style={{ padding: 8 }}>
            <p className="mu" style={{ padding: "4px 12px" }}>In total: {total("love")} love it, {total("up")} thumbs up, {total("down")} thumbs down.</p>
            {rx.length ? (
              <table className="rt"><thead><tr><th>Song</th><th>Love it</th><th>Thumbs up</th><th>Thumbs down</th></tr></thead>
                <tbody>{rx.map((r) => <tr key={r.slug}><td data-label="Song"><Link to={`/studio/songs/${r.slug}`}>{r.title}</Link></td><td data-label="Love it">{r.love}</td><td data-label="Thumbs up">{r.up}</td><td data-label="Thumbs down">{r.down}</td></tr>)}</tbody></table>
            ) : <p className="empty">No songs yet.</p>}
          </div>
        )}
      </section>
      <section className="sec" aria-labelledby="fm-h">
        <div className="sh"><h2 id="fm-h">Messages</h2><button className="btn g" aria-pressed={unread} onClick={() => setUnread(!unread)}>{unread ? "Showing unread" : "Showing all"}</button></div>
        {!fb ? <Loading /> : !fb.length ? <div className="card"><p className="empty">{unread ? "No unread messages." : "No messages yet."}</p></div> : fb.map((f) => (
          <article key={f.id} className="card stack" aria-label={`Message from ${f.email ?? "a visitor"}`}>
            <p className="mu">{new Date(f.created_at).toLocaleString()} · {f.slug ? <Link to={`/studio/songs/${f.slug}`}>{f.title}</Link> : "about the site"} · {f.email ? <a href={`mailto:${f.email}?subject=${encodeURIComponent(f.title ? `About ${f.title} on NAVAAN` : "Your feedback on NAVAAN")}`}>{f.email}</a> : "no email given"}</p>
            <p style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{f.message}</p>
            <div className="row"><button className="btn" onClick={() => void mark(f.id, !f.handled_at)}>{f.handled_at ? "Mark as unread" : "Mark as read"}</button></div>
          </article>
        ))}
      </section>
    </>
  );
}

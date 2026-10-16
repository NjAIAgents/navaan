import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Icon } from "../components/Icon";
import { PlayButton } from "../components/PlayButton";
import { getJSON, postJSON, type PlaylistDetail } from "../lib/api";
import { errText } from "../lib/songs";

const VIS = ["private", "unlisted", "public"] as const;

// One playlist: rename, change who can see it, put songs in the order you like (up and down, which works with a keyboard and a thumb), remove them, delete the list.
export default function Playlist() {
  const { id = "" } = useParams();
  const go = useNavigate();
  const [p, setP] = useState<PlaylistDetail | null>(null);
  const [name, setName] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const load = useCallback(() => getJSON<PlaylistDetail>(`/api/playlists/${id}`).then((x) => { setP(x); setName(x.name); setErr(""); }).catch((e) => setErr(errText(e))), [id]);
  useEffect(() => { void load(); }, [load]);
  const act = async (path: string, body: Record<string, unknown>) => { setBusy(true); try { await postJSON(path, { id, ...body }); setErr(""); await load(); } catch (e) { setErr(errText(e)); } finally { setBusy(false); } };
  if (!p) return err ? <div className="card" role="alert"><h2>Could not open this playlist</h2><p className="mu">{err}</p><Link className="btn" to="/library">Back to Library</Link></div> : <p className="mu" role="status">Loading…</p>;
  const t = p.tracks; const mine = p.mine !== false;
  const queue = t.map((x) => ({ slug: x.slug, title: x.title }));
  const up = (i: number) => act("/api/playlists/move", { slug: t[i].slug, after: i >= 2 ? t[i - 2].slug : "" });   // after the song two above, or to the top
  const down = (i: number) => act("/api/playlists/move", { slug: t[i].slug, after: t[i + 1].slug });
  return (
    <>
      <div className="ph"><Link className="back" to="/library"><Icon name="chevron" />Library</Link><h1 className="disp">{p.name}</h1><p>{t.length} song{t.length === 1 ? "" : "s"}</p>{t.length > 0 && <div className="row"><PlayButton queue={queue} label={p.name} size="big" /></div>}</div>
      {err && <div className="card" role="alert"><p className="mu">{err}</p></div>}
      {!mine && <p className="mu" role="note">Shared with you. You can listen, but not change it.</p>}
      {mine && <form className="row" onSubmit={(e) => { e.preventDefault(); void act("/api/playlists/update", { name }); }}>
        <label className="sr" htmlFor="pl-name">Playlist name</label>
        <input id="pl-name" className="field" style={{ flex: 1, minWidth: 0 }} value={name} onChange={(e) => setName(e.target.value)} maxLength={100} />
        <label className="sr" htmlFor="pl-vis">Who can see it</label>
        <select id="pl-vis" className="field sel" value={p.visibility} onChange={(e) => void act("/api/playlists/update", { visibility: e.target.value })}>{VIS.map((v) => <option key={v} value={v}>{v}</option>)}</select>
        <button className="btn" type="submit" disabled={busy || !name.trim() || name === p.name}>Rename</button>
      </form>}
      <div className="card" style={{ padding: 8 }}>
        {t.length ? <ol className="steps">{t.map((s, i) => (
          <li key={s.slug} className="stp">
            <PlayButton slug={s.slug} title={s.title} queue={queue} label={s.title} />
            <Link className="tx" to={`/song/${s.slug}`}><b>{s.title}</b></Link>
            {mine && <><button className="btn g sq" disabled={busy || i === 0} onClick={() => void up(i)} aria-label={`Move ${s.title} up`}><span style={{ transform: "rotate(-90deg)", display: "flex" }}><Icon name="chevron" /></span></button>
            <button className="btn g sq" disabled={busy || i === t.length - 1} onClick={() => void down(i)} aria-label={`Move ${s.title} down`}><span style={{ transform: "rotate(90deg)", display: "flex" }}><Icon name="chevron" /></span></button>
            <button className="btn g" disabled={busy} onClick={() => void act("/api/playlists/remove", { slug: s.slug })} aria-label={`Remove ${s.title}`}>Remove</button></>}
          </li>
        ))}</ol> : <p className="empty">This playlist is empty. Add songs from a song's page.</p>}
      </div>
      {!mine ? null : confirm ? (
        <div className="card stack" role="group" aria-label="Confirm delete"><p>Delete "{p.name}"? Its songs stay in the catalogue.</p><div className="row"><button className="btn p" disabled={busy} onClick={() => void postJSON("/api/playlists/delete", { id }).then(() => go("/library")).catch((e) => setErr(errText(e)))}>Yes, delete</button><button className="btn g" onClick={() => setConfirm(false)}>Keep it</button></div></div>
      ) : <div className="row"><button className="btn" onClick={() => setConfirm(true)}>Delete playlist</button></div>}
    </>
  );
}

import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Cover, albumFace } from "../components/Cover";
import { Icon } from "../components/Icon";
import { PlayButton } from "../components/PlayButton";
import { ShuffleButton } from "../components/ShuffleButton";
import { AddToPlaylist } from "../components/AddToPlaylist";
import { ShareDialog } from "../components/ShareCard";
import { getJSON, type AlbumRow } from "../lib/api";
import { usePlayer } from "../lib/player";
import { errText } from "../lib/songs";
import { Loading } from "../components/Loading";

// An album as a listener sees it: its cover, who and what it is, play from the top, and the songs in order. Only songs they may hear are in it.
export default function ListenerAlbum() {
  const { slug = "" } = useParams();
  const [a, setA] = useState<AlbumRow | null>(null); const [err, setErr] = useState(""); const [sharing, setSharing] = useState(false);
  const pl = usePlayer();
  useEffect(() => { setA(null); getJSON<AlbumRow>(`/api/catalog/album/${slug}`).then(setA).catch((e) => setErr(errText(e))); }, [slug]);
  if (!a) return err ? <div className="card" role="alert"><h2>This album is not available</h2><p className="mu">{err}</p><Link className="btn" to="/">Back to Browse</Link></div> : <Loading />;
  if (a.coming_soon) return <ComingSoon a={a} />;
  const queue = a.tracks.map((t) => ({ slug: t.slug, title: t.title })); const c = a.tracks.find((t) => t.art); const f = albumFace(a); const colour = a.art?.colour ?? c?.art?.colour;
  return (
    <>
      <section className="hero" style={colour ? { background: `linear-gradient(180deg, ${colour}66, transparent 75%)` } : undefined} aria-labelledby="la-h">
        <Cover slug={f.slug} title={a.title} size={200} art={f.art} />
        <div className="hero-tx">
          <h1 id="la-h" className="disp">{a.title}</h1>
          <p className="mu">by {a.artist || "NAVAAN"}</p>
          <div className="row chips"><span className="chip">{a.kind}</span>{a.release_date && <span className="chip">{a.release_date}</span>}<span className="chip">{a.tracks.length} song{a.tracks.length === 1 ? "" : "s"}</span></div>
          {a.description && <p className="mu">{a.description}</p>}
          <div className="row"><PlayButton queue={queue} label={a.title} size="big" /><ShuffleButton queue={queue} label={a.title} /><button className="btn sq" onClick={() => setSharing(true)} aria-label="Share"><Icon name="share" /></button></div>
        </div>
      </section>
      <section className="sec" aria-labelledby="lt-h">
        <div className="sh"><h2 id="lt-h">Songs</h2><span className="n">{a.tracks.length}</span></div>
        <div className="card" style={{ padding: 8 }}>
          <ol className="steps">{a.tracks.map((t, i) => (
            <li key={t.slug} className="stp">
              <PlayButton slug={t.slug} title={t.title} queue={queue} label={t.title} />
              <Link className="tx" to={`/song/${t.slug}`}><b>{i + 1}. {t.title}</b>{pl.slug === t.slug && pl.playing && <> <span className="sr">now playing</span></>}</Link>
              <AddToPlaylist slug={t.slug} title={t.title} />
              <Icon name="chevron" />
            </li>
          ))}</ol>
        </div>
      </section>
      {sharing && <ShareDialog kind="album" slug={a.slug} title={a.title} onClose={() => setSharing(false)} />}
    </>
  );
}


const left = (ms: number) => { const m = Math.floor(ms / 60000); const d = Math.floor(m / 1440), h = Math.floor((m % 1440) / 60); return d ? `${d} day${d === 1 ? "" : "s"} ${h} h` : h ? `${h} h ${m % 60} min` : `${m % 60} min`; };

// An album announced before its release (spec 003): the cover, the date and a countdown, and the teaser clips. No songs yet: they come with the release, at this same address.
function ComingSoon({ a }: { a: AlbumRow }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 30000); return () => clearInterval(t); }, []);
  const at = a.release_at ? new Date(a.release_at).getTime() : null; const f = albumFace({ ...a, tracks: [] });   // no songs yet: the album's own cover
  return (
    <>
      <section className="hero" aria-labelledby="cs-h">
        <Cover slug={f.slug} title={a.title} size={200} art={f.art} />
        <div className="hero-tx">
          <h1 id="cs-h" className="disp">{a.title}</h1>
          <p className="mu">by {a.artist || "NAVAAN"}</p>
          <div className="row chips"><span className="chip">{a.kind}</span><span className="chip ok">Coming soon</span></div>
          <p role="status">{at === null ? "Release date to be announced." : at <= now ? "Releasing now." : `Out ${new Date(at).toLocaleString([], { day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit" })}, in ${left(at - now)}.`}</p>
          {a.description && <p className="mu">{a.description}</p>}
        </div>
      </section>
      {(a.teasers ?? []).length > 0 && (
        <section className="sec" aria-labelledby="cs-t">
          <div className="sh"><h2 id="cs-t">Teasers</h2></div>
          <div className="card stack">{(a.teasers ?? []).map((t) => <a key={t.url} className="btn" href={t.url} target="_blank" rel="noopener noreferrer">{t.platform === "instagram" ? "Watch on Instagram" : "Watch the Short on YouTube"}</a>)}</div>
        </section>
      )}
    </>
  );
}

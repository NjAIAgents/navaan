import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Cover } from "../components/Cover";
import { Icon } from "../components/Icon";
import { PlayButton } from "../components/PlayButton";
import { ShuffleButton } from "../components/ShuffleButton";
import { AddToPlaylist } from "../components/AddToPlaylist";
import { getJSON, type AlbumRow } from "../lib/api";
import { usePlayer } from "../lib/player";
import { errText } from "../lib/songs";
import { Loading } from "../components/Loading";

// An album as a listener sees it: its cover, who and what it is, play from the top, and the songs in order. Only songs they may hear are in it.
export default function ListenerAlbum() {
  const { slug = "" } = useParams();
  const [a, setA] = useState<AlbumRow | null>(null); const [err, setErr] = useState("");
  const pl = usePlayer();
  useEffect(() => { setA(null); getJSON<AlbumRow>(`/api/catalog/album/${slug}`).then(setA).catch((e) => setErr(errText(e))); }, [slug]);
  if (!a) return err ? <div className="card" role="alert"><h2>This album is not available</h2><p className="mu">{err}</p><Link className="btn" to="/">Back to Browse</Link></div> : <Loading />;
  const queue = a.tracks.map((t) => ({ slug: t.slug, title: t.title })); const c = a.tracks.find((t) => t.art);
  return (
    <>
      <section className="hero" style={c?.art?.colour ? { background: `linear-gradient(180deg, ${c.art.colour}66, transparent 75%)` } : undefined} aria-labelledby="la-h">
        <Cover slug={c?.slug ?? a.tracks[0].slug} title={a.title} size={200} art={c?.art} />
        <div className="hero-tx">
          <h1 id="la-h" className="disp">{a.title}</h1>
          <div className="row chips"><span className="chip">{a.kind}</span>{a.release_date && <span className="chip">{a.release_date}</span>}<span className="chip">{a.tracks.length} song{a.tracks.length === 1 ? "" : "s"}</span></div>
          {a.description && <p className="mu">{a.description}</p>}
          <div className="row"><PlayButton queue={queue} label={a.title} size="big" /><ShuffleButton queue={queue} label={a.title} /></div>
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
    </>
  );
}

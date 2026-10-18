import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Cover } from "../components/Cover";
import { Equaliser } from "../components/Equaliser";
import { Icon } from "../components/Icon";
import { SongTools } from "../components/SongTools";
import { Lyrics } from "../components/Lyrics";
import { ShareDialog } from "../components/ShareCard";
import { SeekBar } from "../components/SeekBar";
import { Transport } from "../components/Transport";
import { getJSON, type TrackView } from "../lib/api";
import { usePlayer, usePosition } from "../lib/player";
import { errText } from "../lib/songs";
import { Loading } from "../components/Loading";

// A song as a listener sees it: the big cover, one round Play button, who and what it is, the lyrics (following the song when timing exists), keep, share, clip and feedback as a row of icons.
export default function ListenerSong() {
  const { slug = "" } = useParams();
  const [t, setT] = useState<TrackView | null>(null);
  const [err, setErr] = useState("");
  const [sharing, setSharing] = useState(false);
  const pl = usePlayer(); const { position, duration } = usePosition();
  useEffect(() => { setT(null); getJSON<TrackView>(`/api/catalog/track/${slug}`).then(setT).catch((e) => setErr(errText(e))); }, [slug]);
  if (!t) return err ? <div className="card" role="alert"><h2>This song is not available</h2><p className="mu">{err}</p><Link className="btn" to="/">Back to Browse</Link></div> : <Loading />;
  const mine = pl.slug === slug, playing = mine && pl.playing;
  return (
    <>
      <section className="hero" style={t.art?.colour ? { background: `linear-gradient(180deg, ${t.art.colour}66, transparent 75%)` } : undefined} aria-labelledby="song-h">
        <Cover slug={slug} title={t.title} size={240} art={t.art} />
        <div className="hero-tx">
          <h1 id="song-h" className="disp">{t.title}{playing && <> <Equaliser /></>}</h1>
          <p className="mu">{[t.language, t.genre].filter(Boolean).join(" · ")}</p>
          {t.albums.length > 0 && <p className="mu">{t.albums.map((a) => a.title).join(", ")}</p>}
          <div className="row">
            {mine ? <Transport big /> : <button className="btn p sq round" onClick={() => void pl.toggle(slug, t.title)} aria-label="Play"><Icon name="play" filled /></button>}
            {mine && <button className="btn g sq" onClick={() => pl.setExpanded(true)} aria-label="Open play mode"><Icon name="expand" /></button>}
            <button className="btn sq" onClick={() => setSharing(true)} aria-label="Share"><Icon name="share" /></button>
          </div>
          <SongTools slug={slug} title={t.title} position={mine ? position : null} duration={mine ? duration : 0} />
          {mine && <SeekBar id="song-seek" />}
          {pl.error && mine === false && <p role="alert" className="mu">{pl.error}</p>}
        </div>
      </section>
      <section className="card" aria-labelledby="ly-h"><h2 id="ly-h">Lyrics</h2><Lyrics plain={t.lyrics} timed={t.timed_lines} position={mine ? position : 0} duration={mine ? duration : 0} follow={playing} onPick={t.timed_lines || (mine && duration > 0) ? (s) => void pl.playAt(slug, t.title, s) : undefined} /></section>
      {sharing && <ShareDialog slug={slug} title={t.title} onClose={() => setSharing(false)} />}
    </>
  );
}

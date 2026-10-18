import { useEffect, useRef } from "react";
import { activeIndex, estimateLines, mmss, type TimedLine } from "../lib/lyrics";

// Lyrics: plain text, or line by line with the current line marked when timing exists. The page follows the current line only while the song plays, and scrolls smoothly unless motion is reduced.
export function Lyrics({ plain, timed, position, follow, duration = 0, onPick }: { plain: string; timed: TimedLine[] | null; position: number; follow: boolean; duration?: number; onPick?: (seconds: number) => void }) {   // onPick: a line was chosen, play from there
  const guess = !timed && follow !== undefined && duration > 0 ? estimateLines(plain, duration) : null;   // measured timing is best; without it the lines follow the song roughly
  const lines = timed ?? guess;
  const cur = lines ? activeIndex(lines, position) : -1;
  const ref = useRef<HTMLLIElement>(null);
  useEffect(() => {
    if (!follow || !ref.current || cur < 0) return;
    const calm = typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
    ref.current.scrollIntoView?.({ block: "center", behavior: calm ? "auto" : "smooth" });
  }, [cur, follow]);
  if (lines) return <><ol className="lyrics" aria-label="Lyrics">{lines.map(([sec, line], i) => <li key={i} ref={i === cur ? ref : undefined} className={i === cur ? "now" : i < cur ? "past" : ""} aria-current={i === cur ? "true" : undefined}>
    {onPick ? <button type="button" className="ly-line" onClick={() => onPick(sec)}><span className="sr">{`Play from ${mmss(sec)}: ${line}`}</span><span className="ly-t" aria-hidden="true">{mmss(sec)}</span><span aria-hidden="true">{line}</span></button> : line}</li>)}</ol>{guess && <p className="mu" style={{ fontSize: 13 }}>Lines follow the song approximately{onPick ? ", so a jump may land a little off" : ""}.</p>}</>;
  return plain.trim() ? <p className="lyrics plain" aria-label="Lyrics">{plain}</p> : <p className="mu">No lyrics for this song.</p>;
}

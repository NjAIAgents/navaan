import { useEffect, useRef } from "react";
import { activeIndex, type TimedLine } from "../lib/lyrics";

// Lyrics: plain text, or line by line with the current line marked when timing exists. The page follows the current line only while the song plays, and scrolls smoothly unless motion is reduced.
export function Lyrics({ plain, timed, position, follow }: { plain: string; timed: TimedLine[] | null; position: number; follow: boolean }) {
  const cur = timed ? activeIndex(timed, position) : -1;
  const ref = useRef<HTMLLIElement>(null);
  useEffect(() => {
    if (!follow || !ref.current || cur < 0) return;
    const calm = typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
    ref.current.scrollIntoView?.({ block: "center", behavior: calm ? "auto" : "smooth" });
  }, [cur, follow]);
  if (timed) return <ol className="lyrics" aria-label="Lyrics">{timed.map(([, line], i) => <li key={i} ref={i === cur ? ref : undefined} className={i === cur ? "now" : i < cur ? "past" : ""} aria-current={i === cur ? "true" : undefined}>{line}</li>)}</ol>;
  return plain.trim() ? <p className="lyrics plain" aria-label="Lyrics">{plain}</p> : <p className="mu">No lyrics for this song.</p>;
}

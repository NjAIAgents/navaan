import { mmss } from "../lib/lyrics";
import { usePlayer, usePosition } from "../lib/player";

// Where you are in the song: a bar you can drag, and the time played and the length beside it. Shown for the song that is loaded in the player.
export function SeekBar({ id = "seek" }: { id?: string }) {
  const p = usePlayer(); const { position, duration } = usePosition();
  if (!p.slug) return null;
  const max = Math.max(1, Math.floor(duration));
  return (
    <div className="pm-bar">
      <label className="sr" htmlFor={id}>Seek</label>
      <input id={id} type="range" min={0} max={max} step={1} value={Math.min(Math.floor(position), max)} aria-valuetext={`${mmss(position)} of ${mmss(duration)}`} onChange={(e) => p.seek(Number(e.target.value))} />
      <div className="pm-times mu"><span>{mmss(position)}</span><span>{mmss(duration)}</span></div>
    </div>
  );
}

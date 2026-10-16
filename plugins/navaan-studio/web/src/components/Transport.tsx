import { Icon } from "./Icon";
import { usePlayer } from "../lib/player";

// Back, play or pause, next: the same three buttons on the bar, in play mode and on the song page. Play is always the round one.
export function Transport({ big = false }: { big?: boolean }) {
  const p = usePlayer();
  if (!p.slug) return null;
  return (
    <div className="tp" role="group" aria-label="Player controls">
      <button className={"btn g sq shuf" + (p.shuffle ? " on" : "")} onClick={() => p.setShuffle(!p.shuffle)} aria-label="Shuffle" aria-pressed={p.shuffle}><Icon name="shuffle" /></button>
      <button className="btn g sq" onClick={p.prev} aria-label="Back"><Icon name="prev" filled /></button>
      <button className={"btn p sq round" + (big ? "" : " mid")} onClick={() => void p.toggle(p.slug!, p.title)} aria-label={p.playing ? "Pause" : "Play"}><Icon name={p.playing ? "pause" : "play"} filled /></button>
      <button className="btn g sq" onClick={p.next} aria-label="Next" disabled={!p.hasNext}><Icon name="next" filled /></button>
    </div>
  );
}

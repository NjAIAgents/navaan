import { Icon } from "./Icon";
import { usePlayer } from "../lib/player";

// Mute and a slider. The level is remembered between visits. (On a phone the device's own volume buttons set the real loudness.)
export function Volume() {
  const p = usePlayer(); const off = p.muted || p.volume === 0;
  return (
    <div className="vol">
      <button className="btn g sq" onClick={p.toggleMute} aria-label={off ? "Unmute" : "Mute"} aria-pressed={off}><Icon name={off ? "mute" : "volume"} /></button>
      <label className="sr" htmlFor="vol-range">Volume</label>
      <input id="vol-range" className="vol-range" type="range" min={0} max={100} step={1} value={Math.round((off ? 0 : p.volume) * 100)} onChange={(e) => p.setVolume(Number(e.target.value) / 100)} aria-valuetext={`${Math.round((off ? 0 : p.volume) * 100)} percent`} />
    </div>
  );
}

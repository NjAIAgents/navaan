import { Icon } from "./Icon";
import { usePlayer, type QItem } from "../lib/player";

// Play a list in a random order: shuffle goes on, and a random song of the list starts (not the one already playing, which would only pause it).
export function ShuffleButton({ queue, label }: { queue: QItem[]; label: string }) {
  const p = usePlayer();
  if (queue.length < 2) return null;
  const go = () => {
    const pool = queue.filter((x) => x.slug !== p.slug); const pick = pool[Math.floor(Math.random() * pool.length)] ?? queue[0];
    p.setShuffle(true); void p.toggle(pick.slug, pick.title, queue);
  };
  return <button className="btn" onClick={go} aria-label={`Shuffle ${label}`}><Icon name="shuffle" /> Shuffle</button>;
}

import { Icon } from "./Icon";
import { usePlayer, type QItem } from "../lib/player";

// Play a song, or a whole list from its first song when `queue` is given. Round, icon only, named for assistive technology. Pause while that song (or list) is the one playing.
export function PlayButton({ queue, slug, title, label, size = "mid" }: { queue?: QItem[]; slug?: string; title?: string; label: string; size?: "mid" | "big" }) {
  const p = usePlayer();
  const first = slug ? { slug, title: title ?? slug } : queue?.[0];
  if (!first) return null;
  const here = !!p.slug && (slug ? p.slug === slug : !!queue?.some((q) => q.slug === p.slug));   // a song's own button follows that song; the list's button follows any song of the list
  const playing = here && p.playing;
  return (
    <button className={"btn p sq round" + (size === "mid" ? " mid" : "")} aria-label={playing ? `Pause ${label}` : `Play ${label}`}
      onClick={() => void p.toggle(here ? p.slug! : first.slug, here ? p.title : first.title, here ? undefined : queue)}>
      <Icon name={playing ? "pause" : "play"} filled />
    </button>
  );
}

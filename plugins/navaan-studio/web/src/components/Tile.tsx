import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Cover, type Art } from "./Cover";
import { PlayButton } from "./PlayButton";
import type { QItem } from "../lib/player";

// One tile of a grid: the cover big, the name and a line under it, an optional action pinned to the top corner (add to playlist, remove), and an optional round play button on the cover (a song, or a whole list from its first song) so it plays without opening the page.
export function Tile({ to, slug, title, sub, art, action, play }: { to: string; slug: string; title: string; sub?: string; art?: Art; action?: ReactNode; play?: { slug?: string; title?: string; queue?: QItem[]; label: string } }) {
  return (
    <div className="tw">
      <Link className="tile" to={to}><Cover slug={slug} title={title} size={160} art={art} /><b>{title}</b>{sub && <span className="s">{sub}</span>}</Link>
      {action && <div className="act">{action}</div>}
      {play && <div className="pbtn"><PlayButton slug={play.slug} title={play.title} queue={play.queue} label={play.label} /></div>}
    </div>
  );
}

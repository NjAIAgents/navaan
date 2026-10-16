import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Cover, type Art } from "./Cover";

// One tile of a grid: the cover big, the name and a line under it, and an optional action (add to playlist, play, remove) pinned to the corner.
export function Tile({ to, slug, title, sub, art, action }: { to: string; slug: string; title: string; sub?: string; art?: Art; action?: ReactNode }) {
  return (
    <div className="tw">
      <Link className="tile" to={to}><Cover slug={slug} title={title} size={160} art={art} /><b>{title}</b>{sub && <span className="s">{sub}</span>}</Link>
      {action && <div className="act">{action}</div>}
    </div>
  );
}

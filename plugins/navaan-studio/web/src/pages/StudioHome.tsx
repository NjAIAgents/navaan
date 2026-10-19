import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getJSON, type SongRow } from "../lib/api";
import { STUDIO_SUB } from "../components/Shell";

const BLURB: Record<string, string> = {
  "/studio/songs": "Every song: write, approve, edit, publish.", "/studio/inspiration": "Quote shorts and their narration.", "/studio/aha": "AI-awareness Shorts for @TheAhalorithm.", "/studio/blog": "Trending topics into a dev.to post and LinkedIn posts.", "/studio/reels": "Your own videos, edited with Claude, posted as Reels.", "/studio/approvals": "Everything waiting for your yes.",
  "/studio/schedule": "When things publish, and when they should.", "/studio/analytics": "Numbers, advice and what people said.", "/studio/cloud": "What is archived in the bucket.",
};

// The studio's front page: where to go, and what is waiting.
export default function StudioHome() {
  const [rows, setRows] = useState<SongRow[] | null>(null);
  useEffect(() => { getJSON<SongRow[]>("/api/songs").then(setRows).catch(() => setRows([])); }, []);   // expected: the tiles work without counts
  const n = (f: (r: SongRow) => boolean) => (rows ? rows.filter(f).length : null);
  const count: Record<string, string | null> = {
    "/studio/songs": rows ? `${n((r) => r.type === "music")} songs` : null,
    "/studio/inspiration": rows ? `${n((r) => r.type === "inspiration")} shorts` : null,
    "/studio/aha": rows ? `${n((r) => r.type === "aha")} shorts` : null,
    "/studio/blog": rows ? `${n((r) => r.type === "blog")} posts` : null,
    "/studio/reels": rows ? `${n((r) => r.type === "reel")} reels` : null,
    "/studio/approvals": rows ? `${n((r) => r.status === "approval" || !!r.thumb_pending)} waiting` : null,
    "/studio/schedule": rows ? `${n((r) => !!r.scheduled)} scheduled` : null,
  };
  return (
    <>
      <div className="ph"><h1 className="disp">Studio</h1><p>Make, approve, schedule and measure.</p></div>
      <div className="grid">
        {STUDIO_SUB.filter((s) => !s.soon).map((s) => (
          <Link key={s.to} className="card stack" to={s.to}>
            <h2>{s.label}</h2><p className="mu">{BLURB[s.to]}</p>{count[s.to] && <span className="chip">{count[s.to]}</span>}
          </Link>
        ))}
        <Link className="card stack" to="/studio/settings"><h2>Settings</h2><p className="mu">Connections, automatic approvals, pictures and narration.</p></Link>
      </div>
    </>
  );
}

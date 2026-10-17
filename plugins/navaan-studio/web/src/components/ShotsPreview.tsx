import type { SongDetail } from "../lib/api";
import { ZoomImage } from "./ZoomImage";
import { mmss } from "../lib/lyrics";

type Shot = { id?: number; label?: string; start?: number; end?: number; image?: string; camera?: string; scene?: string };

// The shot list as a person reads it: each picture in order, with when it is on screen, the camera move and the scene. Not the JSON.
export function ShotsPreview({ d }: { d: SongDetail }) {
  let shots: Shot[] = [];
  try { shots = (JSON.parse(d.text["shots.json"] ?? "{}") as { shots?: Shot[] }).shots ?? []; } catch { shots = []; }   // a file that is not JSON shows the raw text below instead
  if (!shots.length) return null;
  const pic = (s: Shot) => { const n = (s.image ?? "").split("/").pop(); return n ? `/media/${d.slug}/images~${n}` : ""; };
  return (
    <ol className="stack" aria-label="The shots, in order" style={{ listStyle: "none", margin: 0, padding: 0 }}>
      {shots.map((s, i) => (
        <li key={s.id ?? i} className="row" style={{ alignItems: "flex-start", gap: 14, flexWrap: "wrap" }}>
          {pic(s) ? <ZoomImage src={pic(s)} alt={`Picture for ${s.label ?? `shot ${i + 1}`}`} loading="lazy" style={{ width: 160, maxWidth: "100%", aspectRatio: "16 / 9", objectFit: "cover", borderRadius: 8 }} /> : <span className="mu">no picture yet</span>}
          <div className="stack" style={{ gap: 2, flex: "1 1 220px", minWidth: 0 }}>
            <b>{i + 1}. {s.label ?? `Shot ${i + 1}`}</b>
            <span className="mu">{typeof s.start === "number" && typeof s.end === "number" ? `${mmss(s.start)} to ${mmss(s.end)}` : ""}{s.camera ? ` · camera: ${s.camera.replace(/_/g, " ")}` : ""}</span>
            {s.scene && <span>{s.scene}</span>}
          </div>
        </li>
      ))}
    </ol>
  );
}

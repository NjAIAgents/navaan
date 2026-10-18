import { useEffect, useState, type ReactNode } from "react";
import { postJSON, type SongDetail } from "../lib/api";
import { mmss } from "../lib/lyrics";
import { errText } from "../lib/songs";
import { ShotsPreview } from "./ShotsPreview";
import { ZoomImage } from "./ZoomImage";

// What a step wrote, laid out for a person: sentences, tables and pictures instead of the file's JSON. Each view returns null when the file is missing or not what it expects,
// and the step page then shows the raw text as before, so a view can never hide something.
const parse = <T,>(text: string | undefined): T | null => { try { return text ? (JSON.parse(text) as T) : null; } catch { return null; } };   // expected: not JSON, the raw text is shown instead
const picUrl = (slug: string, rel: string, w = 360) => { const n = rel.split("/").pop(); return n ? `/media/${slug}/images~${n}?w=${w}` : ""; };
const full = (slug: string, rel: string) => `/media/${slug}/images~${rel.split("/").pop()}`;
const Facts = ({ rows }: { rows: [string, ReactNode][] }) => <dl className="facts">{rows.filter(([, v]) => v !== "" && v != null).map(([k, v]) => <div key={k}><dt className="mu">{k}</dt><dd>{v}</dd></div>)}</dl>;

// The picture plan, editable: the idea, the character, the look in one line, and the prompt of each picture. Saving changes the words only; pictures already made stay as they are.
export function PlanView({ d, done }: { d: SongDetail; done: () => Promise<unknown> | void }) {
  const pk = d.prompt_pack;
  const init = { concept: pk?.concept ?? "", character: pk?.character ?? "", style_line: pk?.style_line ?? "", prompts: Object.fromEntries((pk?.prompts ?? []).map((p) => [p.n, p.prompt])) as Record<number, string> };
  const sig = JSON.stringify(init);
  const [draft, setDraft] = useState(init); const [busy, setBusy] = useState(false); const [err, setErr] = useState(""); const [saved, setSaved] = useState(false);
  useEffect(() => { setDraft(JSON.parse(sig)); }, [sig]);   // the plan changed on the server (a redo, another save): show it
  if (!pk?.prompts?.length) return null;
  const dirty = JSON.stringify(draft) !== sig;
  const save = async () => {
    setBusy(true); setErr(""); setSaved(false);
    try { await postJSON("/api/plan/save", { slug: d.slug, concept: draft.concept, character: draft.character, style_line: draft.style_line, prompts: pk.prompts.map((p) => ({ n: p.n, prompt: draft.prompts[p.n] })) }); setSaved(true); await done(); }
    catch (e) { setErr(errText(e)); } finally { setBusy(false); }
  };
  const area = (id: string, label: string, v: string, set: (s: string) => void, rows = 3) => <><label htmlFor={id}>{label}</label><textarea id={id} className="field" rows={rows} value={v} disabled={busy} onChange={(e) => { set(e.target.value); setSaved(false); }} /></>;
  const have = new Set(d.images ?? []);
  return (
    <div className="stack" aria-label="The picture plan">
      {area("pl-concept", "The idea", draft.concept, (s) => setDraft({ ...draft, concept: s }))}
      {area("pl-char", "The character", draft.character, (s) => setDraft({ ...draft, character: s }), 4)}
      {area("pl-style", "The look, in one line", draft.style_line, (s) => setDraft({ ...draft, style_line: s }))}
      <h3>The pictures ({pk.prompts.length})</h3>
      <ol className="stack" style={{ listStyle: "none", margin: 0, padding: 0 }}>
        {pk.prompts.map((p) => {
          const rel = `images/pic_${String(p.n).padStart(2, "0")}.png`;
          return (
            <li key={p.n} className="row" style={{ alignItems: "flex-start", gap: 14, flexWrap: "wrap" }}>
              {have.has(rel.split("/")[1]) ? <ZoomImage src={picUrl(d.slug, rel, 240)} full={full(d.slug, rel)} alt={`Picture ${p.n}`} loading="lazy" style={{ width: 140, maxWidth: "100%", aspectRatio: "16 / 9", objectFit: "cover", borderRadius: 8 }} /> : <span className="mu" style={{ width: 140 }}>Not made yet</span>}
              <div className="stack" style={{ flex: "1 1 280px", minWidth: 0, gap: 4 }}>
                <b>{p.n}. {p.section}</b>{p.lyric && <span className="mu">“{p.lyric}”</span>}
                <textarea className="field" rows={4} aria-label={`Prompt for picture ${p.n}`} value={draft.prompts[p.n] ?? ""} disabled={busy} onChange={(e) => { setDraft({ ...draft, prompts: { ...draft.prompts, [p.n]: e.target.value } }); setSaved(false); }} />
              </div>
            </li>
          );
        })}
      </ol>
      <div className="row"><button className="btn p" disabled={busy || !dirty} onClick={() => void save()}>{busy ? "Saving…" : "Save the plan"}</button>{dirty && <button className="btn g" disabled={busy} onClick={() => setDraft(JSON.parse(sig))}>Undo my changes</button>}</div>
      {saved && <p className="mu" role="status">Saved. Pictures already made keep their old prompt: use Redo on “Create the pictures” (it spends credits, with your approval) to paint them from this plan.</p>}
      {err && <p role="alert" style={{ color: "var(--bad)" }}>{err}</p>}
    </div>
  );
}

type Motion = { pictures?: Record<string, { regions?: Record<string, number[][][]>; note?: string }> };
const COLOUR = ["var(--ac)", "var(--wn)", "var(--ok)", "var(--bad)", "var(--dim)"];   // theme colours, one per kind of movement, in the order the kinds appear

// What moves: only the pictures with something marked, each with the moving areas outlined and the director's note, and a count of those that stay still.
export function MotionView({ d }: { d: SongDetail }) {
  const mo = parse<Motion>(d.text?.["motion.json"]); if (!mo?.pictures) return null;
  const all = Object.entries(mo.pictures); const moving = all.filter(([, p]) => p.regions && Object.values(p.regions).some((r) => r.length));
  return (
    <div className="stack" aria-label="What moves">
      <p><b>{moving.length}</b> of {all.length} pictures move; the other {all.length - moving.length} stay still.</p>
      <div className="row" style={{ flexWrap: "wrap", alignItems: "flex-start", gap: 14 }}>
        {moving.map(([rel, p]) => (
          <figure key={rel} className="stack" style={{ margin: 0, width: 240, gap: 6 }}>
            <div style={{ position: "relative", lineHeight: 0 }}>
              <img src={picUrl(d.slug, rel, 480)} alt={`${rel.split("/").pop()} with the moving areas outlined`} loading="lazy" style={{ width: "100%", borderRadius: 8 }} />
              <svg viewBox="0 0 1 1" preserveAspectRatio="none" aria-hidden="true" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
                {Object.entries(p.regions ?? {}).flatMap(([kind, polys], k) => polys.map((poly, i) => <polygon key={`${kind}${i}`} points={poly.map((pt) => pt.join(",")).join(" ")} style={{ fill: COLOUR[k % COLOUR.length], fillOpacity: 0.25, stroke: COLOUR[k % COLOUR.length], strokeWidth: 0.006 }} />))}
              </svg>
            </div>
            <figcaption className="mu"><b>{Object.keys(p.regions ?? {}).join(", ")}</b>{p.note ? `: ${p.note}` : ""}</figcaption>
          </figure>
        ))}
      </div>
    </div>
  );
}

// The captions: every lyric line with when it starts and ends.
export function CaptionsView({ d }: { d: SongDetail }) {
  const cues = parse<[number, number, string][]>(d.text?.["caption_cues.json"]); if (!Array.isArray(cues) || !cues.length) return null;
  return (
    <div className="stack" aria-label="The captions">
      <p><b>{cues.length}</b> lines are timed to the singing.</p>
      <table className="rt"><thead><tr><th>From</th><th>To</th><th>Line</th></tr></thead>
        <tbody>{cues.map(([a, b, t], i) => <tr key={i}><td data-label="From">{mmss(a)}</td><td data-label="To">{mmss(b)}</td><td data-label="Line">{t}</td></tr>)}</tbody></table>
    </div>
  );
}

const mb = (n: number) => `${(n / 1e6).toFixed(1)} MB`;
type Report = { layout?: string; checks?: string; width?: number; height?: number; codec?: string; has_audio?: boolean; duration?: number; bytes?: number; start?: number; dur?: number };
// A finished video's facts in a row: size, length, sound, and whether the checks passed.
export function ReportView({ d, file }: { d: SongDetail; file: string }) {
  const r = parse<Report>(d.text?.[file]); if (!r) return null;
  return <Facts rows={[["Size", r.width && r.height ? `${r.width} × ${r.height}` : ""], ["Length", r.duration ? mmss(r.duration) : ""], ["Starts at", r.start !== undefined ? `${mmss(r.start)} in the song` : ""], ["Sound", r.has_audio === undefined ? "" : r.has_audio ? "yes" : "no sound"], ["File", r.bytes ? mb(r.bytes) : ""], ["Checks", r.checks ?? ""]]} />;
}

export function VisualsView({ d }: { d: SongDetail }) {
  const v = parse<{ mode?: string; layout?: string; camera?: string; scene?: string; images?: string[]; chosen_at?: string }>(d.text?.["visuals.json"]); if (!v) return null;
  return <Facts rows={[["Pictures from", v.mode === "own" ? "your own pictures or video" : v.mode ?? ""], ["Layout", v.layout ?? ""], ["Camera", v.camera ?? ""], ["Scene note", v.scene ?? ""], ["Chosen", v.chosen_at ? new Date(v.chosen_at).toLocaleString() : ""]]} />;
}

// The view for a step, or null when it has none (the page then shows the raw files).
export function stepView(d: SongDetail, id: string, done: () => Promise<unknown> | void): { node: ReactNode; raw: string[] } | null {
  switch (id) {
    case "prompts": return d.prompt_pack?.prompts?.length ? { node: <PlanView d={d} done={done} />, raw: ["prompt_pack.json"] } : null;
    case "shots": return d.text?.["shots.json"] ? { node: <ShotsPreview d={d} />, raw: ["shots.json"] } : null;
    case "motion_plan": case "motion_clips": return d.text?.["motion.json"] ? { node: <MotionView d={d} />, raw: ["motion.json"] } : null;
    case "captions": return d.text?.["caption_cues.json"] ? { node: <CaptionsView d={d} />, raw: ["caption_cues.json"] } : null;
    case "video": case "render": return d.text?.["render_report.json"] ? { node: <ReportView d={d} file="render_report.json" />, raw: ["render_report.json"] } : null;
    case "reel": return d.text?.["reel_report.json"] ? { node: <ReportView d={d} file="reel_report.json" />, raw: ["reel_report.json"] } : null;
    case "visuals_mode": return d.text?.["visuals.json"] ? { node: <VisualsView d={d} />, raw: ["visuals.json"] } : null;
    default: return null;
  }
}

import type { SongDetail } from "../lib/api";

// The cover and the images of a blog post (NAV-139): what the studio drew for it. dev.to takes the images from their public addresses (already in the post); LinkedIn's editor takes uploads, so every file has a download.
type Made = { id: string; kind: string; file: string; alt: string; after?: string | null; url?: string };
type Manifest = { cover?: Record<string, { file: string; url?: string }>; inline?: Made[]; notes?: string[] };
const read = (t?: string): Manifest | null => { try { const v = JSON.parse(t ?? ""); return v && typeof v === "object" ? v as Manifest : null; } catch { return null; } };   // expected: no images yet, or a file that is not JSON

export function PostImages({ d }: { d: SongDetail }) {
  const m = read(d.text["post_images.json"]);
  const cover = m?.cover; if (!cover?.devto) return null;
  const src = (f: string) => `/media/${d.slug}/${f}?v=${(d.files ?? {})[f] ?? 0}`;
  const dest: [string, string][] = [["devto", "dev.to cover (1000 × 420)"], ["linkedin", "LinkedIn cover (1200 × 627)"]];
  return (
    <section className="card stack" aria-label="The images of this post">
      <h3>Images</h3>
      <div className="row" style={{ flexWrap: "wrap", alignItems: "flex-start" }}>
        {dest.filter(([k]) => cover[k]).map(([k, label]) => (
          <figure key={k} className="stack" style={{ margin: 0, maxWidth: 360 }}>
            <img src={src(cover[k].file)} alt={`The ${label}`} style={{ width: "100%", borderRadius: 8 }} />
            <figcaption className="mu">{label} · <a href={src(cover[k].file)} download={cover[k].file}>Download</a>{k === "devto" ? " · already in the post's front matter" : ""}</figcaption>
          </figure>
        ))}
      </div>
      {!!m?.inline?.length && (
        <div className="row" style={{ flexWrap: "wrap", alignItems: "flex-start" }}>
          {m.inline.map((x) => (
            <figure key={x.id} className="stack" style={{ margin: 0, maxWidth: 200 }}>
              <img src={src(x.file)} alt={x.alt} style={{ width: "100%", borderRadius: 8 }} />
              <figcaption className="mu">{x.kind === "picture" ? "Picture" : "Figure"}{x.after ? ` under “${x.after}”` : ""} · <a href={src(x.file)} download={x.file}>Download</a></figcaption>
            </figure>
          ))}
        </div>
      )}
      {!!m?.notes?.length && <ul className="mu">{m.notes.map((n) => <li key={n}>{n}</li>)}</ul>}
    </section>
  );
}

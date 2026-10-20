import { useState } from "react";
import type { SongDetail } from "../lib/api";
import { frontMatter, stripMarkers, toHtml, toPlain } from "../lib/markdown";

// The finished blog post, one tab per place it goes (NAV-134): the post as that place will show it, and buttons that copy it in the format that place takes.
type Dest = { key: string; label: string; file: string; where: string };
const DESTS: Dest[] = [
  { key: "devto", label: "dev.to", file: "devto.md", where: "On dev.to choose Create Post and paste into the editor. The front matter at the top sets the title and tags." },
  { key: "linkedin_article", label: "LinkedIn article", file: "linkedin_article.md", where: "On LinkedIn choose Write article. Paste the formatted text: headings, bold, lists and links stay. Add the title in the title box." },
  { key: "linkedin_post", label: "LinkedIn post", file: "linkedin_post.md", where: "On LinkedIn choose Start a post and paste. A post takes plain text only." },
];

// rich text when the browser allows it (html and plain together), else plain text; false when nothing could be copied
export async function copyText(plain: string, html?: string): Promise<boolean> {
  try {
    if (html && typeof ClipboardItem !== "undefined" && navigator.clipboard?.write) {
      await navigator.clipboard.write([new ClipboardItem({ "text/html": new Blob([html], { type: "text/html" }), "text/plain": new Blob([plain], { type: "text/plain" }) })]); return true;
    }
    await navigator.clipboard.writeText(plain); return true;
  } catch { return false; }   // expected: a browser may refuse the clipboard; the caller shows the text selected instead
}

function CopyButton({ label, plain, html, onFail }: { label: string; plain: string; html?: string; onFail: (t: string) => void }) {
  const [state, setState] = useState<"" | "ok" | "no">("");
  const go = async () => { const ok = await copyText(plain, html); setState(ok ? "ok" : "no"); if (!ok) onFail(plain); setTimeout(() => setState(""), 2500); };
  return <button className="btn p" type="button" onClick={() => void go()}>{state === "ok" ? "Copied" : state === "no" ? "Could not copy" : label}</button>;
}

export function BlogPosts({ d }: { d: SongDetail }) {
  const here = DESTS.filter((x) => d.text[x.file]);
  const [pick, setPick] = useState(here[0]?.key ?? ""); const [shown, setShown] = useState("");
  const dest = here.find((x) => x.key === pick) ?? here[0];
  if (!dest) return <section className="card"><h2>Posts</h2><p className="mu">The posts appear here once they are written.</p></section>;
  const raw = stripMarkers(d.text[dest.file]); const fm = dest.key === "devto" ? frontMatter(raw) : { title: d.text["title.txt"]?.trim() ?? "", description: "", tags: [] as string[], body: raw };
  const html = toHtml(fm.body), plain = toPlain(fm.body);
  return (
    <section className="stack" aria-label="The finished posts">
      <div className="tabs" role="tablist" aria-label="Where the post goes">
        {here.map((x) => <button key={x.key} role="tab" id={`dest-${x.key}`} aria-selected={dest.key === x.key} aria-controls="dest-panel" onClick={() => { setPick(x.key); setShown(""); }}>{x.label}</button>)}
      </div>
      <div role="tabpanel" id="dest-panel" aria-labelledby={`dest-${dest.key}`} className="card stack">
        <p className="mu">{dest.where}</p>
        <div className="row" style={{ flexWrap: "wrap" }}>
          {dest.key === "devto" && <CopyButton label="Copy markdown" plain={raw} onFail={setShown} />}
          {dest.key === "linkedin_article" && <><CopyButton label="Copy formatted text" plain={plain} html={html} onFail={setShown} /><CopyButton label="Copy plain text" plain={plain} onFail={setShown} /></>}
          {dest.key === "linkedin_post" && <CopyButton label="Copy post" plain={plain} onFail={setShown} />}
          {fm.title && <CopyButton label="Copy title" plain={fm.title} onFail={setShown} />}
          {fm.tags.length > 0 && <CopyButton label="Copy tags" plain={fm.tags.join(", ")} onFail={setShown} />}
        </div>
        {shown && <div className="stack"><p role="alert" className="err">The browser did not allow copying. Select the text below and copy it yourself.</p><textarea className="field" readOnly rows={8} value={shown} onFocus={(e) => e.currentTarget.select()} aria-label="The text to copy" /></div>}
        {fm.title && <h3 style={{ margin: 0 }}>{fm.title}</h3>}
        {fm.description && <p className="mu">{fm.description}</p>}
        {fm.tags.length > 0 && <p>{fm.tags.map((t) => <span key={t} className="chip">#{t}</span>)}</p>}
        <div className="post-preview" aria-label={`${dest.label}, as it will look`} dangerouslySetInnerHTML={{ __html: html }} />
        <p className="mu">Claim markers such as [c3] are removed from what you copy.</p>
      </div>
    </section>
  );
}

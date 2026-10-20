import { useEffect, useState } from "react";
import { EditorContent, useEditor, type Editor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Image from "@tiptap/extension-image";
import { Markdown } from "@tiptap/markdown";
import { postJSON } from "../lib/api";
import { errText } from "../lib/songs";
import { frontMatter, stripMarkers, toHtml, withFront } from "../lib/markdown";

// A finished post on a white page (NAV-138): read it as it will look, edit it with a toolbar, preview it, save it back to its markdown file. The file stays the source of truth;
// front matter (dev.to) is edited in three fields above the page and put back together on save. Claim markers like [c3] are hidden here and gone from what is saved.
type Props = { slug: string; file: string; raw: string; devto: boolean; label: string; onSaved: () => Promise<unknown> | void; onReady?: (e: Editor) => void; onDirty?: (dirty: boolean) => void };

export function PostEditor({ slug, file, raw, devto, label, onSaved, onReady, onDirty }: Props) {
  const clean = stripMarkers(raw);
  const first = devto ? frontMatter(clean) : { title: "", description: "", tags: [] as string[], body: clean };
  const [title, setTitle] = useState(first.title); const [desc, setDesc] = useState(first.description); const [tags, setTags] = useState(first.tags.join(", "));
  const [mode, setMode] = useState<"edit" | "preview">("edit"); const [body, setBody] = useState(first.body.trim());
  const [busy, setBusy] = useState(false); const [err, setErr] = useState(""); const [saved, setSaved] = useState(""); const [url, setUrl] = useState<null | "link" | "image">(null); const [addr, setAddr] = useState("");
  const editor = useEditor({
    extensions: [StarterKit.configure({ heading: { levels: [1, 2, 3] } }), Image, Markdown],
    content: first.body.trim(), contentType: "markdown", immediatelyRender: false,
    onUpdate: ({ editor: e }) => { setBody(e.getMarkdown().trim()); setSaved(""); },
  });
  useEffect(() => { if (editor && onReady) onReady(editor); }, [editor, onReady]);
  const tagList = tags.split(",").map((t) => t.trim().toLowerCase()).filter(Boolean);
  const compose = (b = body) => (devto ? withFront(clean, { title, description: desc, tags: tagList }, b) : b + "\n");
  const [base, setBase] = useState<string | null>(null);   // what the page composes to right after the editor has read the file (it tidies the markdown a little), so only a real change counts
  useEffect(() => { if (editor && base === null) { const b = editor.getMarkdown().trim(); setBody(b); setBase(compose(b)); } }, [editor]);   // eslint-disable-line react-hooks/exhaustive-deps
  const dirty = base !== null && compose() !== base;
  useEffect(() => { onDirty?.(dirty); }, [dirty, onDirty]);   // the posting buttons wait for what is unsaved
  useEffect(() => {
    if (!dirty) return;
    const h = (e: BeforeUnloadEvent) => { e.preventDefault(); };
    window.addEventListener("beforeunload", h); return () => window.removeEventListener("beforeunload", h);
  }, [dirty]);
  const save = async () => {
    setBusy(true); setErr(""); setSaved("");
    try { await postJSON("/api/save", { slug, file, content: compose() }); await onSaved(); setSaved("Saved."); } catch (e) { setErr(errText(e)); } finally { setBusy(false); }
  };
  const tb = (name: string, on: () => void, active = false) => <button type="button" className={`btn g${active ? " on" : ""}`} aria-pressed={active} onClick={on} disabled={!editor}>{name}</button>;
  const apply = () => {
    if (!editor || !addr.trim()) return setUrl(null);
    const a = addr.trim();
    if (!/^https?:\/\//.test(a)) return setErr("Use a web address that starts with https://");
    setErr(""); url === "link" ? editor.chain().focus().extendMarkRange("link").setLink({ href: a }).run() : editor.chain().focus().setImage({ src: a }).run(); setUrl(null); setAddr("");
  };
  const c = () => editor?.chain().focus();   // a new chain for every click: a chain made at render time is about an older document
  return (
    <div className="stack" aria-label={`${label}, the editor`}>
      {devto && (
        <div className="stack">
          <label htmlFor={`pe-title-${file}`}>Title</label><input id={`pe-title-${file}`} className="field" value={title} onChange={(e) => { setTitle(e.target.value); setSaved(""); }} />
          <label htmlFor={`pe-desc-${file}`}>Description <span className="mu">({desc.length}/160)</span></label><input id={`pe-desc-${file}`} className="field" value={desc} maxLength={160} onChange={(e) => { setDesc(e.target.value); setSaved(""); }} />
          <label htmlFor={`pe-tags-${file}`}>Tags <span className="mu">(up to 4, lowercase, separated by commas)</span></label><input id={`pe-tags-${file}`} className="field" value={tags} onChange={(e) => { setTags(e.target.value); setSaved(""); }} />
        </div>
      )}
      <div className="row" role="toolbar" aria-label="Formatting" style={{ flexWrap: "wrap" }}>
        <button type="button" className={`btn${mode === "edit" ? " p" : " g"}`} aria-pressed={mode === "edit"} onClick={() => setMode("edit")}>Edit</button>
        <button type="button" className={`btn${mode === "preview" ? " p" : " g"}`} aria-pressed={mode === "preview"} onClick={() => setMode("preview")}>Preview</button>
        {mode === "edit" && <>
          {tb("Heading", () => c()?.toggleHeading({ level: 2 }).run(), !!editor?.isActive("heading", { level: 2 }))}
          {tb("Subheading", () => c()?.toggleHeading({ level: 3 }).run(), !!editor?.isActive("heading", { level: 3 }))}
          {tb("Bold", () => c()?.toggleBold().run(), !!editor?.isActive("bold"))}
          {tb("Italic", () => c()?.toggleItalic().run(), !!editor?.isActive("italic"))}
          {tb("Bullets", () => c()?.toggleBulletList().run(), !!editor?.isActive("bulletList"))}
          {tb("Numbers", () => c()?.toggleOrderedList().run(), !!editor?.isActive("orderedList"))}
          {tb("Quote", () => c()?.toggleBlockquote().run(), !!editor?.isActive("blockquote"))}
          {tb("Code", () => c()?.toggleCodeBlock().run(), !!editor?.isActive("codeBlock"))}
          {tb("Link", () => { setUrl("link"); setAddr(""); }, !!editor?.isActive("link"))}
          {tb("Image", () => { setUrl("image"); setAddr(""); })}
          {tb("Undo", () => c()?.undo().run())}{tb("Redo", () => c()?.redo().run())}
        </>}
      </div>
      {url && mode === "edit" && (
        <div className="row"><label htmlFor="pe-url">{url === "link" ? "Link address" : "Image address"}</label><input id="pe-url" className="field" value={addr} placeholder="https://" onChange={(e) => setAddr(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); apply(); } }} />
          <button type="button" className="btn p" onClick={apply}>Add</button><button type="button" className="btn g" onClick={() => { setUrl(null); setErr(""); }}>Cancel</button></div>
      )}
      <div className="paper" hidden={mode !== "edit"}><EditorContent editor={editor} aria-label={`${label}, edit`} /></div>
      {mode === "preview" && <div className="paper post-preview" aria-label={`${label}, as it will look`}>{devto && title && <h1>{title}</h1>}<div dangerouslySetInnerHTML={{ __html: toHtml(body) }} /></div>}
      <div className="row">
        <button className="btn p" type="button" disabled={busy || !dirty} aria-busy={busy} onClick={() => void save()}>Save {label.toLowerCase()}</button>
        {dirty && <span className="chip wn">Unsaved changes</span>}
        {saved && !dirty && <span className="mu" role="status">{saved}</span>}
      </div>
      {err && <p role="alert" className="err">{err}</p>}
      <p className="mu">Claim markers such as [c3] are hidden here and are not saved. Your edits replace the draft file; the copy buttons copy what you saved.</p>
    </div>
  );
}

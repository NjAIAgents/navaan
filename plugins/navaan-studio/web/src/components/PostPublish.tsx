import { useState } from "react";
import { Link } from "react-router-dom";
import { postJSON, type SongDetail } from "../lib/api";
import { errText } from "../lib/songs";

// Post what is saved on the Posts tab through the site's own API (NAV-78), with the keys saved in Settings. dev.to takes a draft first; going live is a second, deliberate press.
// LinkedIn has no API for long-form articles, so only the short post goes through it (and only once the dev.to article is live, because it links to it).
export function PostPublish({ d, target, dirty, onDone }: { d: SongDetail; target: "devto" | "linkedin_article" | "linkedin_post"; dirty?: boolean; onDone: () => Promise<unknown> | void }) {
  const [confirm, setConfirm] = useState(false); const [busy, setBusy] = useState(false); const [err, setErr] = useState(""); const [said, setSaid] = useState("");
  const st = d.blog_publish; if (!st) return null;
  const go = async (site: "devto" | "linkedin", publish = false) => {
    setBusy(true); setErr(""); setSaid(""); setConfirm(false);
    try { const r = await postJSON<{ url?: string; published?: boolean }>("/api/blog/post", { slug: d.slug, target: site, publish }); setSaid(site === "devto" ? (r.published ? "Live on dev.to." : "Saved on dev.to as a draft.") : "Posted on LinkedIn."); await onDone(); } catch (e) { setErr(errText(e)); } finally { setBusy(false); }
  };
  const keys = <Link to="/studio/settings">Settings</Link>;
  if (target === "linkedin_article") return <p className="mu" role="note">LinkedIn has no way to post a long article from outside, so this one is copy and paste: use the buttons above, then paste into LinkedIn's Write article. The short post (its own tab) is posted from here.</p>;
  const dv = st.devto, li = st.linkedin;
  return (
    <section className="card stack" aria-label={target === "devto" ? "Post to dev.to" : "Post to LinkedIn"}>
      <h3>{target === "devto" ? "Post to dev.to" : "Post to LinkedIn"}</h3>
      {target === "devto" ? (
        <>
          {!dv.key && <p className="mu">Add your dev.to key in {keys} to post from here (dev.to, Settings, Extensions, API keys).</p>}
          {dv.posted && <p role="status">{dv.published ? "Live on dev.to" : "On dev.to as a draft"}: <a href={dv.url} target="_blank" rel="noreferrer">{dv.url}</a></p>}
          {dirty && <p className="mu" role="note">You have unsaved changes: save them first, or they are not posted.</p>}
          <div className="row" style={{ flexWrap: "wrap" }}>
            <button className="btn" disabled={busy || !dv.key || !!dirty} aria-busy={busy} onClick={() => void go("devto", false)}>{dv.posted ? (dv.published ? "Update the live article" : "Update the draft") : "Save as a draft on dev.to"}</button>
            {!dv.published && !confirm && <button className="btn p" disabled={busy || !dv.key || !!dirty} onClick={() => setConfirm(true)}>Publish on dev.to</button>}
          </div>
          {confirm && <div className="stack" role="group" aria-label="Confirm publishing"><p className="mu">This makes the article public on dev.to under your name. Publish it?</p><div className="row"><button className="btn p" disabled={busy} onClick={() => void go("devto", true)}>Yes, publish</button><button className="btn g" onClick={() => setConfirm(false)}>Not yet</button></div></div>}
        </>
      ) : (
        <>
          {!li.key && <p className="mu">Add your LinkedIn token and member id in {keys} to post from here.</p>}
          {!li.text && <p className="mu">The LinkedIn post has not been written yet: run the pipeline up to "Write the short LinkedIn post".</p>}
          {!dv.published && <p className="mu">Publish the dev.to article first: the post links to it.</p>}
          {li.posted && <p role="status">Posted on LinkedIn: <a href={li.url} target="_blank" rel="noreferrer">{li.url}</a></p>}
          {dirty && <p className="mu" role="note">You have unsaved changes: save them first, or they are not posted.</p>}
          {!li.posted && !confirm && <button className="btn p" disabled={busy || !li.key || !li.text || !li.ready || !!dirty} onClick={() => setConfirm(true)}>Post to LinkedIn</button>}
          {confirm && <div className="stack" role="group" aria-label="Confirm posting"><p className="mu">This posts to your LinkedIn profile, with the dev.to article as a link card. It cannot be undone from here. Post it?</p><div className="row"><button className="btn p" disabled={busy} onClick={() => void go("linkedin")}>Yes, post</button><button className="btn g" onClick={() => setConfirm(false)}>Not yet</button></div></div>}
        </>
      )}
      {said && !err && <p role="status" className="mu">{said}</p>}
      {err && <p role="alert" className="err">{err}</p>}
    </section>
  );
}

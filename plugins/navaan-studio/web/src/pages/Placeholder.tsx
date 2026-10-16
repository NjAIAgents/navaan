import { Icon } from "../components/Icon";

// A route whose screen is a later story. Nothing is lost meanwhile: the classic view does everything this area will do.
export default function Placeholder({ title, blurb, story, hash = "" }: { title: string; blurb: string; story: string; hash?: string }) {
  return (
    <>
      <div className="ph"><h1 className="disp">{title}</h1><p>{blurb}</p></div>
      <div className="card" style={{ maxWidth: 560 }}>
        <h2>This screen is coming</h2>
        <p className="mu">It is planned as {story}. Until then the classic view has everything you need here, and nothing is lost.</p>
        <a className="btn p" href={"/legacy" + hash}><Icon name="external" /> Open in the classic view</a>
      </div>
    </>
  );
}

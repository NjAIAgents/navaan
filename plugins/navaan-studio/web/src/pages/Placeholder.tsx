// A route whose screen is a later release.
export default function Placeholder({ title, blurb }: { title: string; blurb: string }) {
  return (
    <>
      <div className="ph"><h1 className="disp">{title}</h1><p>{blurb}</p></div>
      <div className="card" style={{ maxWidth: 560 }}><p className="mu">Nothing to do here yet.</p></div>
    </>
  );
}

import { useEffect, useState } from "react";

// What shows while a screen's data is on its way. A quick answer shows nothing at all (no flash of "Loading…"); a slower one shows soft placeholder blocks in the shape of a page,
// so the content that arrives has somewhere to land. The words are always there for assistive technology.
export function Loading() {
  const [show, setShow] = useState(false);
  useEffect(() => { const t = setTimeout(() => setShow(true), 180); return () => clearTimeout(t); }, []);
  return (
    <div role="status" className="loading">
      <span className="sr">Loading…</span>
      {show && <div aria-hidden="true" className="skel"><span className="sk sk-t" /><span className="sk sk-c" /><span className="sk sk-c" /></div>}
    </div>
  );
}

import { useEffect, useState } from "react";

// The end of a paged list: it loads the next page by itself as it scrolls near (a browser without that still has the button), and says when there is no more.
export function LoadMore({ done, busy, more, noun = "songs" }: { done: boolean; busy: boolean; more: () => void; noun?: string }) {
  const [node, setNode] = useState<HTMLElement | null>(null);
  useEffect(() => {
    if (!node || done || typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver((e) => { if (e.some((x) => x.isIntersecting)) more(); }, { rootMargin: "400px" });
    io.observe(node); return () => io.disconnect();
  }, [node, done, more]);
  if (done) return null;
  return (
    <div ref={setNode} className="row" style={{ justifyContent: "center" }}>
      <button className="btn g" onClick={more} disabled={busy}>{busy ? "Loading…" : `Show more ${noun}`}</button>
    </div>
  );
}

import { useEffect, useState } from "react";

const QUERY = "(max-width: 899px)";   // the same breakpoint as base.css

export function useMobile(): boolean {
  const get = () => (typeof window !== "undefined" && window.matchMedia ? window.matchMedia(QUERY).matches : false);
  const [m, setM] = useState(get);
  useEffect(() => {
    if (!window.matchMedia) return;
    const mq = window.matchMedia(QUERY);
    const on = () => setM(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return m;
}

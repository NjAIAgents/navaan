import { useCallback, useEffect, useRef, useState } from "react";
import { getJSON } from "./api";
import { errText } from "./songs";

/** A list that arrives a page at a time. A new `path` starts over; an answer for an earlier path is ignored. `more()` fetches the next page; `done` is true once a short page came back. */
export function usePaged<T>(path: string, size = 24) {
  const [items, setItems] = useState<T[] | null>(null); const [busy, setBusy] = useState(false); const [done, setDone] = useState(false); const [err, setErr] = useState("");
  const gen = useRef(0); const count = useRef(0); const going = useRef(false);
  const fetchPage = useCallback((offset: number, g: number) => {
    going.current = true; setBusy(true);
    const sep = path.includes("?") ? "&" : "?";
    getJSON<T[]>(`${path}${sep}limit=${size}&offset=${offset}`).then((r) => {
      if (g !== gen.current) return;   // the choice changed while this was on its way
      const page = Array.isArray(r) ? r : [];
      count.current = offset + page.length; setItems((cur) => (offset === 0 ? page : [...(cur ?? []), ...page])); setDone(page.length < size);
    }).catch((e) => { if (g === gen.current) setErr(errText(e)); }).finally(() => { if (g === gen.current) { going.current = false; setBusy(false); } });
  }, [path, size]);
  useEffect(() => { gen.current += 1; count.current = 0; going.current = false; setItems(null); setDone(false); setErr(""); fetchPage(0, gen.current); }, [fetchPage]);
  const more = useCallback(() => { if (going.current || done || err) return; fetchPage(count.current, gen.current); }, [fetchPage, done, err]);
  return { items, busy, done, err, more };
}

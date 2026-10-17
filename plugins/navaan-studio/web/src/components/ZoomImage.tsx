import { useEffect, useRef, useState, type CSSProperties } from "react";

// A picture you can open large: click it (or press Enter) and it fills the screen; Escape, the Close button or a click outside puts it back.
// `src` is what shows in the page; `full` is the large version (the original, not the small copy).
export function ZoomImage({ src, full, alt, width, height, style, loading }: { src: string; full?: string; alt: string; width?: number; height?: number; style?: CSSProperties; loading?: "lazy" | "eager" }) {
  const [open, setOpen] = useState(false); const close = useRef<HTMLButtonElement>(null); const opener = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    close.current?.focus();
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") { setOpen(false); opener.current?.focus(); } };
    window.addEventListener("keydown", key); return () => window.removeEventListener("keydown", key);
  }, [open]);
  return (
    <>
      <button type="button" ref={opener} className="zoom-open" onClick={() => setOpen(true)} aria-label={`Enlarge: ${alt}`}>
        <img src={src} alt={alt} width={width} height={height} loading={loading} style={style} />
      </button>
      {open && (
        <div className="zoom-ov" role="dialog" aria-modal="true" aria-label={alt} onClick={() => { setOpen(false); opener.current?.focus(); }}>
          <img src={full ?? src} alt={alt} onClick={(e) => e.stopPropagation()} />
          <button type="button" ref={close} className="btn" onClick={(e) => { e.stopPropagation(); setOpen(false); opener.current?.focus(); }}>Close</button>
        </div>
      )}
    </>
  );
}

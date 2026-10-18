import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { Icon } from "./Icon";

// A small sheet over the page for one job (share a clip, add to a playlist, say what you think): a title, a close button, Escape closes it. A portal, so the page's own stacking order cannot put the Now playing bar over it.
export function Sheet({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  const x = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    x.current?.focus(); const key = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", key); return () => document.removeEventListener("keydown", key);
  }, [onClose]);
  return createPortal(
    <>
      <div className="scrim top" onClick={onClose} />
      <div className="card dlg stack top" role="dialog" aria-modal="true" aria-label={title}>
        <div className="row"><h2 style={{ flex: 1 }}>{title}</h2><button ref={x} className="btn g sq" onClick={onClose} aria-label="Close"><Icon name="close" /></button></div>
        {children}
      </div>
    </>,
    document.body,
  );
}

import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router-dom";
import { useMe } from "../lib/me";
import { Icon } from "./Icon";
import { THEMES, type Choice } from "../theme/themes";
import { postJSON } from "../lib/api";

type Props = { choice: Choice; onChoice: (c: Choice) => void; onClose: () => void; mobile: boolean; version?: string };

// Opened from the avatar. A popover on a desktop, a bottom sheet on a phone. Appearance is here; the full personalisation page comes with NAV-17.
export function UserMenu({ choice, onChoice, onClose, mobile, version }: Props) {
  const { studio } = useMe();
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.querySelector<HTMLElement>("button, a")?.focus();
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    const away = (e: MouseEvent) => { if (!mobile && ref.current && !ref.current.contains(e.target as Node) && !(e.target as Element).closest?.(".who")) onClose(); };
    document.addEventListener("keydown", key);
    document.addEventListener("mousedown", away);   // a popover has no scrim: it sits inside the glass sidebar, which would clip a fixed one
    return () => { document.removeEventListener("keydown", key); document.removeEventListener("mousedown", away); };
  }, [onClose, mobile]);

  const signOut = async () => { try { await postJSON("/auth/logout"); } finally { location.reload(); } };
  const body = (
    <>
      {mobile && <div className="grab" aria-hidden="true" />}
      <h3 id="appearance-h">Appearance</h3>
      <div role="group" aria-labelledby="appearance-h" style={{ display: "flex", flexDirection: "column" }}>
        {THEMES.map((t) => (
          <button key={t.id} aria-pressed={choice === t.id} onClick={() => onChoice(t.id)}>
            <Icon name={t.scheme === "dark" ? "moon" : "sun"} /> {t.name} {choice === t.id && <span className="sp" style={{ textAlign: "right" }}><Icon name="check" /></span>}
          </button>
        ))}
        <button aria-pressed={choice === "system"} onClick={() => onChoice("system")}>
          <Icon name="device" /> Match my device {choice === "system" && <span className="sp" style={{ textAlign: "right" }}><Icon name="check" /></span>}
        </button>
      </div>
      <hr />
      <Link to="/account" onClick={onClose}><Icon name="user" /> Account</Link>
      <Link to="/plans" onClick={onClose}><Icon name="star" /> Plan</Link>
      {studio && <a href="/legacy#/settings"><Icon name="settings" /> Settings</a>}
      {studio && <a href="/legacy"><Icon name="external" /> Classic view</a>}
      <hr />
      <button onClick={signOut}><Icon name="out" /> Sign out</button>
      {version && <p className="mu" style={{ margin: "8px 12px 0", fontSize: 12 }}>NAVAAN {version}</p>}
    </>
  );
  return mobile ? (
    <>
      <div className="scrim" onClick={onClose} />
      <div ref={ref} className="sheet" role="dialog" aria-modal="true" aria-label="Account menu">{body}</div>
    </>
  ) : (
    // a portal: the sidebar scrolls and clips, so a popover inside it would stretch it sideways
    createPortal(<div ref={ref} className="menu" role="dialog" aria-label="Account menu" style={{ position: "fixed", left: 24, bottom: 76, width: 232 }}>{body}</div>, document.body)
  );
}

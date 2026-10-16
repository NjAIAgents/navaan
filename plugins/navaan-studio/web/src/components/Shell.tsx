import { useCallback, useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { Icon, type IconName } from "./Icon";
import { UserMenu } from "./UserMenu";
import { useMobile } from "./useMobile";
import { useTheme } from "../theme/useTheme";
import { getJSON } from "../lib/api";

type Item = { to: string; label: string; icon: IconName; end?: boolean };
export const NAV: Item[] = [
  { to: "/", label: "Home", icon: "home", end: true },
  { to: "/studio", label: "Studio", icon: "studio" },
  { to: "/library", label: "Library", icon: "library" },
  { to: "/albums", label: "Albums", icon: "albums" },
];
export const STUDIO_SUB: { to: string; label: string; soon?: boolean }[] = [
  { to: "/studio/songs", label: "Songs" },
  { to: "/studio/inspiration", label: "Inspiration" },
  { to: "/studio/podcasts", label: "Podcasts", soon: true },
  { to: "/studio/approvals", label: "Approvals" },
  { to: "/studio/schedule", label: "Schedule" },
  { to: "/studio/analytics", label: "Analytics" },
];

export function titleFor(path: string): string {
  const sub = STUDIO_SUB.find((s) => path.startsWith(s.to));
  if (sub) return sub.label;
  return NAV.find((n) => (n.end ? path === n.to : path.startsWith(n.to)))?.label ?? "NAVAAN";
}

export function Shell() {
  const { pathname } = useLocation();
  const mobile = useMobile();
  const { choice, setChoice } = useTheme();
  const [open, setOpen] = useState(false);
  const [version, setVersion] = useState<string | undefined>();
  const [who, setWho] = useState("Account");
  useEffect(() => { getJSON<{ user?: unknown }>("/api/me").then((m) => { if (typeof m?.user === "string" && m.user) setWho(m.user); }).catch(() => undefined); }, []);
  useEffect(() => { getJSON<{ version?: unknown }>("/auth/state").then((s) => setVersion(typeof s?.version === "string" && s.version ? s.version : undefined)).catch(() => setVersion(undefined)); }, []);
  const close = useCallback(() => setOpen(false), []);
  const title = titleFor(pathname);
  useEffect(() => { document.title = title === "Home" ? "NAVAAN" : `${title} · NAVAAN`; close(); }, [title, close]);
  const inStudio = pathname.startsWith("/studio");

  return (
    <div className="app">
      <a className="sr" href="#main">Skip to content</a>
      <aside className="side" aria-label="Sidebar">
        <NavLink to="/" className="brand"><span className="mark" aria-hidden="true" /> <span className="disp" style={{ letterSpacing: ".14em" }}>NAVAAN</span></NavLink>
        <nav aria-label="Main" style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {NAV.map((n) => (
            <div key={n.to}>
              <NavLink to={n.to} end={n.end} className="nv"><Icon name={n.icon} /> {n.label}</NavLink>
              {n.to === "/studio" && inStudio && (
                <div className="subnv">
                  {STUDIO_SUB.map((s) => (
                    <NavLink key={s.to} to={s.to} className={s.soon ? "soon" : undefined}>{s.label}{s.soon && <span className="chip" style={{ marginLeft: "auto" }}>Soon</span>}</NavLink>
                  ))}
                </div>
              )}
            </div>
          ))}
        </nav>
        <div className="me" style={{ position: "relative" }}>
          <button className="who" onClick={() => setOpen(true)} aria-haspopup="dialog" aria-expanded={open} aria-label={`Account menu, ${who}`}>
            <span className="av" aria-hidden="true">{who.slice(0, 1).toUpperCase()}</span><span>{who}</span><span className="sp" /><Icon name="chevron" />
          </button>
          {open && !mobile && <UserMenu choice={choice} onChoice={setChoice} onClose={close} mobile={false} version={version} />}
        </div>
      </aside>
      <div className="main">
        <header className="top">
          <button className="search" disabled aria-label="Search (coming with the catalog)"><Icon name="search" /> Search songs, albums, lyrics</button>
          <span className="sp" />
          <a className="btn sm g" href="/legacy"><Icon name="external" /> Classic view</a>
        </header>
        <div className="mhead">
          <span className="mark" aria-hidden="true" />
          <h1 className="disp">{title}</h1>
          <span className="sp" />
          <button className="btn g sq" onClick={() => setOpen(true)} aria-label={`Account menu, ${who}`} aria-haspopup="dialog"><span className="av" aria-hidden="true">{who.slice(0, 1).toUpperCase()}</span></button>
        </div>
        <main id="main" className="page" tabIndex={-1}><Outlet /></main>
      </div>
      <nav className="tabbar" aria-label="Main">
        {NAV.map((n) => <NavLink key={n.to} to={n.to} end={n.end}><Icon name={n.icon} />{n.label}</NavLink>)}
      </nav>
      {open && mobile && <UserMenu choice={choice} onChoice={setChoice} onClose={close} mobile version={version} />}
    </div>
  );
}

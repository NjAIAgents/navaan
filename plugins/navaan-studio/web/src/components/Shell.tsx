import { Alerts } from "./Alerts";
import { ErrorBoundary } from "./ErrorBoundary";
import { Suspense, useCallback, useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Icon, type IconName } from "./Icon";
import { UserMenu } from "./UserMenu";
import { useMobile } from "./useMobile";
import { useTheme } from "../theme/useTheme";
import { getJSON } from "../lib/api";
import { MeProvider, useMe } from "../lib/me";
import { PlayerProvider, usePlayer, usePosition } from "../lib/player";
import { mmss } from "../lib/lyrics";
import { Cover } from "./Cover";
import { Transport } from "./Transport";
import { PlayMode } from "./PlayMode";
import { Equaliser } from "./Equaliser";

type Item = { to: string; label: string; icon: IconName; end?: boolean };
const LISTENER_HIDES = new Set(["/studio", "/albums"]);   // the studio side is not shown to a person without studio access (the server refuses it anyway)
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
  { to: "/studio/cloud", label: "Cloud" },
];

export function titleFor(path: string): string {
  const sub = STUDIO_SUB.find((s) => path.startsWith(s.to));
  if (sub) return sub.label;
  return NAV.find((n) => (n.end ? path === n.to : path.startsWith(n.to)))?.label ?? "NAVAAN";
}

function NowPlaying() {
  const p = usePlayer(); const { position, duration } = usePosition();
  if (!p.slug && !p.error) return null;
  return (
    <div className="np card" role="region" aria-label="Now playing">
      {p.slug ? <>
        <button className="np-open" onClick={() => p.setExpanded(true)} aria-label="Open play mode">
          <Cover slug={p.slug} title={p.title} size={44} />
          <span className="tx"><b>{p.title || p.slug}</b>{p.playing ? <Equaliser /> : <span className="eq off" aria-hidden="true"><i /><i /><i /><i /></span>}</span>
        </button>
        <Transport />
        <label className="sr" htmlFor="np-seek">Seek</label>
        <input id="np-seek" className="np-seek" type="range" min={0} max={Math.max(1, Math.floor(duration))} step={1} value={Math.min(Math.floor(position), Math.max(1, Math.floor(duration)))} aria-valuetext={`${mmss(position)} of ${mmss(duration)}`} onChange={(e) => p.seek(Number(e.target.value))} />
      </> : <span role="alert" className="tx">{p.error}</span>}
    </div>
  );
}

export function Shell() { return <MeProvider><PlayerProvider><ShellFrame /></PlayerProvider></MeProvider>; }

function ShellFrame() {
  const { pathname } = useLocation();
  const nav = useNavigate();
  const mobile = useMobile();
  const { choice, setChoice } = useTheme();
  const [open, setOpen] = useState(false);
  const [version, setVersion] = useState<string | undefined>();
  const { user: who, studio } = useMe();
  useEffect(() => { getJSON<{ version?: unknown }>("/auth/state").then((s) => setVersion(typeof s?.version === "string" && s.version ? s.version : undefined)).catch(() => setVersion(undefined)); }, []);
  const close = useCallback(() => setOpen(false), []);
  const title = titleFor(pathname);
  useEffect(() => { document.title = title === "Home" ? "NAVAAN" : `${title} · NAVAAN`; close(); }, [title, close]);
  const inStudio = pathname.startsWith("/studio");
  const nav2 = NAV.filter((n) => studio || !LISTENER_HIDES.has(n.to));

  return (
    <div className="app">
      <a className="sr" href="#main">Skip to content</a>
      <aside className="side" aria-label="Sidebar">
        <NavLink to="/" className="brand"><span className="mark" aria-hidden="true" /> <span className="disp" style={{ letterSpacing: ".14em" }}>NAVAAN</span></NavLink>
        <nav aria-label="Main" style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {nav2.map((n) => (
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
            <span className="av" data-i={who.slice(0, 1).toUpperCase()} aria-hidden="true" /><span>{who}</span><span className="sp" /><Icon name="chevron" />
          </button>
          {open && !mobile && <UserMenu choice={choice} onChoice={setChoice} onClose={close} mobile={false} version={version} />}
        </div>
      </aside>
      <div className="main">
        <header className="top">
          <form className="search" role="search" onSubmit={(e) => { e.preventDefault(); const q = new FormData(e.currentTarget).get("q"); if (typeof q === "string" && q.trim()) nav(`/search?q=${encodeURIComponent(q.trim())}`); }}>
            <Icon name="search" /><input name="q" type="search" aria-label="Search songs, albums, lyrics" placeholder="Search songs, albums, lyrics" autoComplete="off" />
          </form>
          <span className="sp" />
          {studio && <a className="btn sm g" href="/legacy"><Icon name="external" /> Classic view</a>}
        </header>
        <div className="mhead">
          <span className="mark" aria-hidden="true" />
          <h1 className="disp">{title}</h1>
          <span className="sp" />
          <Link className="btn g sq" to="/search" aria-label="Search"><Icon name="search" /></Link>
          <button className="btn g sq" onClick={() => setOpen(true)} aria-label={`Account menu, ${who}`} aria-haspopup="dialog"><span className="av" data-i={who.slice(0, 1).toUpperCase()} aria-hidden="true" /></button>
        </div>
        <main id="main" key={pathname} className="page" tabIndex={-1}>{studio && <Alerts />}<ErrorBoundary><Suspense fallback={<p className="mu" role="status">Loading…</p>}><Outlet /></Suspense></ErrorBoundary></main>
        <NowPlaying />
        <PlayMode />
      </div>
      <nav className="tabbar" aria-label="Main">
        {nav2.map((n) => <NavLink key={n.to} to={n.to} end={n.end}><Icon name={n.icon} />{n.label}</NavLink>)}
      </nav>
      {open && mobile && <UserMenu choice={choice} onChoice={setChoice} onClose={close} mobile version={version} />}
    </div>
  );
}

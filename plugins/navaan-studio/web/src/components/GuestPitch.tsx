import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Loading } from "./Loading";
import { useMe } from "../lib/me";

export const PITCH = "Accounts are coming soon. Create your own playlists and save songs then.";

// A page that needs an account (or the studio) shows this to someone who is not signed in. The wording is the invitation; nothing about the visitor is stored.
export function MembersOnly({ children, studio = false }: { children: ReactNode; studio?: boolean }) {
  const me = useMe();
  if (!me.ready) return <Loading />;
  if (!me.guest) return <>{children}</>;
  return (
    <div className="card stack" style={{ maxWidth: 560 }}>
      <h2>{studio ? "The studio is for the owner" : "Want your own playlists?"}</h2>
      <p>{studio ? "Sign in on the studio address to manage songs, schedules and settings." : PITCH}</p>
      <div className="row">
        {studio && me.studioUrl && <a className="btn p" href={`${me.studioUrl}/app/`}>Studio sign in</a>}
        <Link className="btn" to="/">Browse songs</Link>
      </div>
    </div>
  );
}

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
      <h2>{studio ? "This page is not available here" : "Want your own playlists?"}</h2>
      {!studio && <p>{PITCH}</p>}
      <div className="row">
        {!studio && <Link className="btn p" to="/join">Create account</Link>}
        <Link className="btn" to="/">Browse songs</Link>
      </div>
    </div>
  );
}

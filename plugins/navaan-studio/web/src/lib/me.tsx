import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { getJSON } from "./api";

type Me = { user: string; permissions: string[]; ready: boolean; studio: boolean; guest: boolean; studioUrl?: string; publicUrl?: string };
const Ctx = createContext<Me>({ user: "Account", permissions: [], ready: false, studio: false, guest: false });
export const useMe = () => useContext(Ctx);

// Who is signed in and what they may do (GET /api/me). The shell and the home screen choose the studio or the listener side from it; the server enforces the same permissions on every route.
export function MeProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me>({ user: "Account", permissions: [], ready: false, studio: false, guest: false });
  useEffect(() => {
    getJSON<{ user?: unknown; permissions?: unknown; guest?: unknown; studio_url?: unknown; public_url?: unknown }>("/api/me").then((m) => {
      const permissions = Array.isArray(m?.permissions) ? m.permissions.filter((x): x is string => typeof x === "string") : [];
      const guest = m?.guest === true;
      setMe({ user: guest ? "Visitor" : typeof m?.user === "string" && m.user ? m.user : "Account", permissions, ready: true, studio: permissions.includes("studio.access"), guest, studioUrl: typeof m?.studio_url === "string" ? m.studio_url : undefined, publicUrl: typeof m?.public_url === "string" ? m.public_url : undefined });
    }).catch(() => setMe((x) => ({ ...x, ready: true })));
  }, []);
  return <Ctx.Provider value={me}>{children}</Ctx.Provider>;
}

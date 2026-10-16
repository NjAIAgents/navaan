import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { getJSON } from "./api";

type Me = { user: string; permissions: string[]; ready: boolean; studio: boolean };
const Ctx = createContext<Me>({ user: "Account", permissions: [], ready: false, studio: false });
export const useMe = () => useContext(Ctx);

// Who is signed in and what they may do (GET /api/me). The shell and the home screen choose the studio or the listener side from it; the server enforces the same permissions on every route.
export function MeProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me>({ user: "Account", permissions: [], ready: false, studio: false });
  useEffect(() => {
    getJSON<{ user?: unknown; permissions?: unknown }>("/api/me").then((m) => {
      const permissions = Array.isArray(m?.permissions) ? m.permissions.filter((x): x is string => typeof x === "string") : [];
      setMe({ user: typeof m?.user === "string" && m.user ? m.user : "Account", permissions, ready: true, studio: permissions.includes("studio.access") });
    }).catch(() => setMe((x) => ({ ...x, ready: true })));
  }, []);
  return <Ctx.Provider value={me}>{children}</Ctx.Provider>;
}

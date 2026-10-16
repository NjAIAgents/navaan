// The portal is the API: same origin, session cookie, and a per-process token on every POST (the portal's CSRF defence).
export const token = (): string => document.querySelector<HTMLMetaElement>('meta[name="navaan-token"]')?.content ?? "";

export class ApiError extends Error {
  constructor(public status: number, message: string, public requestId?: string) { super(message); }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, { credentials: "same-origin", ...init });
  const requestId = r.headers.get("X-Request-Id") ?? undefined;
  if (r.status === 401) { location.reload(); throw new ApiError(401, "signed out", requestId); }   // the portal shows its sign-in page
  let body: unknown = null;
  try { body = await r.json(); } catch { /* not JSON: an nginx error page, say */ }
  if (!r.ok) throw new ApiError(r.status, (body as { error?: string } | null)?.error ?? `Request failed (${r.status})`, requestId);
  return body as T;
}

export const getJSON = <T,>(path: string) => call<T>(path);
export const postJSON = <T,>(path: string, body: unknown = {}) =>
  call<T>(path, { method: "POST", headers: { "Content-Type": "application/json", "X-Navaan-Token": token() }, body: JSON.stringify(body) });

export type SongRow = {
  slug: string; type: string; title: string; state: string | null; status: "approval" | "done" | "production";
  album: string; steps_done: number; steps_total: number; public: boolean; published: boolean; scheduled: string;
  next: { type: string; step?: string; gate?: string; label?: string };
};

export type Step = {
  id: string; label: string; kind: string; done: boolean; redo: boolean; restart: boolean; spends: boolean;
  status: "done" | "ready" | "blocked" | "waiting for approval"; needs_gate: string | null; scheduled_for: string | null;
};
export type SongDetail = {
  slug: string; steps: Step[]; next: SongRow["next"]; text: Record<string, string>;
  meta: { state?: string; album?: string; history?: string[] };
  approvals: Record<string, { at: string; via: string }>;
  job: { running: boolean; queued: boolean; rc: number | null }; status_text: string;
  failure: { step: string; error: string; ref: string } | null;
  question: { text?: string } | null; needs_you: string;
};

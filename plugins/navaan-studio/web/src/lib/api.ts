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
  meta: { type?: string; state?: string; album?: string; history?: string[] };
  approvals: Record<string, { at: string; via: string }>;
  job: { running: boolean; queued: boolean; rc: number | null }; status_text: string;
  failure: { step: string; error: string; ref: string } | null;
  question: { text?: string } | null; needs_you: string;
};

export type ScheduleEntry = { slug: string; title: string; type: string; platform: string; at: string; state: "scheduled" | "done" | "missed" | "blocked"; reason: string };

// Analytics (NAV-15): the same payloads the classic Analytics page reads.
export type Rec = {
  rec_id: string; title: string; why: string; action: string; expected_effect: string; priority: number; category: string; confidence: string; status: "open" | "done" | "dismissed";
  dismissed_reason: string | null; account: string; evidence: { title: string; severity: string }[];
};
export type Overview = {
  empty?: boolean; reason?: string; error?: string; account: string; days: number; accounts: { label: string }[];
  kpis: Record<string, number | null>; series: Record<string, [string, number][]>;
  posts?: { media_id: string; title: string; slug: string; posted_at: string; permalink: string; views: number; reach: number; saved: number; shares: number; engagement_rate: number | null }[];
  videos?: { video_id: string; title: string; kind: string; published_at: string; url: string; views: number; likes: number; comments: number; avg_view_s: number | null }[];
  reco: { ready: boolean; open: Rec[]; done: Rec[]; dismissed: Rec[]; analyzed_at?: string };
  runs: { started_at: string; status: string; errors: number; first_error: string }[];
  collect: { running: boolean };
};
export type Reply = { comment_id: string; username: string; text: string; posted_at: string; post_id: string; post: string; account: string; link: string; reply: { draft: string | null; status: string; error: string | null } | null };

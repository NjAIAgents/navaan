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
  art?: { colour: string | null } | null;
};

export type Step = {
  id: string; label: string; kind: string; done: boolean; redo: boolean; restart: boolean; spends: boolean;
  status: "done" | "ready" | "blocked" | "waiting for approval"; needs_gate: string | null; scheduled_for: string | null;
};
export type Question = { id: string; text: string; allow_text: boolean; options: { id: string; label: string; text: boolean }[] };
export type SongDetail = {
  slug: string; steps: Step[]; next: SongRow["next"]; text: Record<string, string>;
  meta: { type?: string; state?: string; album?: string; history?: string[]; source?: string; suno?: { auto_failed?: string }; cleanup?: unknown };
  files: Record<string, number>;
  approvals: Record<string, { at: string; via: string }>;
  job: { running: boolean; queued: boolean; rc: number | null }; status_text: string;
  failure: { step: string; error: string; ref: string } | null;
  question: Question | null; needs_you: string;
  cameras: string[]; cloud: boolean; images: string[];
  visuals?: { mode?: string; layout?: string; camera?: string; scene?: string }; openai_pictures?: boolean;
  prompt_pack?: { aspect?: string; style_line: string; prompts: { n: number; section: string; prompt: string }[] } | null;
  try?: { running?: boolean; error?: string; files?: string[]; v?: number }; vertical?: { running?: boolean; error?: string; done?: number[] };
  visuals_problems?: string[];
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

export type Hit = { kind: "track" | "album" | "playlist" | "short"; id: string; slug: string | null; title: string; title_roman: string; score: number };

// Library and plans (NAV-7)
export type PlaylistRow = { id: string; name: string; description: string; visibility: "private" | "unlisted" | "public"; tracks: number; updated_at: string };
export type PlaylistDetail = { id: string; name: string; description: string; visibility: PlaylistRow["visibility"]; mine?: boolean; tracks: { slug: string; title: string; position: string }[] };
export type LibraryData = { tracks: { slug: string; title: string }[]; albums: { slug: string; title: string }[]; following: boolean };
export type PlansData = {
  plans: { key: string; name: string; price_minor: number | null; currency: string | null; interval: string | null; buyable: boolean; entitlements: { feature: string; enabled: boolean; limit: number | null }[] }[];
  mine: { plan: { key: string; name: string; status: string }; entitlements: Record<string, { enabled: boolean; limit: number | null }>; unlimited: boolean; usage: { playlists: number } };
};

// Listener catalog (NAV-18)
export type TrackRow = { slug: string; title: string; language: string; genre: string; albums: { slug: string; title: string }[]; licence: string; art: { colour: string | null } | null };
export type TrackView = TrackRow & { lyrics: string; timed: boolean; timed_lines: [number, string][] | null };
export type Filters = { albums: { slug: string; title: string }[]; languages: string[]; genres: string[] };
export type AlbumTrack = { slug: string; title: string; position: number; status: string; licence: string; art: { colour: string | null } | null };
export type AlbumRow = { id: string; slug: string; title: string; kind: "album" | "ep" | "single"; status: "draft" | "scheduled" | "published"; release_date: string | null; description: string; tracks: AlbumTrack[] };

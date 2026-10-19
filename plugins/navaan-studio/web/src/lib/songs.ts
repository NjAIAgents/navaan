import type { SongRow } from "./api";
import { gateTitle, stepLabel } from "./gates";

export const classic = (slug: string) => `/legacy#/song/${slug}`;
export const errText = (e: unknown) => { const x = e as Error & { requestId?: string }; return `${x.message}${x.requestId ? ` (ref ${x.requestId})` : ""}`; };

/** The one-line "what happens next" for a song. */
export function nextAction(s: Pick<SongRow, "status" | "next" | "published">): string {
  const n = s.next;
  if (n?.type === "gate" && n.gate) return `Waiting for you: ${gateTitle(n.gate)}`;
  if (s.status === "done") return s.published ? "Published" : "Done";
  if (n?.step) return `Next: ${stepLabel(n.step)}`;
  return "In production";
}

/** Where an item opens: songs and inspiration have screens in the new app, anything else opens in the classic view. */
// The short-form channels: the inspiration pipeline, posted to different accounts. The Aha-lorithm (NAV-67) posts YouTube Shorts only.
export const SHORT_TYPES = ["inspiration", "aha", "reel"];   // a reel is made from your own footage and posts to Instagram only
export const isShort = (t?: string) => SHORT_TYPES.includes(t ?? "");
export const listPath = (type?: string) => (type === "inspiration" ? "/studio/inspiration" : type === "aha" ? "/studio/aha" : type === "reel" ? "/studio/reels" : "/studio/songs");
export const itemPath = (type: string, slug: string) => (type === "music" || isShort(type) ? `${listPath(type)}/${slug}` : null);

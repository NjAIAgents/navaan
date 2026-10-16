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

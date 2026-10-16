const p2 = (n: number) => String(n).padStart(2, "0");
/** An ISO time as the value of a datetime-local input (the viewer's own clock). */
export const toLocalIn = (iso: string): string => { const d = new Date(iso); return Number.isNaN(d.getTime()) ? "" : `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())}T${p2(d.getHours())}:${p2(d.getMinutes())}`; };
/** A datetime-local value back to an ISO time in UTC. */
export const toIso = (local: string): string => new Date(local).toISOString();
export const plusMin = (local: string, m: number): string => toLocalIn(new Date(new Date(local).getTime() + m * 60000).toISOString());
export const fmtL = (iso: string): string => new Date(iso).toLocaleString([], { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

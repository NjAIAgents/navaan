// A length of time in words a person reads at a glance: "45 s", "2 min 31 s", "1 h 4 min".
export function dur(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s} s`;
  const m = Math.floor(s / 60), r = s % 60;
  if (m < 60) return r ? `${m} min ${r} s` : `${m} min`;
  return `${Math.floor(m / 60)} h ${m % 60} min`;
}
// How long it usually takes, as a rough phrase ("about a minute", "about 9 min").
export const usually = (seconds: number) => (seconds < 90 ? "about a minute" : `about ${Math.round(seconds / 60)} min`);

// Timed lyrics: [[seconds, line], ...] in order. The current line is the last one that has started.
export type TimedLine = [number, string];

export function activeIndex(lines: TimedLine[], seconds: number): number {
  let lo = 0, hi = lines.length - 1, found = -1;
  while (lo <= hi) { const mid = (lo + hi) >> 1; if (lines[mid][0] <= seconds) { found = mid; lo = mid + 1; } else hi = mid - 1; }
  return found;
}

export const mmss = (s: number) => { const t = Math.max(0, Math.floor(s || 0)); return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`; };

/** Lyrics text to timed lines when nobody measured the timing: the lines are spread over the song by length, after a short intro and before a short outro. [Verse] style labels are skipped. */
export function estimateLines(plain: string, duration: number): TimedLine[] | null {
  const lines = plain.split("\n").map((l) => l.trim()).filter((l) => l && !/^\[.*\]$/.test(l));
  if (!lines.length || !(duration > 0)) return null;
  const from = Math.min(10, duration * 0.05), to = duration - Math.min(8, duration * 0.04);
  const w = lines.map((l) => Math.max(3, l.replace(/\s/g, "").length)); const total = w.reduce((a, b) => a + b, 0);
  let at = from; return lines.map((l, i) => { const t = at; at += ((to - from) * w[i]) / total; return [t, l] as TimedLine; });
}

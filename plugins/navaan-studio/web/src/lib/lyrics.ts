// Timed lyrics: [[seconds, line], ...] in order. The current line is the last one that has started.
export type TimedLine = [number, string];

export function activeIndex(lines: TimedLine[], seconds: number): number {
  let lo = 0, hi = lines.length - 1, found = -1;
  while (lo <= hi) { const mid = (lo + hi) >> 1; if (lines[mid][0] <= seconds) { found = mid; lo = mid + 1; } else hi = mid - 1; }
  return found;
}

export const mmss = (s: number) => { const t = Math.max(0, Math.floor(s || 0)); return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`; };

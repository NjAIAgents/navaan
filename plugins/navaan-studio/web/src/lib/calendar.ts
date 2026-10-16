// Month grid and day grouping for the Schedule screen. Local time, weeks start on Monday.
import type { ScheduleEntry } from "./api";

export type Cell = { date: Date; inMonth: boolean; key: string };
const pad = (n: number) => String(n).padStart(2, "0");
export const dayKey = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

/** The weeks that cover a month (month is 0 to 11): days of the neighbouring months fill the first and last row, so every row has 7 columns and the 1st sits under the right weekday. */
export function monthGrid(year: number, month: number): Cell[][] {
  const offset = (new Date(year, month, 1).getDay() + 6) % 7;   // Monday is column 0
  const last = new Date(year, month + 1, 0).getTime();
  const weeks: Cell[][] = [];
  for (let w = 0; ; w++) {
    const row = Array.from({ length: 7 }, (_, i) => { const date = new Date(year, month, 1 - offset + w * 7 + i); return { date, inMonth: date.getMonth() === month, key: dayKey(date) }; });
    weeks.push(row);
    if (row[6].date.getTime() >= last) return weeks;
  }
}

/** Entries by local day, each day in time order. */
export function byDay(entries: ScheduleEntry[]): Map<string, ScheduleEntry[]> {
  const m = new Map<string, ScheduleEntry[]>();
  for (const e of [...entries].sort((a, b) => Date.parse(a.at) - Date.parse(b.at))) { const k = dayKey(new Date(e.at)); m.set(k, [...(m.get(k) ?? []), e]); }
  return m;
}

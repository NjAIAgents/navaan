// Themes are data: each has a stylesheet in src/styles/themes/ that defines the same variables. The page carries the active one in <html data-theme>.
// "system" follows the device. The choice is a per-device convenience kept in localStorage; index.html applies it before first paint.
export type ThemeId = "midnight-cinema" | "ivory-gold";
export type Choice = ThemeId | "system";

export const THEMES: { id: ThemeId; name: string; scheme: "dark" | "light" }[] = [
  { id: "midnight-cinema", name: "Midnight Cinema", scheme: "dark" },
  { id: "ivory-gold", name: "Ivory & Gold", scheme: "light" },
];

export const STORAGE_KEY = "navaan.theme";
const isTheme = (v: unknown): v is ThemeId => THEMES.some((t) => t.id === v);

export function readChoice(storage: Pick<Storage, "getItem"> | null = safeStorage()): Choice {
  try {
    const v = storage?.getItem(STORAGE_KEY);
    return isTheme(v) ? v : "system";
  } catch {
    return "system";   // storage can throw (private window, blocked site data): fall back to the device
  }
}

export function resolve(choice: Choice, prefersLight: boolean): ThemeId {
  if (choice !== "system") return choice;
  return prefersLight ? "ivory-gold" : "midnight-cinema";
}

export function systemPrefersLight(win: Window = window): boolean {
  return !!win.matchMedia?.("(prefers-color-scheme: light)").matches;
}

export function applyChoice(choice: Choice, doc: Document = document, win: Window = window): ThemeId {
  const id = resolve(choice, systemPrefersLight(win));
  doc.documentElement.setAttribute("data-theme", id);
  return id;
}

export function saveChoice(choice: Choice, storage: Pick<Storage, "setItem" | "removeItem"> | null = safeStorage()): void {
  try {
    if (choice === "system") storage?.removeItem(STORAGE_KEY);
    else storage?.setItem(STORAGE_KEY, choice);
  } catch {
    // nothing to keep the choice in; it still applies for this visit
  }
}

function safeStorage(): Storage | null {
  try { return window.localStorage; } catch { return null; }
}

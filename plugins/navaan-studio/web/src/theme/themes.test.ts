import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { applyChoice, readChoice, resolve, saveChoice, STORAGE_KEY, THEMES } from "./themes";
import { contrast, over, parseColor, readTokens } from "./contrast";

// vitest runs from the web folder; paths are built from it (import.meta.url is not a file URL under jsdom)
const css = (id: string) => readFileSync(join(process.cwd(), "src", "styles", "themes", `${id}.css`), "utf8");
const REQUIRED = ["--bg", "--s1", "--s2", "--s3", "--ln", "--tx", "--mu", "--dim", "--ac", "--vi", "--g1", "--g2", "--on-action", "--ok", "--wn", "--bad", "--bar", "--sheet", "--blur",
  "--shadow", "--shadow-sm", "--hi", "--scrim", "--on-media", "--media-fill", "--cov1", "--cov2", "--cov3", "--cov4", "--glass-fill", "--gloss", "--rim", "--orbs", "--field"];

describe.each(THEMES)("theme $id", (t) => {
  const tok = readTokens(css(t.id));
  it("defines every token a component can read", () => { for (const k of REQUIRED) expect(tok, k).toHaveProperty(k); });
  it("declares its selector and colour scheme", () => {
    expect(css(t.id)).toContain(`[data-theme="${t.id}"]`);
    expect(css(t.id)).toContain(`color-scheme: ${t.scheme}`);
  });
  const bg = parseColor(tok["--bg"]);
  const onGround = (name: string) => contrast(over(parseColor(tok[name]), bg), bg);
  it("keeps text at 4.5:1 or more on the ground", () => { for (const k of ["--tx", "--mu", "--ac", "--ok", "--wn", "--bad"]) expect(contrast(parseColor(tok[k]), bg), k).toBeGreaterThanOrEqual(4.5); });
  it("keeps tertiary text legible (3:1 or more, for large or non-essential text only)", () => { expect(onGround("--dim")).toBeGreaterThanOrEqual(3); });
  it("puts readable text on the action gradient", () => {
    for (const g of ["--g1", "--g2"]) expect(contrast(parseColor(tok["--on-action"]), parseColor(tok[g])), g).toBeGreaterThanOrEqual(4.5);
  });
  it("keeps text readable on the raised glass surfaces too", () => {
    for (const s of ["--s2", "--s3"]) for (const k of ["--tx", "--mu"]) expect(contrast(parseColor(tok[k]), over(parseColor(tok[s]), bg)), `${k} on ${s}`).toBeGreaterThanOrEqual(4.5);
  });
});

describe("choosing a theme", () => {
  it("resolves system by the device", () => { expect(resolve("system", false)).toBe("midnight-cinema"); expect(resolve("system", true)).toBe("ivory-gold"); expect(resolve("ivory-gold", false)).toBe("ivory-gold"); });
  it("opens dark until someone chooses, and reads only known ids", () => {
    expect(readChoice({ getItem: () => "ivory-gold" })).toBe("ivory-gold"); expect(readChoice({ getItem: () => "system" })).toBe("system");   // "match my device" is a choice
    expect(readChoice({ getItem: () => null })).toBe("midnight-cinema"); expect(readChoice({ getItem: () => "neon" })).toBe("midnight-cinema");
    expect(readChoice({ getItem: () => { throw new Error("blocked"); } })).toBe("midnight-cinema"); expect(readChoice(null)).toBe("midnight-cinema");
  });
  it("saves every choice, system included, and survives a blocked store", () => {
    const m = new Map<string, string>(); const st = { setItem: (k: string, v: string) => void m.set(k, v) };
    saveChoice("ivory-gold", st); expect(m.get(STORAGE_KEY)).toBe("ivory-gold");
    saveChoice("system", st); expect(m.get(STORAGE_KEY)).toBe("system");
    expect(() => saveChoice("ivory-gold", { setItem() { throw new Error("blocked"); } })).not.toThrow();
  });
  it("sets data-theme on the document", () => {
    const win = { matchMedia: () => ({ matches: true }) } as unknown as Window;
    expect(applyChoice("system", document, win)).toBe("ivory-gold"); expect(document.documentElement.getAttribute("data-theme")).toBe("ivory-gold");
    expect(applyChoice("midnight-cinema", document, win)).toBe("midnight-cinema");
  });
  it("is the same list the page applies before first paint", () => {
    const html = readFileSync(join(process.cwd(), "index.html"), "utf8");
    for (const t of THEMES) expect(html).toContain(`"${t.id}"`);
    expect(html).toContain(STORAGE_KEY);
  });
});

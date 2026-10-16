// Fails when a colour literal appears in src outside src/styles/themes/ (constitution XIV: themes are data, components read variables).
// Looks for #hex, rgb()/rgba(), hsl()/hsla(), oklch()/lab() and named CSS colours used as values in css and tsx/ts files.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";

const ROOT = new URL("../src", import.meta.url).pathname;
const SKIP = join(ROOT, "styles", "themes") + sep;
const FUNC = /\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch)\s*\(/i;
const HEX = /#[0-9a-f]{3,8}\b/i;
const NAMED = /:\s*(?:white|black|red|green|blue|gold|navy|gray|grey|silver|orange|purple|pink|yellow|brown)\b/i;

function walk(dir) {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    return statSync(p).isDirectory() ? walk(p) : [p];
  });
}

const bad = [];
for (const f of walk(ROOT)) {
  if (f.startsWith(SKIP) || !/\.(css|tsx?|html)$/.test(f) || /\.test\.tsx?$/.test(f)) continue;
  readFileSync(f, "utf8").split("\n").forEach((line, i) => {
    const code = line.replace(/\/\*.*?\*\//g, "").replace(/\/\/.*$/, "");
    if (HEX.test(code.replace(/&#\d+;/g, "").replace(/href="#[^"]*"/g, "")) || FUNC.test(code) || NAMED.test(code)) bad.push(`${relative(ROOT, f)}:${i + 1}: ${line.trim().slice(0, 100)}`);
  });
}
if (bad.length) {
  console.error("Colour literals outside src/styles/themes/ (use a variable from the theme files):\n  " + bad.join("\n  "));
  process.exit(1);
}
console.log("check-colors: ok, no colour literals outside the theme files");

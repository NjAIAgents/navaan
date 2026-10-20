// A small markdown reader for the finished blog drafts (NAV-134): HTML to show and to put on the clipboard as rich text, and plain text for sites that take no formatting.
// Every piece of text is escaped before any tag is added, and only http(s) links are kept, so a draft can never inject markup.

const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

// the claim markers the fact check reads ("[c3]") never belong on a published page
export const stripMarkers = (md: string) => md.replace(/[ \t]?\[c\d+\]/g, "");

export type FrontMatter = { title: string; description: string; tags: string[]; body: string };
export function frontMatter(md: string): FrontMatter {
  const m = md.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?/);
  if (!m) return { title: "", description: "", tags: [], body: md };
  const get = (k: string) => (m[1].match(new RegExp(`^${k}:\\s*(.*)$`, "m"))?.[1] ?? "").trim().replace(/^["']|["']$/g, "");
  return { title: get("title"), description: get("description"), tags: get("tags").split(",").map((t) => t.trim()).filter(Boolean), body: md.slice(m[0].length) };
}

// inline: `code`, **bold**, *italic* / _italic_, [text](http link); an image keeps only its description
function inline(raw: string): string {
  return raw.split(/(`[^`]+`)/).map((part, i) => {
    if (i % 2) return `<code>${esc(part.slice(1, -1))}</code>`;
    let t = esc(part);
    t = t.replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1");
    t = t.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2">$1</a>').replace(/\[([^\]]+)\]\([^)]*\)/g, "$1");   // a link that is not http(s) keeps its words only
    t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>").replace(/(^|[\s(])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>").replace(/(^|[\s(])_([^_\s][^_]*)_(?=[\s).,;:!?]|$)/g, "$1<em>$2</em>");
    return t;
  }).join("");
}

export function toHtml(md: string): string {
  const lines = md.replace(/\r\n/g, "\n").split("\n"); const out: string[] = []; let i = 0;
  while (i < lines.length) {
    const l = lines[i];
    if (/^```/.test(l)) {
      const code: string[] = []; i++;
      while (i < lines.length && !/^```/.test(lines[i])) code.push(lines[i++]);
      i++; out.push(`<pre><code>${esc(code.join("\n"))}</code></pre>`); continue;
    }
    const h = l.match(/^(#{1,6})\s+(.*)$/);
    if (h) { out.push(`<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`); i++; continue; }
    if (/^(-{3,}|\*{3,})\s*$/.test(l)) { out.push("<hr>"); i++; continue; }
    if (/^>\s?/.test(l)) { const q: string[] = []; while (i < lines.length && /^>\s?/.test(lines[i])) q.push(lines[i++].replace(/^>\s?/, "")); out.push(`<blockquote><p>${inline(q.join(" "))}</p></blockquote>`); continue; }
    const li = l.match(/^(\s*)([-*+]|\d+\.)\s+(.*)$/);
    if (li) {
      const ordered = /\d/.test(li[2]); const items: string[] = [];
      while (i < lines.length) { const m = lines[i].match(/^(\s*)([-*+]|\d+\.)\s+(.*)$/); if (!m || /\d/.test(m[2]) !== ordered) break; items.push(`<li>${inline(m[3])}</li>`); i++; }
      out.push(`<${ordered ? "ol" : "ul"}>${items.join("")}</${ordered ? "ol" : "ul"}>`); continue;
    }
    if (!l.trim()) { i++; continue; }
    const p: string[] = [];
    while (i < lines.length && lines[i].trim() && !/^(```|#{1,6}\s|>\s?|(\s*)([-*+]|\d+\.)\s|-{3,}\s*$)/.test(lines[i])) p.push(lines[i++]);
    out.push(`<p>${inline(p.join(" "))}</p>`);
  }
  return out.join("\n");
}

// plain text for a site with no formatting: headings on their own line, bullets as •, links as "text (url)", code kept as it is
export function toPlain(md: string): string {
  return md.replace(/\r\n/g, "\n").split("\n").map((l) => l
    .replace(/^#{1,6}\s+/, "").replace(/^>\s?/, "").replace(/^(\s*)[-*+]\s+/, "$1• ").replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, "$1 ($2)").replace(/\*\*([^*]+)\*\*/g, "$1").replace(/(^|[\s(])\*([^*\s][^*]*)\*/g, "$1$2").replace(/`([^`]+)`/g, "$1"))
    .filter((l) => !/^```/.test(l)).join("\n").replace(/\n{3,}/g, "\n\n").trim();
}

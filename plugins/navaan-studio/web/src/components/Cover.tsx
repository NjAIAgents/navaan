// A cover tile. Until the catalog has real art (NAV-16, NAV-20) it shows the item's initial on one of four theme gradients chosen from its slug, so a list still has a face.
export function Cover({ slug, title, size = 56 }: { slug: string; title: string; size?: number }) {
  let h = 0;
  for (const ch of slug) h = (h * 31 + ch.charCodeAt(0)) % 997;
  return (
    <span className="cover" data-v={h % 4} style={{ width: size, fontSize: size / 2.4 }} aria-hidden="true">
      <b>{(title || slug).slice(0, 1).toUpperCase()}</b>
    </span>
  );
}

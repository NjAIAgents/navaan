// A line over time without a charting library: the shape is the point, the numbers are in the summary text.
export function Spark({ label, points }: { label: string; points: [string, number][] }) {
  if (points.length < 2) return <figure className="spark"><figcaption>{label}</figcaption><p className="mu">Not enough days yet.</p></figure>;
  const vs = points.map((p) => p[1]); const lo = Math.min(...vs); const hi = Math.max(...vs); const span = hi - lo || 1;
  const path = points.map(([, v], i) => `${i ? "L" : "M"}${((i / (points.length - 1)) * 300).toFixed(1)} ${(56 - ((v - lo) / span) * 48).toFixed(1)}`).join(" ");
  const first = vs[0], last = vs[vs.length - 1];
  return (
    <figure className="spark">
      <figcaption>{label}<span className="mu"> {first.toLocaleString()} to {last.toLocaleString()}</span></figcaption>
      <svg viewBox="0 0 300 64" role="img" aria-label={`${label}: from ${first.toLocaleString()} on ${points[0][0]} to ${last.toLocaleString()} on ${points[points.length - 1][0]}`} preserveAspectRatio="none"><path d={path} /></svg>
    </figure>
  );
}

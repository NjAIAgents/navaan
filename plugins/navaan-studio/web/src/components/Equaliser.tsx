// Four bars that mark the item that is playing. They move only when motion is allowed (the stylesheet stops every animation under prefers-reduced-motion).
export function Equaliser({ label = "Now playing" }: { label?: string }) {
  return <span className="eq" role="img" aria-label={label}><i /><i /><i /><i /></span>;
}

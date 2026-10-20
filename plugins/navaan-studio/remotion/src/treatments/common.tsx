import React from 'react';
import {Easing, interpolate} from 'remotion';

// Shared by the treatment library (NAV-130): palette, easing and the small pieces every treatment uses.

export const GOLD = '#E2B75A', COOL = '#6EA8FF', GREEN = '#5BD6A0', RED = '#FF6B6B', INK = '#F4F7FF';
export const SANS = `"Inter","Avenir Next","Helvetica Neue","Noto Sans Devanagari","Noto Sans","DejaVu Sans",sans-serif`;
export const SERIF = `"Georgia","Baskerville","Noto Serif Devanagari","Noto Serif","DejaVu Serif",serif`;
export const ease = Easing.bezier(0.22, 1, 0.36, 1);
export const pop = Easing.bezier(0.34, 1.56, 0.64, 1);
export const CLAMP = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
export const shadow = '0 6px 28px rgba(0,0,0,0.65), 0 0 2px rgba(0,0,0,0.5)';

// Each treatment gets its beat's own clock (seconds since the beat began) and its length. Its timings are written for a nominal 6 s beat
// and stretched to the real one, so the same chat or checklist reads right in a 3 s beat and a 6 s one.
export type SceneProps = {data: Record<string, any>; local: number; span: number; t: number; text: string; accent: string; color: string};

export const NOMINAL = 6;
export const clock = (local: number, span: number) => {
  const win = Math.min(8, Math.max(2, span * 0.85)), s = local * NOMINAL / win;
  return {s, ramp: (a: number, b: number, easing: (n: number) => number = ease) => interpolate(s, [a, b], [0, 1], {easing, ...CLAMP})};
};

// *marked* words take the accent colour
export const marked = (text: string, accent: string) => text.split(/(\*[^*]+\*)/).filter(Boolean).map((part, i) =>
  part.startsWith('*') && part.endsWith('*') ? <span key={i} style={{color: accent}}>{part.slice(1, -1)}</span> : <React.Fragment key={i}>{part}</React.Fragment>);
export const plain = (text: string) => text.replace(/\*/g, '');

// Where a number came from, said on screen: its source, or that it is sample data, or that a drawing is only an illustration. A treatment never shows a figure without one.
export const Provenance: React.FC<{data: Record<string, any>; illustration?: boolean; style?: React.CSSProperties}> = ({data, illustration, style}) => {
  const say = data.source ? String(data.source) : data.sample ? 'SAMPLE DATA' : illustration ? 'illustration, not data' : '';
  if (!say) return null;
  const flag = !data.source && data.sample;
  return <div style={{textAlign: 'center', fontFamily: SANS, fontSize: flag ? 34 : 30, fontWeight: flag ? 800 : 500, letterSpacing: flag ? 8 : 5, textTransform: data.source ? 'none' : 'uppercase', color: flag ? RED : 'rgba(255,255,255,0.6)', ...style}}>{say}</div>;
};

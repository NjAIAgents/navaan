import React from 'react';
import {Easing, interpolate} from 'remotion';
import {CLAMP, SERIF, ease, shadow} from './common';

// Caption treatments (NAV-130) for a narrated inspiration: calm, one typeface, one per short. They draw the spoken lines over the picture or scene video
// that `Lyrics` already shows; the picture, the music, the voice and the credit page are not touched. The names are mirrored in scripts/visuals_plan.py.
//   karaoke  one line at a time, the spoken word lights up
//   rise     words rise out of the dark as they are spoken; the glow breathes with the voice (`amp`, one 0 to 1 value per frame, when the plan carries it)
//   hero     the key words (`emph`) grow and glow; a closing line (`closing`) opens up and is underlined by a drawn stroke

export type CaptionCue = {text: string; start: number; end: number; at?: number[]};   // at: when each word starts, measured from the voice; without it the words are spread by length
export type CaptionPlan = {treatment: string; emph?: string[]; closing?: boolean; amp?: number[]};
type CaptionProps = {cues: CaptionCue[]; plan: CaptionPlan; t: number; frame: number; color: string; accent: string};

const bare = (w: string) => w.toLowerCase().replace(/[^\p{L}\p{M}\p{N}]/gu, '');   // marks kept: a Devanagari vowel sign is a mark

// the words of a cue: at the times measured from the voice when the plan carries them (voice_timing.py), else timed across the cue by length
const words = (c: CaptionCue, emph: string[]) => {
  const ws = c.text.split(/\s+/).filter(Boolean), total = ws.reduce((n, w) => n + w.length, 0) || 1, hot = emph.map(bare);
  let acc = 0;
  const measured = c.at && c.at.length === ws.length ? c.at : null;
  return ws.map((w, i) => { const at = measured ? measured[i] : c.start + (acc / total) * (c.end - c.start) * 0.93; acc += w.length; return {w, at, i, hot: hot.includes(bare(w))}; });
};
const box = (top: number): React.CSSProperties => ({position: 'absolute', left: 90, right: 90, top, display: 'flex', flexWrap: 'wrap', justifyContent: 'center', alignItems: 'baseline', gap: '6px 22px', textAlign: 'center'});
const TOP = Math.round(1920 * 0.36);

const Karaoke: React.FC<CaptionProps> = ({cues, plan, t, color, accent}) => (
  <>
    {cues.map((c, li) => {
      const ws = words(c, plan.emph ?? []), later = cues[li + 1], italic = !!plan.closing && li === cues.length - 1;
      const k = interpolate(t, [c.start - 0.2, c.start + 0.5], [0, 1], {easing: ease, ...CLAMP}), out = later ? interpolate(t, [later.start - 0.5, later.start], [1, 0], CLAMP) : 1;
      return (
        <div key={li} style={{...box(TOP), opacity: k * out}}>
          {ws.map((w) => {
            const on = interpolate(t, [w.at, w.at + 0.14], [0, 1], CLAMP), now = t >= w.at && t < (ws[w.i + 1]?.at ?? c.end + 0.15);
            return <span key={w.i} style={{fontFamily: SERIF, fontSize: italic ? 104 : 86, lineHeight: 1.35, letterSpacing: 1, fontStyle: italic ? 'italic' : 'normal', textShadow: shadow, color: italic ? accent : color,
              opacity: 0.32 + 0.68 * on, transform: `scale(${1 + 0.07 * (now ? 1 : 0)})`, textDecoration: now ? `underline ${accent}` : 'none', textDecorationThickness: 5, textUnderlineOffset: 14}}>{w.w}</span>;
          })}
        </div>
      );
    })}
  </>
);

const Rise: React.FC<CaptionProps> = ({cues, plan, t, frame, color, accent}) => {
  const amp = plan.amp?.length ? plan.amp[Math.min(plan.amp.length - 1, frame)] ?? 0 : 0;
  return (
    <>
      {amp > 0 ? <div style={{position: 'absolute', left: 540 - (380 + 300 * amp), top: 760 - (380 + 300 * amp), width: 760 + 600 * amp, height: 760 + 600 * amp, borderRadius: '50%', background: `radial-gradient(circle, ${accent}${Math.round((0.12 + 0.3 * amp) * 255).toString(16).padStart(2, '0')} 0%, transparent 70%)`}} /> : null}
      <div style={{position: 'absolute', inset: 0, transform: `scale(${1 + 0.012 * amp})`}}>
        {cues.map((c, li) => {
          const later = cues[li + 1], italic = !!plan.closing && li === cues.length - 1, dim = later ? interpolate(t, [later.start - 0.1, later.start + 0.7], [1, 0.5], CLAMP) : 1;
          return (
            <div key={li} style={{...box(TOP + Math.min(li, 1) * 250), opacity: dim}}>
              {words(c, plan.emph ?? []).map((w) => {
                const k = interpolate(t, [w.at, w.at + 0.45], [0, 1], {easing: ease, ...CLAMP});
                return <span key={w.i} style={{fontFamily: SERIF, fontSize: italic ? 104 : 86, lineHeight: 1.35, letterSpacing: 1, textShadow: shadow, fontStyle: italic ? 'italic' : 'normal', color: italic ? accent : color, opacity: k, transform: `translateY(${(1 - k) * 34}px)`, filter: `blur(${(1 - k) * 12}px)`}}>{w.w}</span>;
              })}
            </div>
          );
        })}
      </div>
    </>
  );
};

const Hero: React.FC<CaptionProps> = ({cues, plan, t, color, accent}) => (
  <>
    {cues.map((c, li) => {
      const later = cues[li + 1], italic = !!plan.closing && li === cues.length - 1, dim = later ? interpolate(t, [later.start - 0.1, later.start + 0.7], [1, 0.5], CLAMP) : 1;
      const line = interpolate(t, [c.start - 0.2, c.start + 0.5], [0, 1], {easing: ease, ...CLAMP}), underline = interpolate(t, [c.start + 0.5, c.end + 0.7], [0, 1], {easing: Easing.inOut(Easing.cubic), ...CLAMP});
      return (
        <div key={li} style={{...box(Math.round(1920 * 0.3) + li * 360 + (italic ? 40 : 0)), opacity: dim * (italic ? line : 1)}}>
          {words(c, plan.emph ?? []).map((w) => {
            const k = interpolate(t, [w.at, w.at + 0.5], [0, 1], {easing: Easing.bezier(0.34, 1.4, 0.64, 1), ...CLAMP}), big = w.hot ? 1.28 : 1;
            const spacing = italic ? interpolate(t, [c.start, c.end + 0.6], [14, 1], {easing: ease, ...CLAMP}) : 1;
            return <span key={w.i} style={{fontFamily: SERIF, fontSize: (italic ? 112 : 76) * big, lineHeight: 1.25, letterSpacing: spacing, textShadow: w.hot ? `0 0 46px ${accent}77, ${shadow}` : shadow,
              ...(italic ? {fontStyle: 'italic' as const, color: accent} : {color: w.hot ? accent : color, fontWeight: w.hot ? 700 : 400}), opacity: Math.min(1, k * 1.8), transform: `scale(${0.82 + 0.18 * k})`, filter: italic ? `blur(${(1 - Math.min(1, k * 1.4)) * 10}px)` : undefined}}>{w.w}</span>;
          })}
          {italic ? (
            <svg width="640" height="60" viewBox="0 0 640 60" style={{position: 'absolute', left: '50%', marginLeft: -320, top: '100%', marginTop: 4}}>
              <path d="M10 38 C 120 8, 220 52, 330 28 S 540 14, 630 34" stroke={accent} strokeWidth="6" strokeLinecap="round" fill="none" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - underline} style={{filter: `drop-shadow(0 0 12px ${accent}99)`}} />
            </svg>) : null}
        </div>
      );
    })}
  </>
);

export const CAPTIONS: Record<string, React.FC<CaptionProps>> = {karaoke: Karaoke, rise: Rise, hero: Hero};

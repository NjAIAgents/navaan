import React from 'react';
import {AbsoluteFill, interpolate, random, useCurrentFrame, useVideoConfig} from 'remotion';
import {Quote} from './Quote';
import type {QuoteProps} from './Quote';
import {Lyrics} from './Lyrics';
import type {Cue, LyricsProps} from './Lyrics';
import {CAPTIONS} from './treatments/captions';
import type {CaptionPlan} from './treatments/captions';
import {SCENES} from './treatments/scenes';
import {CLAMP, COOL, SANS, ease, marked, shadow} from './treatments/common';

// One short, drawn the way its plan says (NAV-130). The plan is `visuals` (visual_plan.json, written by the planner and approved with the script):
//   beats    an Aha-lorithm beat shown by a scene treatment (a chat, a comparison, a counting number ...) instead of a picture
//   caption  how a narrated inspiration's spoken lines are drawn (karaoke, rise, hero)
// The base composition does everything else exactly as before (pictures, camera, music, voice, end card): `quote` for an Aha-lorithm short, `lyrics` for a narrated inspiration,
// `none` for a plain dark scene (previews and samples). A beat or caption this file does not know is left to the base, so a plan can never leave a hole in the video.

export type VisualBeat = {line: number; treatment: string; data?: Record<string, any>};
export type Visuals = {beats?: VisualBeat[]; caption?: CaptionPlan};
export type PlanLine = {text: string; start: number; end: number; bg?: string; aha?: boolean};
export type VisualShortProps = {
  base: 'quote' | 'lyrics' | 'none'; visuals: Visuals;
  width: number; height: number; fps: number; duration: number;
  lines?: PlanLine[]; hold_until?: number; cues?: Cue[];
  style: {color: string; accent: string; [k: string]: unknown};
  [k: string]: unknown;
};

export const visualShortDefaults: VisualShortProps = {
  base: 'none', width: 1080, height: 1920, fps: 30, duration: 8, style: {color: '#F4F7FF', accent: '#E2B75A'}, hold_until: 7.5,
  lines: [{text: 'Your *words* here', start: 0, end: 7.5}], visuals: {beats: [{line: 0, treatment: 'hook'}]},
};

export const Backdrop: React.FC<{t: number; accent: string}> = ({t, accent}) => (
  <AbsoluteFill style={{background: 'radial-gradient(circle at 50% 38%, #1c2540 0%, #0a0f1c 55%, #05070d 100%)'}}>
    <div style={{position: 'absolute', width: 980, height: 980, borderRadius: '50%', left: 50 + 70 * Math.sin(t * 0.6), top: 380 + 50 * Math.cos(t * 0.5), background: `radial-gradient(circle, ${accent}26 0%, transparent 65%)`}} />
    {Array.from({length: 30}).map((_, i) => {   // slow dust rising
      const size = 3 + random(`z${i}`) * 5, y = 1980 - ((random(`y${i}`) * 1980 + t * (14 + random(`s${i}`) * 26)) % 1980);
      return <div key={i} style={{position: 'absolute', left: random(`x${i}`) * 1080, top: y, width: size, height: size, borderRadius: '50%', background: i % 3 ? accent : COOL, opacity: 0.12 + random(`o${i}`) * 0.3}} />;
    })}
  </AbsoluteFill>
);

export const Title: React.FC<{text: string; accent: string; color: string; k: number}> = ({text, accent, color, k}) => (
  <div style={{position: 'absolute', left: 120, right: 120, top: 170, height: 250, display: 'flex', alignItems: 'flex-start', justifyContent: 'center', textAlign: 'center', opacity: k, transform: `translateY(${(1 - k) * 36}px)`}}>
    <span style={{fontFamily: SANS, fontSize: Array.from(text).length > 44 ? 62 : Array.from(text).length > 26 ? 76 : 92, lineHeight: 1.12, fontWeight: 800, letterSpacing: -0.5, color, textShadow: shadow}}>{marked(text, accent)}</span>
  </div>
);

export const VisualShort: React.FC<VisualShortProps> = (props) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const accent = props.style.accent, color = props.style.color, lines = props.lines ?? [];
  const beats = (props.visuals?.beats ?? []).filter((b) => SCENES[b.treatment] && lines[b.line]);
  const owned = new Set(beats.map((b) => b.line));
  const cap = props.visuals?.caption && CAPTIONS[props.visuals.caption.treatment] ? props.visuals.caption : null;
  const cues = props.cues ?? [];
  const master = interpolate(t, [0, 0.5, props.duration - 0.6, props.duration], [0, 1, 1, 0], CLAMP);
  const lastEnd = cues.length ? cues[cues.length - 1].end : 0, capFade = interpolate(t, [lastEnd + 0.3, lastEnd + 1.0], [1, 0], CLAMP);   // gone before the credit page
  const Caption = cap ? CAPTIONS[cap.treatment] : null;
  return (
    <AbsoluteFill>
      {props.base === 'quote' ? <Quote {...(props as unknown as QuoteProps)} lines={lines.map((l, i) => (owned.has(i) ? {...l, text: ''} : l))} />
        : props.base === 'lyrics' ? <Lyrics {...(props as unknown as LyricsProps)} cues={cap ? cues.map((c) => ({...c, text: ''})) : cues} />
        : <AbsoluteFill style={{background: '#05070d'}} />}
      {Caption && cap ? <AbsoluteFill style={{opacity: capFade, pointerEvents: 'none'}}><Caption cues={cues} plan={cap} t={t} frame={frame} color={color} accent={accent} /></AbsoluteFill> : null}
      <AbsoluteFill style={{opacity: master, pointerEvents: 'none'}}>
        {lines.map((l, i) => {
          const next = i < lines.length - 1 ? lines[i + 1].start : props.hold_until ?? props.duration, from = i === 0 ? 0 : l.start - 0.2, to = next + 0.2;
          if (t < from - 0.05 || t > to + 0.05) return null;
          const local = t - l.start, span = Math.max(0.5, next - l.start);
          const inK = i === 0 ? 1 : interpolate(t, [from, from + 0.35], [0, 1], CLAMP), outK = interpolate(t, [to - 0.35, to], [1, 0], CLAMP);
          const pulse = l.aha ? interpolate(local, [0, 0.18, 1.1], [0, 0.55, 0], CLAMP) : 0;   // the takeaway lands with a glow
          const beat = beats.find((b) => b.line === i), S = beat ? SCENES[beat.treatment] : null;
          return (
            <React.Fragment key={i}>
              {beat && S ? (
                <AbsoluteFill style={{opacity: inK * outK}}>
                  {S.backdrop ? <Backdrop t={t} accent={accent} /> : null}
                  {S.title ? <Title text={l.text} accent={accent} color={color} k={interpolate(local, [0, 0.6], [0, 1], {easing: ease, ...CLAMP})} /> : null}
                  <S.C data={beat.data ?? {}} local={local} span={span} t={t} text={l.text} accent={accent} color={color} />
                </AbsoluteFill>
              ) : null}
              {pulse > 0 ? <AbsoluteFill style={{background: `radial-gradient(circle at 50% 44%, ${accent}${Math.round(pulse * 160).toString(16).padStart(2, '0')} 0%, transparent 62%)`}} /> : null}
            </React.Fragment>
          );
        })}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

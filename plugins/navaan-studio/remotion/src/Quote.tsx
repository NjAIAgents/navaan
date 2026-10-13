import React from 'react';
import {AbsoluteFill, Audio, Img, Easing, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';

export type Line = {text: string; start: number; end: number};
export type QuoteProps = {
  width: number;
  height: number;
  fps: number;
  duration: number;
  background: string;
  music: string | null;
  voiceover: string | null;
  lines: Line[];
  hold_until: number;
  author: {text: string; start: number; end: number} | null;
  camera: 'push_in' | 'pull_out' | 'pan_left' | 'pan_right' | 'drift';
  transition: 'rise' | 'fade' | 'blur';
  style: {color: string; accent: string; dim: number};
  watermark: string;
};

export const defaultProps: QuoteProps = {
  width: 1080, height: 1920, fps: 30, duration: 10, background: 'background.jpg', music: null, voiceover: null,
  lines: [{text: 'Your words here', start: 1, end: 8}], hold_until: 8.5, author: null,
  camera: 'push_in', transition: 'rise', style: {color: '#FFFFFF', accent: '#FF4D7E', dim: 0.45}, watermark: 'NAVAAN',
};

const FONT = `"Kohinoor Devanagari","Noto Serif Devanagari","Noto Sans Devanagari","Georgia","Noto Serif","DejaVu Serif",serif`;
const ease = Easing.bezier(0.22, 1, 0.36, 1);
const smooth = Easing.inOut(Easing.cubic);

const cameraStyle = (cam: QuoteProps['camera'], p: number): React.CSSProperties => {
  let s = 1, x = 0, y = 0;
  if (cam === 'push_in') s = 1 + 0.14 * p;
  else if (cam === 'pull_out') s = 1.14 - 0.14 * p;
  else if (cam === 'pan_left') { s = 1.12; x = 6 * (0.5 - p); }
  else if (cam === 'pan_right') { s = 1.12; x = -6 * (0.5 - p); }
  else { s = 1.06 + 0.04 * Math.sin(Math.PI * p); x = 1.5 * Math.sin(2 * Math.PI * p); y = 1.2 * Math.sin(2 * Math.PI * p + 1); }
  return {transform: `translate(${x}%, ${y}%) scale(${s})`};
};

export const Quote: React.FC<QuoteProps> = (props) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames, width, height} = useVideoConfig();
  const t = frame / fps;
  const p = interpolate(frame, [0, durationInFrames], [0, 1], {easing: smooth, extrapolateRight: 'clamp'});
  const dev = props.lines.some((l) => /[ऀ-ॿ]/.test(l.text));
  const longest = Math.max(...props.lines.map((l) => Array.from(l.text).length));
  const size = Math.min(dev ? 92 : 104, Math.floor((width - 192) / (longest * (dev ? 0.5 : 0.52))));
  const lh = Math.round(size * 1.42);
  const blockTop = Math.round(height * 0.44 - (lh * props.lines.length) / 2);
  const holdOut = interpolate(t, [props.hold_until, props.hold_until + 0.6], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const master = interpolate(t, [0, 0.5, props.duration - 0.6, props.duration], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

  const enter = (start: number) => {
    const k = interpolate(t, [start, start + 0.7], [0, 1], {easing: ease, extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
    const rise = props.transition === 'rise' ? (1 - k) * 44 : 0;
    const blur = props.transition === 'blur' ? (1 - k) * 14 : 0;
    return {opacity: k * holdOut, transform: `translateY(${rise}px)`, filter: blur ? `blur(${blur}px)` : undefined} as React.CSSProperties;
  };

  const accentW = props.author ? interpolate(t, [props.author.start, props.author.start + 0.6], [0, 80], {easing: ease, extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) : 0;
  const shadow = '0 6px 28px rgba(0,0,0,0.65), 0 0 2px rgba(0,0,0,0.5)';

  return (
    <AbsoluteFill style={{backgroundColor: '#000', opacity: master}}>
      <AbsoluteFill style={{overflow: 'hidden'}}>
        <Img src={staticFile(props.background)} style={{width: '100%', height: '100%', objectFit: 'cover', ...cameraStyle(props.camera, p)}} />
      </AbsoluteFill>
      <AbsoluteFill style={{background: `linear-gradient(180deg, rgba(0,0,0,${props.style.dim * 0.7}) 0%, rgba(0,0,0,${props.style.dim * 1.15}) 45%, rgba(0,0,0,${props.style.dim * 1.3}) 100%)`}} />
      {props.lines.map((l, i) => (
        <div key={i} style={{position: 'absolute', left: 0, width, top: blockTop + i * lh, height: lh, display: 'flex', alignItems: 'center', justifyContent: 'center', ...enter(l.start)}}>
          <span style={{fontFamily: FONT, fontSize: size, fontWeight: dev ? 600 : 400, color: props.style.color, textShadow: shadow, whiteSpace: 'nowrap'}}>{l.text}</span>
        </div>
      ))}
      {props.author ? (
        <div style={{position: 'absolute', left: 0, width, top: blockTop + lh * props.lines.length + 36, display: 'flex', flexDirection: 'column', alignItems: 'center', opacity: interpolate(t, [props.author.start, props.author.start + 0.7], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) * holdOut}}>
          <div style={{height: 4, width: accentW, background: props.style.accent, marginBottom: 30, borderRadius: 2}} />
          <span style={{fontFamily: FONT, fontSize: Math.round(size * 0.5), color: 'rgba(255,255,255,0.92)', textShadow: shadow}}>{props.author.text}</span>
        </div>
      ) : null}
      <div style={{position: 'absolute', left: 0, width, bottom: 130, textAlign: 'center', fontFamily: FONT, fontSize: 34, letterSpacing: props.watermark.startsWith('@') ? 2 : 14, color: 'rgba(255,255,255,0.68)', opacity: interpolate(t, [0.4, 1.1], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}}>
        {props.watermark.startsWith('@') ? props.watermark : props.watermark.toUpperCase()}
      </div>
      {props.music ? <Audio src={staticFile(props.music)} volume={props.voiceover ? 0.35 : 0.9} /> : null}
      {props.voiceover ? <Audio src={staticFile(props.voiceover)} volume={1} /> : null}
    </AbsoluteFill>
  );
};

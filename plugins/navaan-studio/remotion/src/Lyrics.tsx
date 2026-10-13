import React from 'react';
import {AbsoluteFill, Audio, Easing, OffthreadVideo, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';

export type Cue = {text: string; start: number; end: number};
export type LyricsProps = {
  width: number;
  height: number;
  fps: number;
  duration: number;
  bg: string;
  bg_is_image?: boolean;
  audio: string | null;
  cues: Cue[];
  title: string;
  hook: string;
  handle: {text: string; icon?: string; start: number} | null;
  style: {color: string; accent: string; dim: number};
  mode?: 'reel' | 'cover';
};

export const lyricsDefaults: LyricsProps = {
  width: 1080, height: 1920, fps: 30, duration: 10, bg: 'reel_bg.mp4', audio: null,
  cues: [{text: 'Your lyric line here', start: 1, end: 5}], title: '', hook: '', handle: null,
  style: {color: '#FFFFFF', accent: '#FF4D7E', dim: 0.42}, mode: 'reel',
};

const FONT = `"Kohinoor Devanagari","Noto Serif Devanagari","Noto Sans Devanagari","Georgia","Noto Serif","DejaVu Serif",serif`;
const ease = Easing.bezier(0.22, 1, 0.36, 1);
const shadow = '0 6px 28px rgba(0,0,0,0.7), 0 0 2px rgba(0,0,0,0.5)';
const dev = (s: string) => /[ऀ-ॿ]/.test(s);

const Glyph: React.FC<{size: number; color: string}> = ({size, color}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.9} strokeLinecap="round" style={{filter: 'drop-shadow(0 6px 14px rgba(0,0,0,0.6))'}}>
    <rect x="3" y="3" width="18" height="18" rx="5.2" />
    <circle cx="12" cy="12" r="4.1" />
    <circle cx="17.3" cy="6.7" r="0.6" fill={color} />
  </svg>
);

const HandleRow: React.FC<{text: string; size: number; color: string}> = ({text, size, color}) => (
  <div style={{display: 'flex', alignItems: 'center', gap: Math.round(size * 0.38)}}>
    <Glyph size={Math.round(size * 0.95)} color={color} />
    <span style={{fontFamily: FONT, fontSize: size, letterSpacing: 3, color, textShadow: shadow, whiteSpace: 'nowrap'}}>{text}</span>
  </div>
);

export const Lyrics: React.FC<LyricsProps> = (p) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const t = frame / fps;
  const cover = p.mode === 'cover';
  const master = cover ? 1 : interpolate(t, [0, 0.4, p.duration - 0.5, p.duration], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const fadeIn = (start: number, d = 0.7) => interpolate(t, [start, start + d], [0, 1], {easing: ease, extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const dim = p.style.dim;
  const lastEnd = p.cues.length ? Math.max(...p.cues.map((c) => c.end)) : 0;

  return (
    <AbsoluteFill style={{backgroundColor: '#000', opacity: master}}>
      <AbsoluteFill>
        {p.bg_is_image ? (
          <Img src={staticFile(p.bg)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
        ) : (
          <OffthreadVideo src={staticFile(p.bg)} muted style={{width: '100%', height: '100%', objectFit: 'cover'}} />
        )}
      </AbsoluteFill>
      <AbsoluteFill style={{background: `linear-gradient(180deg, rgba(0,0,0,${dim * 0.8}) 0%, rgba(0,0,0,${dim * 1.2}) 45%, rgba(0,0,0,${dim * 1.5}) 100%)`}} />
      {cover ? (
        <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center'}}>
          <div style={{width: 130, height: 4, background: p.style.accent, borderRadius: 2, marginBottom: 46}} />
          <div style={{fontFamily: FONT, fontSize: 84, lineHeight: 1.28, textAlign: 'center', color: p.style.color, textShadow: shadow, maxWidth: width - 190, textWrap: 'balance' as const}}>{p.hook}</div>
          <div style={{fontFamily: FONT, fontSize: 46, color: 'rgba(255,255,255,0.86)', textShadow: shadow, marginTop: 58, fontWeight: dev(p.title) ? 600 : 400}}>{p.title}</div>
          {p.handle ? <div style={{position: 'absolute', top: Math.round(height * 0.77)}}><HandleRow text={p.handle.text} size={44} color={p.style.color} /></div> : null}
        </AbsoluteFill>
      ) : (
        <>
          {p.cues.map((c, i) => {
            const k = fadeIn(c.start, 0.55);
            const out = interpolate(t, [c.end - 0.45, c.end], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
            const size = dev(c.text) ? 84 : 76;
            return (
              <div key={i} style={{position: 'absolute', left: 0, width, top: Math.round(height * 0.5 - 230), height: 460, display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: k * out, transform: `translateY(${(1 - k) * 36}px)`}}>
                <div style={{fontFamily: FONT, fontSize: size, lineHeight: 1.34, textAlign: 'center', color: p.style.color, textShadow: shadow, maxWidth: width - 170, fontWeight: dev(c.text) ? 600 : 400, textWrap: 'balance' as const}}>{c.text}</div>
              </div>
            );
          })}
          {p.handle ? (
            <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', opacity: fadeIn(p.handle.start, 0.9), transform: `translateY(${(1 - fadeIn(p.handle.start, 0.9)) * 30}px)`}}>
              <div style={{width: 90 * fadeIn(p.handle.start, 0.9), height: 4, background: p.style.accent, borderRadius: 2, marginBottom: 40}} />
              <div style={{fontFamily: FONT, fontSize: 76, color: p.style.color, textShadow: shadow, marginBottom: 44, fontWeight: dev(p.title) ? 600 : 400}}>{p.title}</div>
              <HandleRow text={p.handle.text} size={50} color={p.style.color} />
            </AbsoluteFill>
          ) : null}
        </>
      )}
      {p.audio && !cover ? <Audio src={staticFile(p.audio)} volume={1} /> : null}
    </AbsoluteFill>
  );
};

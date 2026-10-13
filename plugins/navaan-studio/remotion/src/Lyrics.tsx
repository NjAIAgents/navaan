import React from 'react';
import {AbsoluteFill, Audio, Easing, OffthreadVideo, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';

export type Cue = {text: string; start: number; end: number};
export type Act = {kind: 'ache' | 'confess' | 'hope'; from: number; to: number};
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
  acts?: Act[];
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


// Director's grade per act: [brightness, saturate, contrast] at the start and end of the act.
const GRADE: Record<Act['kind'], {a: [number, number, number]; b: [number, number, number]}> = {
  ache: {a: [0.82, 0.78, 1.0], b: [0.80, 0.74, 1.02]},
  confess: {a: [1.0, 1.18, 1.1], b: [1.04, 1.22, 1.12]},
  hope: {a: [0.95, 1.0, 1.04], b: [1.22, 1.15, 1.0]},
};
const clamp01 = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

export const Lyrics: React.FC<LyricsProps> = (p) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const t = frame / fps;
  const cover = p.mode === 'cover';
  const master = cover ? 1 : interpolate(t, [0, 0.4, p.duration - 0.5, p.duration], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const fadeIn = (start: number, d = 0.7) => interpolate(t, [start, start + d], [0, 1], {easing: ease, extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const dim = p.style.dim;
  const lastEnd = p.cues.length ? Math.max(...p.cues.map((c) => c.end)) : 0;

  const acts: Act[] = p.acts && p.acts.length ? p.acts : [{kind: 'ache', from: 0, to: p.duration}];
  const actAt = (x: number) => acts.find((a) => x >= a.from && x < a.to) || acts[acts.length - 1];
  const act = actAt(t);
  const conf = acts.find((a) => a.kind === 'confess');
  const hope = acts.find((a) => a.kind === 'hope');
  // grade keyframes
  const times: number[] = [0];
  const ch: number[][] = [[], [], []];
  const push = (x: number, v: number[]) => { if (x > times[times.length - 1] + 0.01) { times.push(x); v.forEach((n, i) => ch[i].push(n)); } };
  const g0 = GRADE[acts[0].kind].a; ch[0].push(g0[0]); ch[1].push(g0[1]); ch[2].push(g0[2]);
  acts.forEach((a) => { const g = GRADE[a.kind]; push(a.from + 0.7, g.a); push(Math.max(a.from + 0.8, a.to - 0.3), g.b); });
  const lastG = GRADE[acts[acts.length - 1].kind].b; push(p.duration, lastG);
  const grade = ch.map((arr) => interpolate(t, times, arr, clamp01));
  // camera: slow push-in over the whole reel, a punch-in when the rap starts, released at the return
  const punch = conf
    ? interpolate(t, [conf.from, conf.from + 0.5, conf.to, conf.to + 1.4], [0, 0.06, 0.06, 0], {...clamp01, easing: ease})
    : 0;
  const zoom = 1 + 0.09 * (t / p.duration) + punch;
  // one-beat dip at the language change, so the cut lands
  const dipAt = (x: number) => interpolate(t, [x - 0.12, x, x + 0.4], [0, 0.55, 0], clamp01);
  const dip = conf ? Math.max(dipAt(conf.from), dipAt(conf.to)) : 0;
  // dawn glow rising through the closing act
  const glow = hope ? interpolate(t, [hope.from, hope.to + 0.5], [0, 0.34], clamp01) : 0;

  return (
    <AbsoluteFill style={{backgroundColor: '#000', opacity: master}}>
      <AbsoluteFill style={cover ? undefined : {transform: `scale(${zoom})`, filter: `brightness(${grade[0] * (1 - dip)}) saturate(${grade[1]}) contrast(${grade[2]})`}}>
        {p.bg_is_image ? (
          <Img src={staticFile(p.bg)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
        ) : (
          <OffthreadVideo src={staticFile(p.bg)} muted style={{width: '100%', height: '100%', objectFit: 'cover'}} />
        )}
      </AbsoluteFill>
      <AbsoluteFill style={{background: `linear-gradient(180deg, rgba(0,0,0,${dim * 0.8}) 0%, rgba(0,0,0,${dim * 1.2}) 45%, rgba(0,0,0,${dim * 1.5}) 100%)`}} />
      {!cover && glow > 0 ? <AbsoluteFill style={{background: 'radial-gradient(ellipse 90% 45% at 50% 100%, rgba(255,176,96,' + glow + ') 0%, rgba(255,120,80,' + glow * 0.35 + ') 45%, rgba(0,0,0,0) 80%)', mixBlendMode: 'screen' as const}} /> : null}
      {!cover ? <AbsoluteFill style={{background: 'radial-gradient(ellipse at 50% 50%, rgba(0,0,0,0) 55%, rgba(0,0,0,0.55) 100%)'}} /> : null}
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
            const a = actAt(c.start + 0.01);
            const rap = a.kind === 'confess';
            const k = fadeIn(c.start, rap ? 0.3 : a.kind === 'hope' ? 0.9 : 0.8);
            const out = interpolate(t, [c.end - (rap ? 0.25 : 0.55), c.end], [1, 0], clamp01);
            const size = dev(c.text) ? 84 : rap ? 88 : 76;
            const isLast = hope && i === p.cues.length - 1;
            // slow drift in on the final line
            const finalScale = isLast ? interpolate(t, [c.start, c.end], [1, 1.07], clamp01) : 1;
            const words = c.text.split(' ');
            return (
              <div key={i} style={{position: 'absolute', left: 0, width, top: Math.round(height * 0.5 - 230), height: 460, display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: out * (rap ? 1 : k), transform: rap ? undefined : `translateY(${(1 - k) * 30}px) scale(${finalScale})`}}>
                <div style={{fontFamily: FONT, fontSize: size, lineHeight: 1.3, textAlign: 'center', color: p.style.color, textShadow: shadow, maxWidth: width - 150, fontWeight: dev(c.text) ? 600 : rap ? 700 : 400, textWrap: 'balance' as const, letterSpacing: rap ? 0.5 : 0}}>
                  {rap
                    ? words.map((w, wi) => {
                        const step = Math.min(0.2, ((c.end - c.start) * 0.5) / Math.max(1, words.length));
                        const wk = interpolate(t, [c.start + wi * step, c.start + wi * step + 0.22], [0, 1], {...clamp01, easing: ease});
                        return <span key={wi} style={{display: 'inline-block', opacity: wk, transform: `translateY(${(1 - wk) * 22}px)`, marginRight: '0.28em'}}>{w}</span>;
                      })
                    : c.text}
                </div>
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

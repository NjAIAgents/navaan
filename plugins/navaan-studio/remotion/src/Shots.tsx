import React from 'react';
import {AbsoluteFill, Audio, Img, Loop, OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';

// A music video stitched from the user's own pictures. Each shot shows one picture with a slow camera move, shots cross fade.
// shots.json (approved by the user) is turned into these props by shots_render.py.
export type Shot = {start: number; end: number; image: string; camera: string; focus?: [number, number]; loop?: string | null};
export type ShotsProps = {
  width: number;
  height: number;
  fps: number;
  duration: number;
  audio: string | null;
  shots: Shot[];
  loopSeconds?: number;
  fade: number;
  grade: {dim: number; vignette: number};
  fadeOut: number;
};

export const shotsDefaults: ShotsProps = {
  width: 1920, height: 1080, fps: 24, duration: 10, audio: null, shots: [], fade: 1.2,
  grade: {dim: 0.08, vignette: 0.35}, fadeOut: 2,
};

const BASE = 1.16; // every picture is drawn a little larger than the frame, so a move never shows an edge

// camera move -> transform for progress p in 0..1. focus is where a push or pull aims, as fractions of the picture.
const move = (camera: string, p: number, focus: [number, number]) => {
  const e = p; // linear reads as a steady camera; the fades hide the joins
  const [fx, fy] = focus;
  const travel = (BASE - 1) * 50; // percent of the frame the picture can slide before an edge shows
  switch (camera) {
    case 'push_in': {
      const s = BASE + 0.1 * e;
      return {s, x: (0.5 - fx) * 8 * e, y: (0.5 - fy) * 8 * e};
    }
    case 'pull_out': {
      const s = BASE + 0.1 * (1 - e);
      return {s, x: (0.5 - fx) * 8 * (1 - e), y: (0.5 - fy) * 8 * (1 - e)};
    }
    case 'pan_left': return {s: BASE, x: travel - 2 * travel * e, y: 0};
    case 'pan_right': return {s: BASE, x: -travel + 2 * travel * e, y: 0};
    case 'tilt_up': return {s: BASE, x: 0, y: travel - 2 * travel * e};
    case 'tilt_down': return {s: BASE, x: 0, y: -travel + 2 * travel * e};
    case 'drift': return {s: BASE + 0.03, x: -travel * 0.6 + 1.2 * travel * e, y: travel * 0.3 - 0.6 * travel * e};
    default: return {s: BASE, x: 0, y: 0}; // hold
  }
};

const ShotView: React.FC<{shot: Shot; len: number; fade: number; lead: number; loopSeconds: number}> = ({shot, len, fade, lead, loopSeconds}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  // the sequence starts `lead` seconds before the shot's own start so the fade in overlaps the previous shot
  const t = f / fps - lead;
  const p = Math.min(1, Math.max(0, t / Math.max(0.1, len)));
  const op = interpolate(f / fps, [0, lead || 0.001, lead + len, lead + len + fade], [lead ? 0 : 1, 1, 1, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const m = move(shot.camera, p, shot.focus || [0.5, 0.5]);
  const style: React.CSSProperties = {width: '100%', height: '100%', objectFit: 'cover', objectPosition: `${(shot.focus?.[0] ?? 0.5) * 100}% ${(shot.focus?.[1] ?? 0.5) * 100}%`, transform: `translate(${m.x}%, ${m.y}%) scale(${m.s})`, transformOrigin: '50% 50%'};
  return (
    <AbsoluteFill style={{opacity: op}}>
      {shot.loop ? (
        // a seamless loop made by motion_clips.py: steam, cloth, flames. The camera move still runs on top.
        <Loop durationInFrames={Math.max(1, Math.round(loopSeconds * fps))}>
          <OffthreadVideo src={staticFile(shot.loop)} muted style={style} />
        </Loop>
      ) : (
        <Img src={staticFile(shot.image)} style={style} />
      )}
    </AbsoluteFill>
  );
};

export const Shots: React.FC<ShotsProps> = (p) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const out = p.fadeOut > 0 ? interpolate(t, [p.duration - p.fadeOut, p.duration], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) : 1;
  return (
    <AbsoluteFill style={{background: '#000'}}>
      <AbsoluteFill style={{opacity: out}}>
        {p.shots.map((s, i) => {
          const lead = i === 0 ? 0 : p.fade;
          const from = Math.max(0, s.start - lead);
          const len = Math.max(0.2, s.end - s.start);
          const total = lead + len + p.fade; // keep drawing through the next shot's fade in
          return (
            <Sequence key={i} from={Math.round(from * fps)} durationInFrames={Math.max(1, Math.round(total * fps))}>
              <ShotView shot={s} len={len} fade={p.fade} lead={s.start - from} loopSeconds={p.loopSeconds ?? 6} />
            </Sequence>
          );
        })}
        <AbsoluteFill style={{background: `rgba(0,0,0,${p.grade.dim})`}} />
        <AbsoluteFill style={{background: `radial-gradient(ellipse at 50% 50%, rgba(0,0,0,0) 55%, rgba(0,0,0,${p.grade.vignette}) 100%)`}} />
      </AbsoluteFill>
      {p.audio ? <Audio src={staticFile(p.audio)} volume={1} /> : null}
    </AbsoluteFill>
  );
};

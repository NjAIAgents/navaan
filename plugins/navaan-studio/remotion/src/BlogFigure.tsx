import React from 'react';
import {AbsoluteFill} from 'remotion';
import {SCENES} from './treatments/scenes';
import {Backdrop, Title} from './VisualShort';
import {GOLD, INK} from './treatments/common';

// One explanatory figure for a blog post (NAV-139): a scene treatment of the shorts library (a flow, a comparison, a checklist, a timeline, a chart ...) drawn at its finished moment and rendered as a still,
// 1080x1500. It reuses the treatments as they are, so a figure with a number has the same rule as in a short: a source or the sample label (scripts/visuals_plan.py checks it).
export type FigureProps = {width: number; height: number; treatment: string; data: Record<string, any>; text: string; accent?: string; color?: string};
export const figureDefaults: FigureProps = {width: 1080, height: 1500, treatment: 'flow', data: {nodes: ['Your question', 'Patterns it has seen', 'A plausible answer', 'Your check']}, text: 'How an answer is made'};

export const BlogFigure: React.FC<FigureProps> = (p) => {
  const S = SCENES[p.treatment]; const accent = p.accent ?? GOLD, color = p.color ?? INK;
  if (!S) return <AbsoluteFill style={{background: '#05070d'}} />;
  return (
    <AbsoluteFill style={{overflow: 'hidden'}}>
      <div style={{position: 'absolute', left: 0, top: -120, width: 1080, height: 1920}}>   {/* the vertical stage of a short, cut to the part a figure needs */}
        {S.backdrop ? <Backdrop t={3} accent={accent} /> : <AbsoluteFill style={{background: '#05070d'}} />}
        {S.title ? <Title text={p.text} accent={accent} color={color} k={1} /> : null}
        <S.C data={p.data} local={9} span={10} t={3} text={p.text} accent={accent} color={color} />
      </div>
    </AbsoluteFill>
  );
};

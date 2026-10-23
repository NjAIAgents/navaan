import React from 'react';
import {AbsoluteFill} from 'remotion';
import {SANS} from './treatments/common';

// One explanatory figure for a blog post (NAV-139, redrawn in NAV-148): a flow, a comparison, a checklist, a timeline, a chart ... drawn as a still in the look of a blog, not of a short:
// white, dark text, the cover's accent colour, 1200 wide, set in flowing layout. The canvas is tall and scripts/blog_images.py crops it to the content, so no figure has an empty foot or a cut-off end.
// It takes the same treatment names and the same data as the shorts' scene library (scripts/visuals_plan.py checks a number has a source or the sample label), but none of its dark vertical stage.
export type FigureProps = {width: number; height: number; treatment: string; data: Record<string, any>; text: string; palette?: string};
export const figureDefaults: FigureProps = {width: 1200, height: 2400, treatment: 'flow', data: {nodes: ['Your question', 'Patterns it has seen', 'A plausible answer', 'Your check']}, text: 'How an answer is made', palette: 'midnight'};

export const W = 1200, PAD = 64, INNER = W - 2 * PAD;
const INK = '#14171F', MUTE = '#5B6270', LINE = '#E3E6EC', SOFT = '#F4F6FA', RED = '#D64545', GREEN = '#1F8F63';
export const ACCENTS: Record<string, string> = {midnight: '#3B5BDB', indigo: '#5B4BDB', forest: '#1F8F63', ember: '#D9582B', ocean: '#0E7FA3', slate: '#4A5A6B', paper: '#B4472A', mono: '#1F2328'};   // the cover palettes' accents, darkened to read on white (a test keeps the names equal)

const Frame: React.FC<{title: string; accent: string; children: React.ReactNode}> = ({title, accent, children}) => (
  <div style={{width: W, boxSizing: 'border-box', padding: PAD, fontFamily: SANS, color: INK, background: '#fff'}}>
    <div style={{display: 'flex', gap: 22, marginBottom: 46}}>
      <div style={{width: 10, borderRadius: 5, background: accent, flex: 'none'}} />
      <div style={{fontSize: 52, fontWeight: 800, lineHeight: 1.12, letterSpacing: -1}}>{title}</div>
    </div>
    {children}
  </div>
);

// where a number came from, said under the figure: its source, or that it is sample data, or that a drawing is only an illustration
const Source: React.FC<{data: Record<string, any>; illustration?: boolean}> = ({data, illustration}) => {
  const say = data.source ? `Source: ${data.source}` : data.sample ? 'SAMPLE DATA' : illustration ? 'Illustration, not data' : '';
  if (!say) return null;
  const flag = !data.source && data.sample;
  return <div style={{marginTop: 40, fontSize: flag ? 26 : 24, fontWeight: flag ? 800 : 500, letterSpacing: flag ? 4 : 0, color: flag ? RED : MUTE, wordBreak: 'break-all'}}>{say}</div>;
};

type P = {data: Record<string, any>; accent: string};

const Compare: React.FC<P> = ({data, accent}) => {
  const card = (p: {title: string; text: string}, hot: boolean) => (
    <div style={{flex: 1, borderRadius: 24, border: `2px solid ${hot ? accent : LINE}`, background: hot ? `${accent}12` : SOFT, padding: '36px 40px'}}>
      <div style={{fontSize: 26, fontWeight: 700, letterSpacing: 4, textTransform: 'uppercase', color: hot ? accent : MUTE}}>{p.title}</div>
      <div style={{fontSize: 52, fontWeight: 800, lineHeight: 1.12, marginTop: 16}}>{p.text}</div>
    </div>);
  return <div style={{display: 'flex', alignItems: 'center', gap: 24}}>{card(data.left, false)}<div style={{fontSize: 76, fontWeight: 800, color: accent}}>{data.sign ?? '≠'}</div>{card(data.right, true)}</div>;
};

const Bars: React.FC<P> = ({data, accent}) => (
  <div>
    {(data.rows ?? []).map((r: {label: string; fill: number}, i: number) => (
      <div key={i} style={{marginBottom: 34}}>
        <div style={{fontSize: 36, fontWeight: 600, marginBottom: 12}}>{r.label}</div>
        <div style={{height: 34, borderRadius: 17, background: '#EEF0F5', overflow: 'hidden'}}><div style={{height: '100%', width: `${Math.max(0, Math.min(1, r.fill)) * 100}%`, borderRadius: 17, background: i === 0 ? accent : '#9AA3B2'}} /></div>
      </div>))}
    <Source data={data} illustration />
  </div>
);

const Stat: React.FC<P> = ({data, accent}) => {
  const dec = data.decimals ?? 0, text = Number(data.value).toLocaleString('en-US', {minimumFractionDigits: dec, maximumFractionDigits: dec});
  return (
    <div style={{textAlign: 'center', padding: '20px 0'}}>
      <div style={{fontSize: 230, fontWeight: 800, lineHeight: 1, letterSpacing: -6, color: accent}}>{text}<span style={{fontSize: 100, marginLeft: 12}}>{data.unit}</span></div>
      <div style={{fontSize: 46, fontWeight: 600, lineHeight: 1.25, marginTop: 28}}>{data.label}</div>
      <Source data={data} />
    </div>
  );
};

const Chat: React.FC<P> = ({data, accent}) => (
  <div style={{display: 'flex', flexDirection: 'column', gap: 26}}>
    <div style={{alignSelf: 'flex-end', maxWidth: 820, padding: '30px 38px', borderRadius: '34px 34px 8px 34px', background: accent, color: '#fff', fontSize: 40, lineHeight: 1.3, fontWeight: 600}}>{data.question}</div>
    <div style={{alignSelf: 'flex-start', maxWidth: 900, padding: '30px 38px', borderRadius: '34px 34px 34px 8px', background: SOFT, border: `2px solid ${LINE}`, fontSize: 38, lineHeight: 1.35}}>{data.answer}</div>
    {(data.tags ?? []).length > 0 && <div style={{display: 'flex', gap: 16, flexWrap: 'wrap'}}>{(data.tags as string[]).slice(0, 2).map((t, i) => <span key={i} style={{padding: '12px 28px', borderRadius: 999, border: `2px solid ${accent}`, color: accent, fontSize: 30, fontWeight: 700}}>{t}</span>)}</div>}
    <Source data={data} illustration />
  </div>
);

const Flow: React.FC<P> = ({data, accent}) => {
  const nodes: string[] = data.nodes ?? [];
  return (
    <div style={{display: 'flex', flexDirection: 'column', alignItems: 'stretch'}}>
      {nodes.map((n, i) => {
        const last = i === nodes.length - 1;
        return (
          <React.Fragment key={i}>
            <div style={{padding: '30px 36px', borderRadius: 22, textAlign: 'center', fontSize: 42, fontWeight: 700, lineHeight: 1.2, border: `2px solid ${last ? accent : LINE}`, background: last ? `${accent}14` : SOFT, color: last ? accent : INK}}>{n}</div>
            {!last && <svg width={INNER} height="64" viewBox={`0 0 ${INNER} 64`}><path d={`M${INNER / 2} 8 V48 M${INNER / 2 - 16} 34 L${INNER / 2} 52 L${INNER / 2 + 16} 34`} stroke={accent} strokeWidth="5" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>}
          </React.Fragment>);
      })}
    </div>
  );
};

const Chart: React.FC<P> = ({data, accent}) => {
  const Wc = INNER, H = 560, series: {label: string; points: number[]}[] = data.series ?? [], n = Math.max(1, ...series.map((s) => s.points.length)), labels: string[] = data.xlabels ?? [];
  const xy = (v: number, i: number) => [48 + (i * (Wc - 96)) / Math.max(1, n - 1), H - 56 - Math.max(0, Math.min(1, v)) * (H - 120)] as const;
  const path = (a: number[]) => a.map((v, i) => `${i ? 'L' : 'M'}${xy(v, i)[0]} ${xy(v, i)[1]}`).join(' ');
  const tones = [accent, '#9AA3B2'];
  return (
    <div>
      <svg width={Wc} height={H} viewBox={`0 0 ${Wc} ${H}`}>
        {[0, 1, 2, 3].map((g) => <line key={g} x1="48" x2={Wc - 48} y1={H - 56 - (g * (H - 120)) / 3} y2={H - 56 - (g * (H - 120)) / 3} stroke={LINE} strokeWidth="2" />)}
        {series.map((s, k) => <g key={k}><path d={path(s.points)} stroke={tones[k % 2]} strokeWidth="7" fill="none" strokeLinecap="round" strokeLinejoin="round" />{s.points.map((v, i) => <circle key={i} cx={xy(v, i)[0]} cy={xy(v, i)[1]} r="9" fill="#fff" stroke={tones[k % 2]} strokeWidth="5" />)}</g>)}
        {Array.from({length: n}).map((_, i) => <text key={i} x={xy(0, i)[0]} y={H - 14} fill={MUTE} fontSize="26" textAnchor="middle" fontFamily={SANS}>{labels[i] ?? ''}</text>)}
      </svg>
      <div style={{display: 'flex', gap: 34, marginTop: 8}}>{series.map((s, k) => <div key={k} style={{display: 'flex', alignItems: 'center', gap: 12, fontSize: 30, fontWeight: 600}}><span style={{width: 26, height: 8, borderRadius: 4, background: tones[k % 2]}} />{s.label}</div>)}</div>
      <Source data={data} />
    </div>
  );
};

const Checklist: React.FC<P> = ({data}) => (
  <div style={{display: 'flex', flexDirection: 'column', gap: 22}}>
    {(data.items ?? []).map((t: string, i: number) => (
      <div key={i} style={{display: 'flex', alignItems: 'center', gap: 30, padding: '28px 34px', borderRadius: 22, border: `2px solid ${LINE}`, background: SOFT}}>
        <svg width="60" height="60" viewBox="0 0 60 60" style={{flex: 'none'}}><rect x="3" y="3" width="54" height="54" rx="14" fill={`${GREEN}1F`} stroke={GREEN} strokeWidth="4" /><path d="M16 31 L26 41 L45 20" stroke={GREEN} strokeWidth="6" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
        <div style={{fontSize: 42, fontWeight: 600, lineHeight: 1.22}}>{t}</div>
      </div>))}
  </div>
);

const Timeline: React.FC<P> = ({data, accent}) => {
  const steps: {head: string; sub?: string}[] = data.steps ?? [];
  return (
    <div style={{position: 'relative', paddingLeft: 12}}>
      <div style={{position: 'absolute', left: 31, top: 20, bottom: 70, width: 6, borderRadius: 3, background: LINE}} />
      {steps.map((s, i) => (
        <div key={i} style={{position: 'relative', display: 'flex', gap: 34, marginBottom: 40}}>
          <div style={{width: 44, height: 44, borderRadius: '50%', background: '#fff', border: `8px solid ${i === steps.length - 1 ? accent : '#9AA3B2'}`, boxSizing: 'border-box', flex: 'none', marginTop: 4}} />
          <div><div style={{fontSize: 46, fontWeight: 800, lineHeight: 1.15}}>{s.head}</div>{s.sub ? <div style={{fontSize: 34, color: MUTE, marginTop: 6, lineHeight: 1.3}}>{s.sub}</div> : null}</div>
        </div>))}
    </div>
  );
};

const Ring: React.FC<P> = ({data, accent}) => {
  const R = 190, circ = 2 * Math.PI * R, v = Math.max(0, Math.min(100, Number(data.value))) / 100;
  return (
    <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center'}}>
      <div style={{position: 'relative', width: 480, height: 480}}>
        <svg width="480" height="480" viewBox="0 0 480 480" style={{transform: 'rotate(-90deg)'}}><circle cx="240" cy="240" r={R} stroke="#EEF0F5" strokeWidth="46" fill="none" /><circle cx="240" cy="240" r={R} stroke={accent} strokeWidth="46" fill="none" strokeLinecap="round" strokeDasharray={circ} strokeDashoffset={circ * (1 - v)} /></svg>
        <div style={{position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 130, fontWeight: 800, color: accent, letterSpacing: -3}}>{Math.round(Number(data.value))}<span style={{fontSize: 60, marginLeft: 6}}>%</span></div>
      </div>
      <div style={{fontSize: 44, fontWeight: 600, textAlign: 'center', lineHeight: 1.25, marginTop: 30}}>{data.label}</div>
      <Source data={data} />
    </div>
  );
};

const Strike: React.FC<P> = ({data, accent}) => (
  <div style={{textAlign: 'center', padding: '10px 0'}}>
    <div style={{display: 'inline-block', position: 'relative', fontSize: 120, fontWeight: 800, letterSpacing: -2, color: MUTE}}>{data.wrong}<div style={{position: 'absolute', left: -10, right: -10, top: '54%', height: 12, background: RED, borderRadius: 6}} /></div>
    <div style={{marginTop: 34}}><span style={{display: 'inline-block', fontSize: 120, fontWeight: 800, letterSpacing: -2, color: accent, borderBottom: `12px solid ${accent}`, lineHeight: 1.1}}>{data.right}</span></div>
    {data.rest ? <div style={{marginTop: 44, fontSize: 44, fontWeight: 600, color: INK}}>{data.rest}</div> : null}
  </div>
);

export const FIGURES: Record<string, React.FC<P>> = {compare: Compare, bars: Bars, stat: Stat, chat: Chat, flow: Flow, chart: Chart, checklist: Checklist, timeline: Timeline, ring: Ring, strike: Strike};

export const BlogFigure: React.FC<FigureProps> = (p) => {
  const F = FIGURES[p.treatment], accent = ACCENTS[p.palette ?? 'midnight'] ?? ACCENTS.midnight;
  return (
    <AbsoluteFill style={{background: '#fff'}}>
      {F ? <Frame title={p.text} accent={accent}><F data={p.data} accent={accent} /></Frame> : null}
    </AbsoluteFill>
  );
};

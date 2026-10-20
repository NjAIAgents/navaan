import React from 'react';
import {Easing, interpolate} from 'remotion';
import {CLAMP, COOL, GOLD, GREEN, INK, Provenance, RED, SANS, SceneProps, clock, plain, pop, shadow} from './common';

// Scene treatments (NAV-130): what a beat of an Aha-lorithm short can show instead of a picture. Each draws from its beat's `data` only, so the same component serves any short;
// the plan (visual_plan.json) says which one a beat gets and what it says. The names here are mirrored in scripts/visuals_plan.py (a test keeps the two lists equal).

// ---------- hook: the words come in one by one as they are spoken, the *marked* ones in the accent colour
const Hook: React.FC<SceneProps> = ({text, local, span, accent, color}) => {
  const words = text.split(/\s+/).filter(Boolean), total = words.reduce((n, w) => n + plain(w).length, 0) || 1, over = Math.min(2.2, span * 0.7);
  let acc = 0;
  return (
    <div style={{position: 'absolute', left: 100, right: 100, top: Math.round(1920 * 0.3), height: Math.round(1920 * 0.28), display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'center', gap: '10px 26px', textAlign: 'center'}}>
      {words.map((w, i) => {
        const at = 0.05 + over * (acc / total); acc += plain(w).length;
        const k = interpolate(local, [at, at + 0.38], [0, 1], {easing: pop, ...CLAMP});
        const hot = w.startsWith('*') || w.endsWith('*');
        return <span key={i} style={{fontFamily: SANS, fontSize: 118, fontWeight: 800, letterSpacing: -1, lineHeight: 1.05, color: hot ? accent : color, textShadow: shadow, display: 'inline-block',
          opacity: Math.min(1, k * 1.6), transform: `translateY(${(1 - k) * 48}px) scale(${0.7 + 0.3 * k})`}}>{plain(w)}</span>;
      })}
    </div>
  );
};

// ---------- compare: two panels slide in, a sign lands between them
const Compare: React.FC<SceneProps> = ({data, local, span, accent, color}) => {
  const {ramp} = clock(local, span);
  const a = ramp(0.2, 0.8), b = ramp(0.55, 1.15), sign = ramp(0.9, 1.3, pop);
  const panel = (p: {title: string; text: string}, tone: string, k: number, from: number) => (
    <div style={{height: 330, borderRadius: 44, border: `3px solid ${tone}88`, background: 'rgba(8,12,22,0.78)', boxShadow: `0 0 60px ${tone}22`, padding: '34px 54px', display: 'flex', flexDirection: 'column', justifyContent: 'center', opacity: k, transform: `translateX(${(1 - k) * from}px)`}}>
      <div style={{fontFamily: SANS, fontSize: 40, fontWeight: 700, letterSpacing: 6, textTransform: 'uppercase', color: tone}}>{p.title}</div>
      <div style={{fontFamily: SANS, fontSize: 78, fontWeight: 800, lineHeight: 1.05, marginTop: 14, color}}>{p.text}</div>
    </div>
  );
  return (
    <div style={{position: 'absolute', left: 80, right: 80, top: Math.round(1920 * 0.36), display: 'flex', flexDirection: 'column'}}>
      {panel(data.left, accent, a, -520)}
      <div style={{height: 110, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: SANS, fontSize: 112, fontWeight: 800, color, opacity: sign, transform: `scale(${0.4 + 0.6 * sign})`}}>{data.sign ?? '≠'}</div>
      {panel(data.right, COOL, b, 520)}
    </div>
  );
};

// ---------- bars: rows fill one after another (an illustration of "more" and "less", never a measurement)
const Bars: React.FC<SceneProps> = ({data, local, span, accent, color}) => {
  const {s} = clock(local, span);
  return (
    <div style={{position: 'absolute', left: 100, right: 100, top: Math.round(1920 * 0.38), display: 'flex', flexDirection: 'column', gap: 70}}>
      {(data.rows as {label: string; fill: number}[]).map((r, i) => {
        const k = interpolate(s, [0.3 + i * 0.45, 1.3 + i * 0.45], [0, 1], {easing: Easing.bezier(0.16, 1, 0.3, 1), ...CLAMP}), tone = i === 0 ? accent : COOL;
        return (
          <div key={i} style={{opacity: Math.min(1, k * 3)}}>
            <div style={{fontFamily: SANS, fontSize: 56, fontWeight: 700, color, marginBottom: 20, textShadow: shadow}}>{r.label}</div>
            <div style={{height: 44, borderRadius: 22, background: 'rgba(255,255,255,0.14)', overflow: 'hidden'}}>
              <div style={{height: '100%', width: `${Math.max(0, Math.min(1, r.fill)) * k * 100}%`, borderRadius: 22, background: `linear-gradient(90deg, ${tone}, ${tone}cc)`, boxShadow: `0 0 28px ${tone}88`}} />
            </div>
          </div>
        );
      })}
      <Provenance data={data} illustration style={{marginTop: 10}} />
    </div>
  );
};

// ---------- stat: one number counts up
const Stat: React.FC<SceneProps> = ({data, local, span, accent, color}) => {
  const {ramp} = clock(local, span);
  const k = ramp(0.3, 1.9, Easing.bezier(0.16, 1, 0.3, 1)), from = data.from ?? 0, n = from + (data.value - from) * k;
  const dec = data.decimals ?? 0, text = n.toLocaleString('en-US', {minimumFractionDigits: dec, maximumFractionDigits: dec});
  return (
    <div style={{position: 'absolute', left: 80, right: 80, top: Math.round(1920 * 0.34), textAlign: 'center', opacity: ramp(0.1, 0.6)}}>
      <div style={{fontFamily: SANS, fontWeight: 800, fontSize: 260, lineHeight: 1, letterSpacing: -4, color: accent, textShadow: `0 0 70px ${accent}55, ${shadow}`}}>{text}<span style={{fontSize: 110, marginLeft: 14}}>{data.unit ?? ''}</span></div>
      <div style={{fontFamily: SANS, fontSize: 62, fontWeight: 700, color, marginTop: 28, textShadow: shadow}}>{data.label}</div>
      <Provenance data={data} style={{marginTop: 34}} />
    </div>
  );
};

// ---------- chat: a question, typing dots, an answer typed out, then two tags
const Chat: React.FC<SceneProps> = ({data, local, span, t}) => {
  const {s, ramp} = clock(local, span);
  const answer = String(data.answer), typed = answer.slice(0, Math.floor(interpolate(s, [2.3, 5.0], [0, answer.length], CLAMP)));
  const tags: string[] = data.tags ?? [];
  return (
    <div style={{position: 'absolute', left: 80, right: 80, top: 520, display: 'flex', flexDirection: 'column', gap: 36, fontFamily: SANS}}>
      <div style={{alignSelf: 'flex-end', maxWidth: 780, padding: '34px 44px', borderRadius: '44px 44px 8px 44px', background: `linear-gradient(135deg, ${COOL}, #3d6fd6)`, color: '#fff', fontSize: 52, fontWeight: 600,
        opacity: ramp(0.4, 0.8), transform: `translateY(${(1 - ramp(0.4, 0.9)) * 40}px) scale(${0.9 + 0.1 * ramp(0.4, 0.9, pop)})`}}>{data.question}</div>
      {s > 1.3 && s < 2.3 ? (
        <div style={{alignSelf: 'flex-start', padding: '30px 40px', borderRadius: '44px 44px 44px 8px', background: 'rgba(255,255,255,0.1)', display: 'flex', gap: 16}}>
          {[0, 1, 2].map((i) => <div key={i} style={{width: 22, height: 22, borderRadius: '50%', background: INK, opacity: 0.35 + 0.65 * Math.max(0, Math.sin(t * 9 - i * 0.9)), transform: `translateY(${-10 * Math.max(0, Math.sin(t * 9 - i * 0.9))}px)`}} />)}
        </div>) : null}
      {s >= 2.3 ? (
        <div style={{alignSelf: 'flex-start', maxWidth: 800, padding: '34px 44px', borderRadius: '44px 44px 44px 8px', background: 'rgba(255,255,255,0.1)', border: '2px solid rgba(255,255,255,0.14)', color: INK, fontSize: 52, fontWeight: 500, lineHeight: 1.25, minHeight: 90}}>
          {typed}<span style={{opacity: Math.floor(t * 2.5) % 2 ? 0 : 1, color: GOLD}}>|</span>
        </div>) : null}
      <div style={{display: 'flex', gap: 22, marginTop: 14, alignSelf: 'flex-start'}}>
        {tags.slice(0, 2).map((tag, i) => {
          const tone = i === 0 ? GOLD : COOL, at = 5.2 + i * 0.7;
          return <div key={i} style={{padding: '16px 34px', borderRadius: 40, background: `${tone}26`, border: `2px solid ${tone}`, color: tone, fontSize: 40, fontWeight: 700, opacity: ramp(at, at + 0.4), transform: `scale(${0.6 + 0.4 * ramp(at, at + 0.5, pop)})`}}>{tag}</div>;
        })}
      </div>
    </div>
  );
};

// ---------- flow: boxes appear in turn, the arrows draw themselves, the last box is the point
const Flow: React.FC<SceneProps> = ({data, local, span, t}) => {
  const {ramp} = clock(local, span), nodes: string[] = data.nodes, step = 4.6 / nodes.length;
  return (
    <div style={{position: 'absolute', left: 140, right: 140, top: 430, display: 'flex', flexDirection: 'column', alignItems: 'center', fontFamily: SANS}}>
      {nodes.map((n, i) => {
        const k = ramp(0.5 + i * step, 1.1 + i * step, pop), arrow = ramp(1.3 + i * step, 1.9 + i * step), last = i === nodes.length - 1, tone = last ? GOLD : COOL;
        return (
          <React.Fragment key={i}>
            <div style={{width: '100%', padding: '40px 30px', textAlign: 'center', borderRadius: 40, border: `3px solid ${tone}`, background: last ? `${GOLD}1f` : 'rgba(8,12,22,0.8)', boxShadow: last ? `0 0 ${50 + 30 * Math.sin(t * 5)}px ${GOLD}66` : `0 0 40px ${COOL}22`,
              fontSize: 60, fontWeight: 800, color: last ? GOLD : INK, opacity: k, transform: `scale(${0.8 + 0.2 * k})`}}>{n}</div>
            {!last ? (
              <svg width="60" height="120" viewBox="0 0 60 120" style={{margin: '6px 0'}}>
                <path d="M30 4 L30 100" stroke={COOL} strokeWidth="6" strokeLinecap="round" fill="none" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - arrow} />
                <path d="M12 82 L30 106 L48 82" stroke={COOL} strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" fill="none" opacity={arrow > 0.85 ? 1 : 0} />
              </svg>) : null}
          </React.Fragment>
        );
      })}
    </div>
  );
};

// ---------- chart: one or two lines draw themselves, the points pop (values are 0 to 1 heights; the figures need a source or the sample label)
const Chart: React.FC<SceneProps> = ({data, local, span}) => {
  const {ramp} = clock(local, span);
  const W = 880, H = 640, series: {label: string; points: number[]}[] = data.series, n = Math.max(...series.map((s) => s.points.length)), labels: string[] = data.xlabels ?? [];
  const xy = (v: number, i: number) => [60 + (i * (W - 120)) / Math.max(1, n - 1), H - 60 - v * (H - 140)] as const;
  const path = (a: number[]) => a.map((v, i) => `${i ? 'L' : 'M'}${xy(v, i)[0]} ${xy(v, i)[1]}`).join(' ');
  const tones = [GOLD, COOL], first = series[0].points;
  return (
    <div style={{position: 'absolute', left: 100, top: 500, fontFamily: SANS}}>
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`}>
        <defs><linearGradient id="fillg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={GOLD} stopOpacity="0.35" /><stop offset="1" stopColor={GOLD} stopOpacity="0" /></linearGradient></defs>
        {[0, 1, 2, 3].map((g) => <line key={g} x1="60" x2={W - 60} y1={H - 60 - (g * (H - 140)) / 3} y2={H - 60 - (g * (H - 140)) / 3} stroke="rgba(255,255,255,0.14)" strokeWidth="2" strokeDasharray="8 10" opacity={ramp(0.2, 0.8)} />)}
        <path d={`${path(first)} L${xy(0, first.length - 1)[0]} ${H - 60} L${xy(0, 0)[0]} ${H - 60} Z`} fill="url(#fillg)" opacity={ramp(0.8, 4.2, Easing.inOut(Easing.cubic))} />
        {series.slice(0, 2).map((sr, si) => {
          const k = ramp(0.8 + si * 0.6, 4.2 + si * 0.6, Easing.inOut(Easing.cubic));
          return <path key={si} d={path(sr.points)} stroke={tones[si]} strokeWidth={si ? 7 : 10} fill="none" strokeLinecap="round" strokeLinejoin="round" pathLength={1} style={{strokeDasharray: 1, strokeDashoffset: 1 - k, filter: si ? undefined : `drop-shadow(0 0 14px ${GOLD}aa)`}} opacity={si ? 0.9 : 1} />;
        })}
        {first.map((v, i) => { const [x, y] = xy(v, i); const p = ramp(0.8 + (i / Math.max(1, n - 1)) * 3.4, 1.1 + (i / Math.max(1, n - 1)) * 3.4, pop); return <circle key={i} cx={x} cy={y} r={14 * p} fill="#0a0f1c" stroke={GOLD} strokeWidth="6" />; })}
        {first.map((_, i) => <text key={i} x={xy(0, i)[0]} y={H - 14} fill="rgba(255,255,255,0.6)" fontSize="30" textAnchor="middle" fontFamily={SANS}>{labels[i] ?? `${i + 1}`}</text>)}
      </svg>
      <div style={{display: 'flex', gap: 40, justifyContent: 'center', marginTop: 24, fontSize: 38, fontWeight: 700, opacity: ramp(4.6, 5.2)}}>
        {series.slice(0, 2).map((sr, i) => <span key={i} style={{color: tones[i]}}>● {sr.label}</span>)}
      </div>
      <Provenance data={data} style={{marginTop: 34, opacity: ramp(0.6, 1.2)}} />
    </div>
  );
};

// ---------- checklist: boxes fill and ticks are drawn
const Checklist: React.FC<SceneProps> = ({data, local, span}) => {
  const {ramp} = clock(local, span), items: string[] = data.items, step = 4.2 / items.length;
  return (
    <div style={{position: 'absolute', left: 110, right: 110, top: 520, display: 'flex', flexDirection: 'column', gap: 56, fontFamily: SANS}}>
      {items.map((s, i) => {
        const at = 0.6 + i * step, row = ramp(at, at + 0.6), tick = ramp(at + 0.7, at + 1.15, Easing.out(Easing.cubic)), fill = ramp(at + 0.7, at + 1.0);
        return (
          <div key={i} style={{display: 'flex', alignItems: 'center', gap: 44, padding: '38px 44px', borderRadius: 40, background: 'rgba(8,12,22,0.72)', border: `2px solid ${fill > 0.5 ? GREEN + '99' : 'rgba(255,255,255,0.16)'}`, opacity: row, transform: `translateX(${(1 - row) * 160}px)`}}>
            <svg width="96" height="96" viewBox="0 0 96 96">
              <rect x="6" y="6" width="84" height="84" rx="22" fill={`rgba(91,214,160,${0.22 * fill})`} stroke={fill > 0.1 ? GREEN : 'rgba(255,255,255,0.4)'} strokeWidth="6" />
              <path d="M26 50 L42 66 L72 32" stroke={GREEN} strokeWidth="10" strokeLinecap="round" strokeLinejoin="round" fill="none" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - tick} />
            </svg>
            <div style={{fontSize: 66, fontWeight: 800, color: INK, textShadow: shadow}}>{s}</div>
          </div>
        );
      })}
    </div>
  );
};

// ---------- timeline: the line grows, the points pop, the words slide in
const Timeline: React.FC<SceneProps> = ({data, local, span}) => {
  const {ramp} = clock(local, span), steps: {head: string; sub?: string}[] = data.steps, gap = Math.min(250, 750 / Math.max(1, steps.length - 1)), grow = ramp(0.4, 5.2, Easing.inOut(Easing.quad));
  return (
    <div style={{position: 'absolute', left: 150, right: 90, top: 500, height: 900, fontFamily: SANS}}>
      <div style={{position: 'absolute', left: 36, top: 24, width: 8, height: (steps.length - 1) * gap * grow + 20, borderRadius: 4, background: `linear-gradient(180deg, ${COOL}, ${GOLD})`, boxShadow: `0 0 24px ${COOL}66`}} />
      {steps.map((st, i) => {
        const at = 0.4 + (i / Math.max(1, steps.length - 1)) * 4.4, k = ramp(at, at + 0.5, pop), w = ramp(at + 0.15, at + 0.8), hot = i === steps.length - 1;
        return (
          <div key={i} style={{position: 'absolute', left: 0, top: i * gap, display: 'flex', alignItems: 'center', gap: 56}}>
            <div style={{width: 80, height: 80, borderRadius: '50%', background: '#0a0f1c', border: `8px solid ${hot ? GOLD : COOL}`, boxShadow: `0 0 ${hot ? 40 : 20}px ${hot ? GOLD : COOL}88`, transform: `scale(${k})`}} />
            <div style={{opacity: w, transform: `translateX(${(1 - w) * 120}px)`}}>
              <div style={{fontSize: 78, fontWeight: 800, color: hot ? GOLD : INK, textShadow: shadow}}>{st.head}</div>
              {st.sub ? <div style={{fontSize: 46, color: 'rgba(255,255,255,0.78)', marginTop: 6}}>{st.sub}</div> : null}
            </div>
          </div>
        );
      })}
    </div>
  );
};

// ---------- ring: a progress ring with a counting percentage
const Ring: React.FC<SceneProps> = ({data, local, span, t}) => {
  const {ramp} = clock(local, span), k = ramp(0.6, 3.6, Easing.out(Easing.cubic)), R = 330, circ = 2 * Math.PI * R, v = Math.max(0, Math.min(100, Number(data.value))) / 100;
  return (
    <div style={{position: 'absolute', left: 0, right: 0, top: 480, display: 'flex', flexDirection: 'column', alignItems: 'center', fontFamily: SANS}}>
      <div style={{position: 'relative', width: 820, height: 820}}>
        <svg width="820" height="820" viewBox="0 0 820 820" style={{transform: 'rotate(-90deg)'}}>
          <circle cx="410" cy="410" r={R} stroke="rgba(255,255,255,0.12)" strokeWidth="44" fill="none" />
          {Array.from({length: 60}).map((_, i) => <line key={i} x1={410 + (R + 52) * Math.cos((i / 60) * 2 * Math.PI)} y1={410 + (R + 52) * Math.sin((i / 60) * 2 * Math.PI)} x2={410 + (R + 66) * Math.cos((i / 60) * 2 * Math.PI)} y2={410 + (R + 66) * Math.sin((i / 60) * 2 * Math.PI)} stroke={i / 60 < v * k ? GOLD : 'rgba(255,255,255,0.2)'} strokeWidth="4" />)}
          <circle cx="410" cy="410" r={R} stroke={GOLD} strokeWidth="44" strokeLinecap="round" fill="none" strokeDasharray={circ} strokeDashoffset={circ * (1 - v * k)} style={{filter: `drop-shadow(0 0 22px ${GOLD}aa)`}} />
        </svg>
        <div style={{position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center'}}>
          <div style={{fontSize: 230, fontWeight: 800, color: INK, letterSpacing: -4, textShadow: shadow}}>{Math.round(v * 100 * k)}<span style={{fontSize: 100, color: GOLD}}>%</span></div>
          <div style={{fontSize: 46, fontWeight: 700, color: 'rgba(255,255,255,0.8)', marginTop: 4, opacity: ramp(2.2, 2.9)}}>{data.label}</div>
        </div>
      </div>
      <Provenance data={data} style={{marginTop: 20, opacity: ramp(0.6, 1.2) * (0.8 + 0.2 * Math.sin(t * 4))}} />
    </div>
  );
};

// ---------- strike: a word is crossed out, the better one is underlined
const Strike: React.FC<SceneProps> = ({data, local, span}) => {
  const {ramp} = clock(local, span);
  const w1 = ramp(0.4, 1.0, pop), cross = ramp(1.5, 2.1, Easing.inOut(Easing.cubic)), w2 = ramp(2.4, 3.1, pop), under = ramp(3.3, 4.0, Easing.inOut(Easing.cubic)), rest = ramp(4.4, 5.2);
  return (
    <div style={{position: 'absolute', left: 60, right: 60, top: 560, textAlign: 'center', fontFamily: SANS}}>
      <div style={{position: 'relative', display: 'inline-block', whiteSpace: 'nowrap', fontSize: 150, fontWeight: 800, letterSpacing: -3, color: cross > 0.2 ? 'rgba(244,247,255,0.45)' : INK, opacity: w1, transform: `scale(${0.7 + 0.3 * w1})`, textShadow: shadow}}>
        {data.wrong}
        <div style={{position: 'absolute', left: -14, top: '54%', height: 16, width: `${(100 * cross) + (cross ? 3 : 0)}%`, background: RED, borderRadius: 8, transform: 'rotate(-3deg)', transformOrigin: 'left', boxShadow: `0 0 28px ${RED}88`}} />
      </div>
      <div style={{position: 'relative', display: 'inline-block', whiteSpace: 'nowrap', marginTop: 70, fontSize: 170, fontWeight: 800, letterSpacing: -3, color: GOLD, opacity: w2, transform: `translateY(${(1 - w2) * 90}px) scale(${0.8 + 0.2 * w2})`, textShadow: `0 0 70px ${GOLD}55, ${shadow}`}}>
        {data.right}
        <div style={{position: 'absolute', left: 0, bottom: -26, height: 14, width: `${under * 100}%`, background: GOLD, borderRadius: 7, boxShadow: `0 0 26px ${GOLD}aa`}} />
      </div>
      {data.rest ? <div style={{marginTop: 110, fontSize: 60, fontWeight: 600, color: 'rgba(255,255,255,0.85)', opacity: rest, transform: `translateY(${(1 - rest) * 30}px)`}}>{data.rest}</div> : null}
    </div>
  );
};

// The registry. `backdrop`: the treatment brings its own dark scene (the hook stays over the beat's picture); `title`: the beat's text is set above it as a caption.
export const SCENES: Record<string, {C: React.FC<SceneProps>; backdrop: boolean; title: boolean}> = {
  hook: {C: Hook, backdrop: false, title: false},
  compare: {C: Compare, backdrop: true, title: true},
  bars: {C: Bars, backdrop: true, title: true},
  stat: {C: Stat, backdrop: true, title: true},
  chat: {C: Chat, backdrop: true, title: true},
  flow: {C: Flow, backdrop: true, title: true},
  chart: {C: Chart, backdrop: true, title: true},
  checklist: {C: Checklist, backdrop: true, title: true},
  timeline: {C: Timeline, backdrop: true, title: true},
  ring: {C: Ring, backdrop: true, title: true},
  strike: {C: Strike, backdrop: true, title: false},
};

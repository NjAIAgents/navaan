import React from 'react';
import {Composition} from 'remotion';
import {Quote, QuoteProps, defaultProps} from './Quote';
import {Lyrics, LyricsProps, lyricsDefaults} from './Lyrics';
import {Shots, ShotsProps, shotsDefaults} from './Shots';

// The renderer passes the song folder's timing.json as props. Duration, size and fps all come from it,
// so one composition serves every inspiration short.
const lyricsMeta = ({props}: {props: Record<string, unknown>}) => {
  const p = props as unknown as LyricsProps;
  return {durationInFrames: Math.max(1, Math.round(p.duration * p.fps)), fps: p.fps, width: p.width, height: p.height};
};

// Reel cut from the best part of a song (clip_reel.py): lyric lines timed to the music, end card, plus a still for the Reel cover.
export const Root: React.FC = () => (
  <>
    <Composition id="Lyrics" component={Lyrics} width={1080} height={1920} fps={30} durationInFrames={300} defaultProps={lyricsDefaults} calculateMetadata={lyricsMeta} />
    <Composition id="Shots" component={Shots} width={1920} height={1080} fps={24} durationInFrames={240} defaultProps={shotsDefaults}
      calculateMetadata={({props}) => { const p = props as unknown as ShotsProps; return {durationInFrames: Math.max(1, Math.round(p.duration * p.fps)), fps: p.fps, width: p.width, height: p.height}; }} />
    <Composition id="LyricsCover" component={Lyrics} width={1080} height={1920} fps={30} durationInFrames={30} defaultProps={{...lyricsDefaults, mode: 'cover' as const}} calculateMetadata={lyricsMeta} />
    <Composition
      id="Quote"
      component={Quote}
      width={1080}
      height={1920}
      fps={30}
      durationInFrames={300}
      defaultProps={defaultProps}
      calculateMetadata={({props}) => {
        const p = props as QuoteProps;
        return {durationInFrames: Math.max(1, Math.round(p.duration * p.fps)), fps: p.fps, width: p.width, height: p.height};
      }}
    />
  </>
);

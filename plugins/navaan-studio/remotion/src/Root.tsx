import React from 'react';
import {Composition} from 'remotion';
import {Quote, QuoteProps, defaultProps} from './Quote';

// The renderer passes the song folder's timing.json as props. Duration, size and fps all come from it,
// so one composition serves every inspiration short.
export const Root: React.FC = () => (
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
      return {
        durationInFrames: Math.max(1, Math.round(p.duration * p.fps)),
        fps: p.fps,
        width: p.width,
        height: p.height,
      };
    }}
  />
);

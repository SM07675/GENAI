import React from 'react';
import { Observation } from '../../store/taskStore';

export interface ObservationCardProps {
  observation: Observation;
}

export const ObservationCard: React.FC<ObservationCardProps> = ({ observation }) => {
  return (
    <div className="p-3 rounded-lg border border-cyan-500/20 bg-cyan-950/10 backdrop-blur-md text-xs space-y-1.5 transition-all hover:border-cyan-500/40">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <span className="text-cyan-400">👁</span>
          <span className="font-mono text-[11px] font-semibold text-cyan-300 uppercase tracking-wide">
            {observation.source}
          </span>
        </div>
        <span className="text-[10px] text-zinc-500 font-mono">
          {new Date(observation.timestamp).toLocaleTimeString()}
        </span>
      </div>
      <p className="text-zinc-200 text-[12px] leading-relaxed whitespace-pre-wrap">
        {observation.content}
      </p>
    </div>
  );
};

import { Suspense } from 'react';
import { Html } from '@react-three/drei';
import { CharacterModel } from './CharacterModel';
import { AssistantState } from '../../types';

interface CharacterContainerProps {
  assistantState: AssistantState;
  onClipsDetected?: (clips: string[]) => void;
}

function ModelLoader() {
  return (
    <Html center>
      <div className="flex flex-col items-center justify-center p-6 rounded-2xl bg-slate-950/80 backdrop-blur-xl border border-cyan-500/20 shadow-2xl shadow-cyan-500/10">
        <div className="relative flex items-center justify-center w-16 h-16 mb-4">
          <div className="absolute inset-0 rounded-full border-2 border-cyan-500/20 border-t-cyan-400 animate-spin" />
          <div className="w-8 h-8 rounded-full bg-cyan-500/20 animate-pulse flex items-center justify-center">
            <div className="w-3 h-3 rounded-full bg-cyan-400" />
          </div>
        </div>
        <span className="text-sm font-medium tracking-wider text-cyan-200/90 uppercase">
          Initializing Entity...
        </span>
      </div>
    </Html>
  );
}

export function CharacterContainer({ assistantState, onClipsDetected }: CharacterContainerProps) {
  return (
    <Suspense fallback={<ModelLoader />}>
      <CharacterModel
        modelPath="/model.glb"
        assistantState={assistantState}
        onClipsDetected={onClipsDetected}
      />
    </Suspense>
  );
}

import { StandardAnimationName } from '../types';

/**
 * Normalizes string for easy matching
 */
const cleanName = (str: string): string => str.toLowerCase().replace(/[^a-z0-9]/g, '');

/**
 * Intelligent animation clip mapper.
 * Matches requested state (e.g. 'idle', 'speaking', 'processing') against available clip names in the GLB.
 */
export function mapStateToClipName(
  requestedState: string,
  availableClips: string[]
): string | null {
  if (!availableClips || availableClips.length === 0) return null;

  const target = cleanName(requestedState);

  // 1. Direct exact match
  const exactMatch = availableClips.find(clip => cleanName(clip) === target);
  if (exactMatch) return exactMatch;

  // 2. Substring / Includes match
  const includeMatch = availableClips.find(clip => {
    const cleaned = cleanName(clip);
    return cleaned.includes(target) || target.includes(cleaned);
  });
  if (includeMatch) return includeMatch;

  // 3. Synonym / Keyword fallback rules for Genie GLB clips
  const synonyms: Record<string, string[]> = {
    idle: ['idle', 'wait', 'stand', 'rest', 'breathe', 'loop', 'default', 'pose'],
    speaking: ['talk_standing', 'talk_sitting', 'talking', 'speak', 'mouth', 'say', 'chat', 'discuss'],
    talking: ['talk_standing', 'talk_sitting', 'talking', 'speak', 'mouth', 'say'],
    processing: ['talk_sitting', 'sneakwalk', 'idle', 'ponder', 'wonder', 'confused'],
    thinking: ['talk_sitting', 'sneakwalk', 'idle', 'ponder', 'wonder'],
    listening: ['idle', 'talk_sitting', 'hear', 'attentive', 'look', 'nod'],
    recording: ['idle', 'talk_sitting'],
    waking: ['idle', 'talk_standing'],
    error: ['sneakwalk', 'idle'],
    success: ['dance', 'victory', 'cheer', 'happy', 'joy'],
    dance: ['dance', 'groove', 'spin', 'boogie'],
    walk: ['walk', 'sneakwalk'],
  };

  const keywords = synonyms[target] || [];
  for (const kw of keywords) {
    const match = availableClips.find(clip => cleanName(clip).includes(kw));
    if (match) return match;
  }

  // 4. Default strictly to an 'Idle' clip if available, NEVER arbitrary availableClips[0] (which is Dance)
  const idleMatch = availableClips.find(clip => cleanName(clip).includes('idle'));
  if (idleMatch) return idleMatch;

  return availableClips[0];
}

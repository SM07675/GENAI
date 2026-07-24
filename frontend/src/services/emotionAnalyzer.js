/**
 * emotionAnalyzer — analyzes user and assistant text to detect emotional context.
 * Returns an EmotionCommand or null if no pattern matches.
 */
import { ROBOT_EMOTIONS } from '../types/robotEmotion.js';

const USER_PATTERNS = [
  {
    patterns: [/thank(?:s| you)/i, /you'?re amazing/i, /you are amazing/i, /(?:i )?love you/i, /appreciate/i, /you'?re the best/i],
    emotion: ROBOT_EMOTIONS.LOVING, intensity: 0.9, duration: 3500,
  },
  {
    patterns: [/that worked/i, /it works/i, /perfect(?:ly)?/i, /great job/i, /good job/i, /well done/i, /you did it/i, /nailed it/i, /nice work/i],
    emotion: ROBOT_EMOTIONS.SUCCESS, intensity: 0.85, duration: 3000,
  },
  {
    patterns: [/wow\b/i, /amazing\b/i, /incredible\b/i, /holy/i, /omg\b/i, /oh my/i, /no way/i, /!{2,}/],
    emotion: ROBOT_EMOTIONS.EXCITED, intensity: 0.9, duration: 2500,
  },
  {
    patterns: [/really\?/i, /seriously\?/i, /what\?+/i, /is that true/i, /are you sure\?/i],
    emotion: ROBOT_EMOTIONS.SURPRISED, intensity: 0.8, duration: 2000,
  },
  {
    patterns: [/\bhappy\b/i, /\bgreat\b/i, /love it\b/i, /brilliant\b/i, /\bsweet\b/i, /\bawesome\b/i],
    emotion: ROBOT_EMOTIONS.HAPPY, intensity: 0.7, duration: 3000,
  },
  {
    patterns: [/i(?:'m| am) sad\b/i, /feel(?:ing)? (?:bad|sad|down|terrible|depressed)/i, /\bawful\b/i, /\bhorrible\b/i],
    emotion: ROBOT_EMOTIONS.SAD, intensity: 0.6, duration: 4000,
  },
  {
    patterns: [/i don'?t understand/i, /what do you mean/i, /i'?m confused/i, /makes no sense/i, /huh\?/i, /\?\?+/],
    emotion: ROBOT_EMOTIONS.CONFUSED, intensity: 0.7, duration: 3000,
  },
];

const ASSISTANT_PATTERNS = [
  {
    patterns: [/\bdone[!.]?\s*$/i, /completed successfully/i, /all set[!.]?\s*$/i, /there you go/i, /finished[!.]?\s*$/i],
    emotion: ROBOT_EMOTIONS.SUCCESS, intensity: 0.8, duration: 2500,
  },
  {
    patterns: [/error/i, /failed/i, /(?:i'?m|i am) sorry/i, /unable to/i, /can'?t (?:do|find|access)/i, /something went wrong/i],
    emotion: ROBOT_EMOTIONS.WORRIED, intensity: 0.7, duration: 3000,
  },
  {
    patterns: [/happy to help/i, /of course[!,]?/i, /absolutely[!,]?/i, /great choice/i, /wonderful/i, /you'?re welcome/i],
    emotion: ROBOT_EMOTIONS.HAPPY, intensity: 0.7, duration: 3000,
  },
];

/**
 * Analyze text and return an emotion command, or null if no pattern matches.
 * @param {string} text
 * @param {'user'|'assistant'} source
 * @returns {EmotionCommand | null}
 */
export function analyzeTextEmotion(text, source = 'user') {
  if (!text || text.trim().length < 2) return null;
  const patterns = source === 'user' ? USER_PATTERNS : ASSISTANT_PATTERNS;
  for (const entry of patterns) {
    for (const pattern of entry.patterns) {
      if (pattern.test(text)) {
        return {
          emotion: entry.emotion,
          intensity: entry.intensity,
          duration: entry.duration,
          source,
        };
      }
    }
  }
  return null;
}

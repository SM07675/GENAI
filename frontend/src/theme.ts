/**
 * theme.ts — Genie Design System: centralized tokens.
 *
 * Visual identity: calm near-black / warm-neutral surfaces, a single
 * restrained signature accent ("Iris"), and an aurora blend reserved for
 * the Genie Core itself. Color communicates state — it does not decorate
 * every component.
 */

export interface ThemeColors {
  bg: string;
  bgElevated: string;
  surface: string;
  surfaceHover: string;
  surfaceBorder: string;
  text: string;
  textMuted: string;
  textFaint: string;
  iris: string;
  irisSoft: string;
  aurora: string;
  success: string;
  warning: string;
  danger: string;
}

export const LIGHT_THEME: ThemeColors = {
  bg: '#F6F5F3',
  bgElevated: '#FFFFFF',
  surface: 'rgba(255, 255, 255, 0.72)',
  surfaceHover: 'rgba(255, 255, 255, 0.92)',
  surfaceBorder: 'rgba(20, 20, 26, 0.08)',
  text: '#15151B',
  textMuted: '#5B5D68',
  textFaint: '#9A9CA6',
  iris: '#5B46E0',
  irisSoft: 'rgba(91, 70, 224, 0.12)',
  aurora: '#2FB6A3',
  success: '#1F9D6E',
  warning: '#B4740F',
  danger: '#C4432E',
};

export const DARK_THEME: ThemeColors = {
  bg: '#0A0A0D',
  bgElevated: '#111116',
  surface: 'rgba(255, 255, 255, 0.045)',
  surfaceHover: 'rgba(255, 255, 255, 0.08)',
  surfaceBorder: 'rgba(255, 255, 255, 0.08)',
  text: '#F2F2F5',
  textMuted: '#8B8D98',
  textFaint: '#5D5F6B',
  iris: '#7C6CFF',
  irisSoft: 'rgba(124, 108, 255, 0.16)',
  aurora: '#5EE6D0',
  success: '#3ED598',
  warning: '#E0A73B',
  danger: '#EA6B57',
};

export type ThemeMode = 'light' | 'dark' | 'system';

export function getThemeColors(mode: ThemeMode): ThemeColors {
  if (mode === 'light') return LIGHT_THEME;
  if (mode === 'dark') return DARK_THEME;

  if (typeof window !== 'undefined' && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    return DARK_THEME;
  }
  return LIGHT_THEME;
}

/** Spacing scale (px). Everything in the shell aligns to this. */
export const SPACE = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
  xxxl: 48,
} as const;

/** Radius scale — sharp for controls, soft for panels, full for pills/orb. */
export const RADIUS = {
  sm: 8,
  md: 14,
  lg: 20,
  xl: 28,
  full: 999,
} as const;

/** Motion durations (seconds), per the Genie motion system. */
export const MOTION = {
  micro: 0.12,
  standard: 0.28,
  spatial: 0.45,
  hero: 0.7,
} as const;

/** Spring presets for framer-motion, tuned to feel premium, not floaty. */
export const SPRING = {
  snappy: { type: 'spring', stiffness: 420, damping: 32, mass: 0.9 },
  soft: { type: 'spring', stiffness: 220, damping: 26, mass: 1 },
  hero: { type: 'spring', stiffness: 140, damping: 20, mass: 1.1 },
} as const;

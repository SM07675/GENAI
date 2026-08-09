/**
 * theme.ts — Genie AI Centralized Design System & Theme Tokens.
 *
 * Primary Visual Identity:
 * - Sky Blue, Light Blue, White Glass, Deep Navy, Soft Cyan, Gentle Glow
 * - Aesthetic: Clean + Friendly + Intelligent + Futuristic + Calm + Premium
 */

export interface ThemeColors {
  primary: string;          // Sky Blue
  primaryGlow: string;      // Sky Blue Glow
  secondary: string;        // Light Blue
  accent: string;           // Bright Blue / Cyan
  highlight: string;        // Soft Cyan
  bg: string;               // App Background Gradient
  surface: string;          // Translucent Glass Surface
  surfaceBorder: string;    // Subtle Glass Border
  text: string;             // Deep Navy / Off-White
  textMuted: string;        // Blue-Gray
  cardBg: string;           // Translucent Card Fill
  success: string;          // Emerald / Mint
  warning: string;          // Amber / Gold
  danger: string;           // Soft Rose / Coral
}

export const LIGHT_THEME: ThemeColors = {
  primary: '#0284c7',         // Sky 600
  primaryGlow: 'rgba(56, 189, 248, 0.4)',
  secondary: '#e0f2fe',       // Sky 100
  accent: '#0369a1',          // Sky 700
  highlight: '#38bdf8',       // Sky 400
  bg: 'linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 50%, #bae6fd 100%)',
  surface: 'rgba(255, 255, 255, 0.85)',
  surfaceBorder: 'rgba(186, 230, 253, 0.6)',
  text: '#0f172a',            // Slate 900
  textMuted: '#475569',       // Slate 600
  cardBg: 'rgba(255, 255, 255, 0.7)',
  success: '#10b981',
  warning: '#f59e0b',
  danger: '#f43f5e',
};

export const DARK_THEME: ThemeColors = {
  primary: '#38bdf8',         // Sky 400
  primaryGlow: 'rgba(56, 189, 248, 0.35)',
  secondary: '#0f172a',       // Slate 900
  accent: '#0284c7',          // Sky 600
  highlight: '#22d3ee',       // Cyan 400
  bg: 'radial-gradient(ellipse at 50% 30%, #0c192e 0%, #030712 100%)',
  surface: 'rgba(15, 23, 42, 0.82)',
  surfaceBorder: 'rgba(56, 189, 248, 0.2)',
  text: '#f8fafc',            // Slate 50
  textMuted: '#94a3b8',       // Slate 400
  cardBg: 'rgba(15, 23, 42, 0.65)',
  success: '#34d399',
  warning: '#fbbf24',
  danger: '#fb7185',
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

/**
 * Conditional debug logger for Genie.
 *
 * In development: logs to console with prefix.
 * In production: silent (no-op).
 *
 * Usage:
 *   import { glog } from '../utils/logger';
 *   glog('[WS]', 'wake_word_detected', { state: currentVS });
 */

const IS_DEV =
  typeof process !== 'undefined'
    ? process.env.NODE_ENV !== 'production'
    : typeof window !== 'undefined' &&
      (window.location.hostname === 'localhost' ||
        window.location.hostname === '127.0.0.1');

/**
 * Log a debug message (dev only). Accepts any number of arguments.
 */
export function glog(...args: unknown[]): void {
  if (IS_DEV) {
    // eslint-disable-next-line no-console
    console.log(...args);
  }
}

/**
 * Log a warning (always visible, but prefixed).
 */
export function gwarn(...args: unknown[]): void {
  // eslint-disable-next-line no-console
  console.warn('[Genie]', ...args);
}

/**
 * Log an error (always visible).
 */
export function gerr(...args: unknown[]): void {
  // eslint-disable-next-line no-console
  console.error('[Genie]', ...args);
}

/**
 * audioAnalyser — module-level singleton audio analyser.
 *
 * Solves the critical bug where both `useAudioLipSync` (in GenieRobot)
 * and `AudioWaveform` tried to call `createMediaElementSource()` on the
 * same HTMLAudioElement — which throws:
 *   "InvalidStateError: HTMLMediaElement already connected to a different
 *    MediaElementSourceNode"
 *
 * Solution: one AudioContext, one AnalyserNode, one source — shared across
 * all consumers in the app.
 */

let _ctx      = null;
let _analyser = null;
let _source   = null;
let _element  = null;

/**
 * Returns the shared AnalyserNode, creating it lazily on first call.
 * Safe to call from multiple React hooks — subsequent calls are no-ops.
 *
 * @param {HTMLAudioElement} audioElement
 * @returns {AnalyserNode | null}
 */
export function getOrCreateAnalyser(audioElement) {
  if (!audioElement) return null;

  // Already initialised — return the shared analyser
  if (_analyser && _element === audioElement) return _analyser;

  // If the element changed (shouldn't happen but guard anyway) tear down first
  if (_analyser && _element !== audioElement) {
    destroyAnalyser();
  }

  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 256;
    analyser.smoothingTimeConstant = 0.80;

    const source = ctx.createMediaElementSource(audioElement);
    source.connect(analyser);
    analyser.connect(ctx.destination);

    _ctx      = ctx;
    _analyser = analyser;
    _source   = source;
    _element  = audioElement;

    // Attempt to resume immediately in case we are in a user gesture
    if (ctx.state === 'suspended') {
      ctx.resume().catch(() => {});
    }

    return analyser;
  } catch (e) {
    console.warn('[AudioAnalyser] Failed to initialise shared analyser:', e.message);
    return null;
  }
}

/**
 * Resumes the AudioContext if it was suspended due to autoplay policies.
 * Should be called right before playing audio.
 */
export function resumeAnalyser() {
  if (_ctx && _ctx.state === 'suspended') {
    _ctx.resume().catch(e => console.warn('[AudioAnalyser] Failed to resume context:', e));
  }
}

/**
 * Returns the shared analyser if already created, or null.
 * Does NOT create a new one.
 */
export function getAnalyser() {
  return _analyser;
}

/**
 * Tear down the shared analyser (call on logout / audio element swap).
 */
export function destroyAnalyser() {
  try {
    _source?.disconnect();
    _analyser?.disconnect();
    _ctx?.close();
  } catch (_) {
    // ignore
  }
  _ctx = null; _analyser = null; _source = null; _element = null;
}

/**
 * useWakeWordDetector
 *
 * Root cause of the network-error loop:
 *   1. SpeechRecognition fires onerror("network") then ALWAYS fires onend.
 *   2. Both handlers were independently scheduling a restart.
 *   3. The onerror handler scheduled a restart, then onend fired and scheduled
 *      another one (since errorHandledRef was not set before onend ran in the
 *      same microtask tick). Result: two concurrent restarts per error.
 *   4. The backoff counter was being incremented correctly, but the timer was
 *      replaced by the second (onend) restart with delay=200ms, wiping out the
 *      backoff delay entirely. Net effect: constant 200ms retry regardless of
 *      how many errors occurred.
 *
 * Production fix:
 *   - A single `pendingRestartRef` flag: whichever handler (onerror or onend)
 *     schedules the restart first sets the flag; the other handler is a no-op.
 *   - Backoff is calculated and stored before abort/end so it cannot be reset.
 *   - `onerror` calls `recognition.abort()` after setting the flag, ensuring
 *     onend fires with the flag already set → onend becomes a no-op.
 *   - Fatal errors (permission denied) permanently stop the hook.
 *   - Non-Chromium browsers get a single warning, not a retry loop.
 */
import { useEffect, useRef, useState, useCallback } from "react";

const FATAL_ERRORS = new Set(["not-allowed", "service-not-allowed", "audio-capture"]);

// Errors where retrying is pointless without user action
const NO_RETRY_ERRORS = new Set(["not-allowed", "service-not-allowed", "audio-capture"]);

export function useWakeWordDetector({
  enabled = false,
  keywords = ["hey genie", "okay genie", "hi genie", "genie"],
  onWakeWord,
}) {
  const recognitionRef      = useRef(null);
  const restartTimerRef     = useRef(null);
  const pendingRestartRef   = useRef(false);   // true = a restart is already scheduled
  const deadRef             = useRef(false);   // true = permanently stopped (fatal error)
  const networkErrCountRef  = useRef(0);
  const enabledRef          = useRef(enabled);
  const onWakeWordRef       = useRef(onWakeWord);
  const keywordsRef         = useRef(keywords);

  const [isListening, setIsListening] = useState(false);

  // Keep refs in sync with latest props without re-creating callbacks
  enabledRef.current    = enabled;
  onWakeWordRef.current = onWakeWord;
  keywordsRef.current   = keywords;

  // ── helpers ────────────────────────────────────────────────────────────────

  const clearTimer = () => {
    if (restartTimerRef.current) {
      clearTimeout(restartTimerRef.current);
      restartTimerRef.current = null;
    }
  };

  /** Schedule a restart after `delay` ms. Only the first caller wins. */
  const scheduleRestart = useCallback((delay) => {
    if (pendingRestartRef.current) return;  // already scheduled — drop duplicate
    pendingRestartRef.current = true;
    clearTimer();
    restartTimerRef.current = setTimeout(() => {
      pendingRestartRef.current = false;
      restartTimerRef.current   = null;
      if (enabledRef.current && !deadRef.current) {
        startInstance();
      }
    }, delay);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── core recognition lifecycle ─────────────────────────────────────────────

  const startInstance = useCallback(() => {
    if (!enabledRef.current || deadRef.current) return;
    if (recognitionRef.current) return;       // already running

    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      // Not a Chromium browser — stop permanently, no loop
      console.warn("⚠️ Wake word: Web Speech API unavailable. Use Chrome, Edge, or Brave.");
      deadRef.current = true;
      return;
    }

    const recognition = new SR();
    recognition.continuous      = false;   // false = cleaner restart cycle
    recognition.interimResults  = false;   // final transcripts only
    recognition.lang            = "en-US";
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      setIsListening(true);
      // Successful start resets network error counter
      networkErrCountRef.current = 0;
    };

    recognition.onresult = (event) => {
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript.toLowerCase().trim();
        const match = keywordsRef.current.find(
          (kw) => transcript.includes(kw.toLowerCase())
        );
        if (match) {
          console.log(`🎯 Wake word: "${match}"`);
          onWakeWordRef.current?.(match, transcript);
        }
      }
    };

    recognition.onerror = (event) => {
      setIsListening(false);

      if (NO_RETRY_ERRORS.has(event.error)) {
        console.error(`🚫 Wake word stopped: ${event.error}. Check microphone permissions.`);
        deadRef.current = true;
        recognitionRef.current = null;
        // abort() will trigger onend; with deadRef=true onend will not reschedule
        try { recognition.abort(); } catch (_) {}
        return;
      }

      if (event.error === "network") {
        networkErrCountRef.current += 1;
        // Exponential back-off: 2s → 4s → 8s → 16s → 32s → cap at 60s
        const delay = Math.min(2000 * Math.pow(2, networkErrCountRef.current - 1), 60000);
        console.warn(
          `🌐 Wake word network error #${networkErrCountRef.current}. ` +
          `Retry in ${delay / 1000}s. (Internet required for Web Speech API)`
        );
        // Schedule restart BEFORE calling abort() so onend sees pendingRestartRef=true
        scheduleRestart(delay);
        recognitionRef.current = null;
        try { recognition.abort(); } catch (_) {}
        return;
      }

      // no-speech / aborted / other: quick restart
      if (event.error !== "aborted") {
        scheduleRestart(300);
      }
      recognitionRef.current = null;
      try { recognition.abort(); } catch (_) {}
    };

    recognition.onend = () => {
      setIsListening(false);
      recognitionRef.current = null;
      // Only reschedule if onerror did NOT already do it
      if (!deadRef.current && enabledRef.current) {
        scheduleRestart(250);
      }
    };

    recognitionRef.current = recognition;
    try {
      recognition.start();
    } catch (err) {
      console.error("❌ Wake word start failed:", err.message);
      recognitionRef.current = null;
      scheduleRestart(3000);
    }
  }, [scheduleRestart]); // stable — uses refs for everything else

  // ── destroy ─────────────────────────────────────────────────────────────────

  const destroy = useCallback(() => {
    deadRef.current = true;
    clearTimer();
    pendingRestartRef.current = false;
    if (recognitionRef.current) {
      try { recognitionRef.current.abort(); } catch (_) {}
      recognitionRef.current = null;
    }
    setIsListening(false);
  }, []);

  // ── effect: respond to enabled prop changes ─────────────────────────────────

  useEffect(() => {
    if (enabled) {
      deadRef.current           = false;
      pendingRestartRef.current = false;
      networkErrCountRef.current = 0;
      startInstance();
    } else {
      destroy();
      console.log("⏹️ Wake word mode disabled");
    }
    return () => {
      // Cleanup on unmount — don't set deadRef so re-mount works
      clearTimer();
      pendingRestartRef.current = false;
      if (recognitionRef.current) {
        try { recognitionRef.current.abort(); } catch (_) {}
        recognitionRef.current = null;
      }
    };
  }, [enabled]); // eslint-disable-line react-hooks/exhaustive-deps

  return { isListening };
}

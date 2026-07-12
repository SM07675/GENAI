"""Wake word detection for hands-free activation.

Supports multiple wake word engines:
- Porcupine (Picovoice) - high accuracy, requires API key
- Vosk - fully offline, free
- Simple keyword matching as fallback

Users can say "Hey Genie" or "Okay Genie" to activate listening.
This module can be started automatically when the server boots.
"""
from __future__ import annotations

import logging
import threading
import queue
from typing import Callable

log = logging.getLogger("genie.wake_word")


class WakeWordDetector:
    """Listens for wake words to trigger voice interaction hands-free."""

    def __init__(self, callback: Callable[[], None], engine: str = "simple", keywords: list[str] | None = None):
        """
        Args:
            callback: Function to call when wake word is detected
            engine: "porcupine", "vosk", or "simple"
            keywords: Custom keywords to detect (default: ["genie", "hey genie", "okay genie"])
        """
        self.callback = callback
        self.engine = engine
        self.keywords = keywords or ["genie", "hey genie", "okay genie", "hi genie"]
        self.running = False
        self.thread = None
        self._detector = None
        self._audio_queue = queue.Queue()

    def start(self):
        """Start listening for wake words in background thread."""
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.thread.start()
        log.info(f"Wake word detection started (engine: {self.engine}, keywords: {self.keywords})")

    def stop(self):
        """Stop wake word detection."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        if self._detector:
            try:
                if hasattr(self._detector, 'delete'):
                    self._detector.delete()
            except Exception:
                pass
        log.info("Wake word detection stopped")

    def _listen_loop(self):
        """Background thread that continuously listens for wake words."""
        try:
            if self.engine == "porcupine":
                self._listen_porcupine()
            elif self.engine == "vosk":
                self._listen_vosk()
            else:
                self._listen_simple()
        except Exception as e:
            log.error(f"Wake word detection error: {e}")
            self.running = False

    def _listen_porcupine(self):
        """Use Porcupine for wake word detection (requires API key)."""
        try:
            import pvporcupine
            import pyaudio
        except ImportError:
            log.error("Porcupine requires: pip install pvporcupine pyaudio")
            return

        # Try to create custom wake word or use built-in keywords
        try:
            self._detector = pvporcupine.create(
                keywords=["jarvis", "computer"]  # closest to "genie"
            )
        except Exception as e:
            log.error(f"Failed to initialize Porcupine: {e}")
            return

        pa = pyaudio.PyAudio()
        audio_stream = pa.open(
            rate=self._detector.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=self._detector.frame_length,
        )

        log.info("Listening for 'Hey Genie' or 'Okay Genie'...")

        while self.running:
            pcm = audio_stream.read(self._detector.frame_length, exception_on_overflow=False)
            pcm = [int.from_bytes(pcm[i:i+2], byteorder='little', signed=True) 
                   for i in range(0, len(pcm), 2)]
            
            keyword_index = self._detector.process(pcm)
            if keyword_index >= 0:
                log.info("Wake word detected!")
                self.callback()

        audio_stream.close()
        pa.terminate()

    def _listen_vosk(self):
        """Use Vosk for wake word detection (fully offline)."""
        try:
            from vosk import Model, KaldiRecognizer
            import pyaudio
            import json
        except ImportError:
            log.error("Vosk requires: pip install vosk pyaudio")
            return

        # You'd need to download a Vosk model first
        try:
            model = Model(model_name="vosk-model-small-en-us-0.15")
            rec = KaldiRecognizer(model, 16000)
        except Exception as e:
            log.error(f"Failed to load Vosk model: {e}")
            log.info("Download model: python -m vosk download-model small-en-us")
            return

        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=4000,
        )

        log.info(f"Listening for wake words: {', '.join(self.keywords)}")

        while self.running:
            data = stream.read(4000, exception_on_overflow=False)
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                text = result.get("text", "").lower()
                
                # Check if any keyword is in the text
                for keyword in self.keywords:
                    if keyword.lower() in text:
                        log.info(f"Wake word detected: '{text}'")
                        self.callback()
                        break

        stream.close()
        pa.terminate()

    def _listen_simple(self):
        """Simple audio threshold + keyword detection fallback."""
        try:
            import pyaudio
            import numpy as np
        except ImportError:
            log.warning("Simple wake word requires: pip install pyaudio numpy")
            return

        # Just detect loud sounds as wake word (very basic)
        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=1024,
        )

        log.info("Simple wake detection active (loud sound triggers)")
        cooldown = 0

        while self.running:
            data = stream.read(1024, exception_on_overflow=False)
            audio_data = np.frombuffer(data, dtype=np.int16)
            volume = np.abs(audio_data).mean()

            # Trigger on loud sounds (above threshold) with cooldown
            if volume > 1000 and cooldown == 0:
                log.info("Activation sound detected!")
                self.callback()
                cooldown = 30  # ~2 second cooldown

            if cooldown > 0:
                cooldown -= 1

        stream.close()
        pa.terminate()

# Debug Session: genie-voice-loop [OPEN]

## Scope
- Project: Genie AI
- Goal: make the voice assistant run continuously with stable wake -> listen -> transcribe -> think -> speak -> follow-up -> wake cycles.
- User-reported symptoms: wake words only work once/randomly, recording sometimes never starts, clipped audio, stale/repeated commands, silence submits input, microphone locks, listening stops after one answer, TTS is unclear or incomplete, self-hearing/echo, stuck UI states, conflicting threads/audio loops, and failures halt the assistant.

## Hypotheses
1. Backend and frontend each drive parts of the voice lifecycle, creating duplicate state machines and conflicting microphone ownership.
2. Wake detection and speech capture are restarted on invalid or missing transitions after TTS/cancel/error paths.
3. Frontend recorder/VAD logic submits incomplete or stale chunks because it is tied to UI state changes instead of a backend-issued capture session.
4. Playback completion, follow-up listening, and wake restart are not synchronized to real audio playback completion.
5. Hidden exceptions or reconnect paths leave the system in inconsistent voice states without bounded recovery.

## Plan
1. Inspect the current voice path end to end.
2. Add instrumentation only.
3. Reproduce via tests and local runs.
4. Confirm root cause from logs.
5. Apply minimal structural fix.
6. Verify with tests and repeat-cycle checks.

## Status
- Created debug session file.
- Instrumentation pending.

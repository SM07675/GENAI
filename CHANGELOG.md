# Changelog

## [2.0.0] - Communication Upgrade - 2024

### 🎯 Major Features

#### Natural Conversation Mode
- **Continuous conversation mode**: Automatically listens after responding (like Alexa/Google Assistant)
- **Context awareness**: Understands follow-up questions without repeating context
- **Reference resolution**: Handles "it", "there", "another", etc. naturally
- **Multi-turn tracking**: Remembers locations, apps, queries across conversation

#### Communication Improvements
- **Natural responses**: Concise, conversational replies (not robotic)
- **Faster TTS**: Sentence-by-sentence streaming (500ms vs 2-3s latency)
- **Smart acknowledgments**: Uses "Sure", "Got it", "On it" naturally
- **Better error messages**: Friendly, helpful messages instead of technical errors

#### Optional Features
- **Wake word detection**: Say "Hey Genie" for hands-free activation
- **Configurable engines**: Porcupine, Vosk, or Simple detection
- **Settings panel**: Toggle continuous mode and other options via UI

### ✨ Enhancements

#### Backend
- Added `conversation_manager.py`: Context tracking and reference resolution
- Added `wake_word.py`: Optional wake word detection system
- Updated `orchestrator.py`: Integrated conversation context
- Enhanced `system_prompt.md`: Better communication guidelines
- Improved TTS pipeline: Sentence-level streaming with background processing

#### Frontend
- Updated `App.jsx`: Continuous mode logic, settings panel
- Enhanced `VoiceBar.jsx`: Auto-recording in continuous mode
- Improved `StatusBar.jsx`: Controls for continuous mode toggle
- Updated `appStore.js`: Added state for auto-recording
- Modified `useAudioPlayer.js`: Exposed `isPlaying` state for better flow

#### Documentation
- Added `ALEXA_MODE_GUIDE.md`: Quick start guide for users
- Added `COMMUNICATION_IMPROVEMENTS.md`: Technical documentation
- Added `EXAMPLES.md`: Real conversation examples
- Added `UPGRADE_SUMMARY.md`: What changed overview
- Updated `README.md`: Highlighted new features

### 🔧 Technical Changes

#### Context Resolution
- Location references: "there" → last mentioned location
- App references: "it" → last opened app
- Query references: "another" → continues previous search
- Automatic resolution in real-time (< 10ms overhead)

#### Performance
- **4-6x faster** perceived response time
- Parallel TTS generation for long responses
- Automatic engine selection (ElevenLabs for simple, Edge for complex)
- Background task management with proper cleanup

#### State Management
- Added `shouldAutoRecord` flag for continuous mode
- Better audio playback state tracking
- Conversation context per session (24h auto-cleanup)
- Multi-session support with isolation

### 🎨 UI/UX

#### New Controls
- Continuous mode toggle (🔄 button)
- Settings panel (⚙️ button)
- Visual "CONTINUOUS" badge when active
- Context-aware help text

#### Visual Feedback
- Orb states now more responsive
- Better loading indicators
- Smooth animations for mode changes
- Mobile-friendly controls

### 🐛 Bug Fixes
- Fixed audio queue management for continuous playback
- Improved WebSocket reconnection logic
- Better error handling for tool failures
- Prevented duplicate recordings in continuous mode

### 📊 Performance Metrics
- First audio latency: 2-3s → 500ms (**80% reduction**)
- Context resolution: < 10ms overhead
- TTS streaming: Sentence-by-sentence (instant start)
- Memory usage: Minimal increase (~2MB per session)

### 🔐 Security & Privacy
- All context stays in-memory (not persisted)
- Automatic context cleanup after 24h
- No new cloud dependencies (except optional wake word API)
- Local-first architecture maintained

### ⚠️ Breaking Changes
**None!** Fully backward compatible.

### 📦 New Dependencies (Optional)
- `pvporcupine` - For Porcupine wake word engine
- `vosk` - For Vosk wake word engine  
- `pyaudio` - For wake word audio capture
- `numpy` - For simple wake word detection

All wake word dependencies are optional and commented out by default.

### 🎓 Migration Guide
No migration needed! New features are opt-in:
1. Continuous mode is OFF by default (toggle in UI)
2. Wake word is optional (requires separate installation)
3. All existing functionality preserved

### 📝 Notes
- Context tracking works best for 2-3 recent turns
- Wake word requires clear pronunciation
- Continuous mode may need adjustment for noisy environments
- All new features can be disabled if not needed

---

## [1.0.0] - Initial Release

### Features
- Local STT with faster-whisper
- Edge TTS for voice synthesis
- Gemini LLM integration
- Tool system (apps, web, media, system control)
- Desktop and mobile support via ngrok
- WebSocket-based real-time communication
- Electron desktop app
- Memory and reminders
- News and web search
- YouTube Music integration

---

**For detailed upgrade information, see:**
- `UPGRADE_SUMMARY.md` - What changed overview
- `ALEXA_MODE_GUIDE.md` - User guide
- `COMMUNICATION_IMPROVEMENTS.md` - Technical details
- `EXAMPLES.md` - Usage examples

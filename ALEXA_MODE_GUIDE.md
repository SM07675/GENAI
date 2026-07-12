# 🎙️ Alexa/Google Assistant Mode - Quick Start Guide

Make Genie work just like Alexa, Google Assistant, or Gemini with natural conversation!

---

## 🚀 Quick Setup

### Step 1: Update Your Installation
```bash
cd backend
pip install -r requirements.txt
```

### Step 2: Enable Continuous Conversation Mode

1. Start Genie (run `start_genie.bat` or your normal startup)
2. In the Genie UI, click the **settings icon** (⚙️) in the status bar
3. Toggle **"Continuous Conversation Mode"** to **ON**
4. You'll see a "CONTINUOUS" badge in the status bar

That's it! Now Genie automatically listens after responding, just like Alexa.

---

## 💬 How to Use

### Natural Conversations
Once continuous mode is enabled, just talk naturally:

```
You: "What's the weather in New York?"
Genie: "It's 72 degrees and sunny in New York"
[Automatically starts listening]

You: "What about tomorrow?"
Genie: [Understands "New York" from context]
      "Tomorrow will be 68 degrees with some clouds"
[Automatically starts listening]

You: "Thanks"
Genie: "You're welcome!"
```

### Context Understanding
Genie now remembers what you talked about:

**Location References:**
```
"Weather in Paris" → "What about tomorrow there?" ✅
"Search restaurants in Tokyo" → "Show me more there" ✅
```

**App References:**
```
"Open Chrome" → "Close it" ✅
"Launch Spotify" → "Make it fullscreen" ✅
```

**Query References:**
```
"Play some jazz" → "Play another one" ✅
"Search for Python tutorials" → "Show me more" ✅
```

---

## 🎯 Key Features

### ✅ Like Alexa/Google Assistant
- **Hands-free:** No button presses needed in continuous mode
- **Natural language:** Speak like you would to a friend
- **Quick responses:** Starts speaking immediately (500ms vs 2-3 seconds before)
- **Context awareness:** Remembers what you just talked about
- **Follow-ups:** Just keep talking, no need to repeat context

### ✅ Better Than Cloud Assistants
- **Privacy:** Everything runs locally, no cloud data collection
- **Offline STT/TTS:** Works without internet (faster-whisper + Edge TTS)
- **Customizable:** Full control over behavior and responses
- **No wake word needed:** Push-to-talk still available anytime

---

## ⚙️ Settings & Customization

### Toggle Continuous Mode
**Via UI:** Click ⚙️ icon → Toggle "Continuous Conversation Mode"

**Via Code:** Edit `frontend/src/App.jsx`
```javascript
const [continuousMode, setContinuousMode] = useState(true); // true = on by default
```

### Adjust Auto-Listen Delay
Default: 800ms pause after Genie finishes speaking

Edit `frontend/src/App.jsx`:
```javascript
const timer = setTimeout(() => {
  // ...
}, 800); // Change this number (milliseconds)
```

### Change Voice Style
Edit `backend/app/prompts/system_prompt.md` to customize personality:
- More casual vs professional
- More verbose vs concise
- Personality traits (friendly, technical, humorous)

---

## 🎤 Optional: Wake Word Detection

Want true hands-free like Alexa? Add wake word detection!

### Setup (Choose One Engine)

**Option 1: Vosk (Recommended - Free & Offline)**
```bash
pip install vosk pyaudio
```

**Option 2: Porcupine (Most Accurate - Requires API Key)**
```bash
pip install pvporcupine pyaudio
```

**Option 3: Simple Mode (Basic - No Extra Setup)**
```bash
pip install pyaudio numpy
```

### Usage Example
```python
# Add to backend/app/main.py
from .wake_word import WakeWordDetector

def on_wake_word():
    print("Wake word detected! Starting to listen...")
    # Trigger voice recording
    
detector = WakeWordDetector(callback=on_wake_word, engine="vosk")
detector.start()
```

Say **"Hey Genie"** or **"Okay Genie"** to activate!

---

## 🎨 UI Indicators

### Status Bar
- **🔄 button:** Toggle continuous mode
- **⚙️ button:** Open settings
- **"CONTINUOUS" badge:** Shows when mode is active

### Orb States
- **Ready:** Green, idle
- **Listening:** Blue, pulsing (microphone active)
- **Thinking:** Purple, animated (processing)
- **Speaking:** Pink, pulsing (TTS playing)

### Voice Bar
- Shows "Continuous mode active" when enabled
- Updates help text based on mode
- Stop button appears when Genie is working

---

## 💡 Tips & Tricks

### 1. Natural Speech Patterns
✅ **Good:** "What's the weather?"
❌ **Unnecessary:** "Computer, please tell me what the current weather conditions are"

✅ **Good:** "Play some jazz" → "Play another"
❌ **Unnecessary:** "Play some jazz" → "Play another jazz song"

### 2. Quick Interruptions
While Genie is speaking or thinking, click **"Stop"** to interrupt immediately.

### 3. Mix Voice & Text
Continuous mode doesn't affect text input - use whichever is convenient!

### 4. Context Reset
If Genie misunderstands context, just be explicit:
"No, I meant weather in London, not Paris"

### 5. Battery Saving
On mobile or laptop? Disable continuous mode to save battery - just use push-to-talk instead.

---

## 🔧 Troubleshooting

### Issue: Genie doesn't auto-listen after responding
**Solution:** 
1. Check continuous mode is enabled (⚙️ → toggle ON)
2. Look for "CONTINUOUS" badge in status bar
3. Verify audio finished playing (check orb state)

### Issue: Too much background noise triggers false recordings
**Solution:**
1. Disable continuous mode temporarily
2. Use push-to-talk (hold mic button)
3. Adjust microphone sensitivity in system settings

### Issue: Responses are too slow
**Solution:**
1. Check TTS engine setting in `.env`: `TTS_ENGINE=auto`
2. For faster responses on simple queries, use `TTS_ENGINE=elevenlabs`
3. Ensure good internet connection (for cloud LLM calls)

### Issue: Context not working correctly
**Solution:**
1. Be more specific initially: "Weather in Tokyo" not just "weather"
2. Conversation context resets after 20+ turns (by design)
3. Try rephrasing if misunderstood

### Issue: Wake word not detecting
**Solution:**
1. Speak clearly: "Hey GEE-nee" with emphasis
2. Check microphone permissions
3. Try different engine: Vosk vs Porcupine vs Simple
4. Reduce background noise

---

## 📚 Examples Library

### Smart Home Control
```
"Set volume to 50" 
"Now to 75" ✅ (remembers previous volume command)
"Turn on night light"
"Turn it off" ✅ (remembers night light)
```

### Media Control
```
"Play Arijit Singh on YouTube Music"
"Play another song from him" ✅
"Show me sad playlists"
"Play the first one" ✅
```

### Information Queries
```
"What's the news about AI?"
"What about Tesla?" ✅ (understands topic switch)
"Give me a morning briefing"
"What's the weather?" ✅
```

### App Control
```
"Open Chrome"
"Go to YouTube" ✅ (opens URL in Chrome)
"Now open Instagram" ✅
"Close all of them" ✅ (closes mentioned apps)
```

---

## 🌟 Advanced Features

### Custom Personality
Edit `system_prompt.md` to make Genie more:
- **Casual:** "Yo, opening Chrome for ya"
- **Professional:** "Launching Chrome browser now"
- **Humorous:** "Chrome time! Let's browse the interwebs"
- **Multilingual:** Mix English/Hindi naturally

### Voice Cloning (Future)
Genie supports ElevenLabs - use voice cloning to have Genie speak in your voice or a celebrity's!

### Multi-user Context
Currently single-session. For multi-user, extend `conversation_manager.py` with user profiles.

---

## 🎓 Learn More

- **Full documentation:** See `COMMUNICATION_IMPROVEMENTS.md`
- **Technical details:** Check `backend/app/conversation_manager.py`
- **System prompt:** Read `backend/app/prompts/system_prompt.md`
- **Original README:** See `README.md` for full feature list

---

## 🎉 Enjoy Your Personal AI Assistant!

You now have a local, privacy-focused assistant that works like Alexa or Google Assistant, but:
- ✅ No cloud dependency (except optional LLM)
- ✅ Complete privacy control
- ✅ Fully customizable
- ✅ Open source

**Happy talking!** 🎙️✨

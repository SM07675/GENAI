# 🚀 Genie Quick Reference Card

## 💬 Natural Communication Patterns

### Context-Aware Conversations
```
✅ "Weather in Tokyo" → "Tomorrow?" → "Day after?"
✅ "Open Chrome" → "Close it"
✅ "Play jazz" → "Play another"
✅ "Search Python" → "Show me more"
```

### Natural Responses
```
Before: "I have successfully launched Chrome"
After:  "Opening Chrome"
```

---

## 🎙️ Continuous Mode

### Enable
Click ⚙️ → Toggle "Continuous Conversation Mode" → **ON**

### How It Works
```
You:   "What time is it?"
Genie: "It's 3 PM" [auto-starts listening]
You:   "Set a timer for 5 minutes"
Genie: "Timer set" [auto-starts listening]
```

### Disable
Click ⚙️ → Toggle **OFF** or click "Stop" button

---

## 🗣️ Voice Commands

### System Control
```
"Set volume to 50"
"Turn on night light"
"Sleep the PC"
"What time is it?"
```

### Apps & Web
```
"Open Chrome"
"Close Spotify"
"Launch Steam"
"Open Instagram"
```

### Media
```
"Play sad songs"
"Play Arijit Singh on YouTube Music"
"Search for jazz playlists"
"Play another one"
```

### Information
```
"What's the weather?"
"Give me AI news"
"Search for Python tutorials"
"Morning briefing"
```

### Memory & Reminders
```
"Remember my favorite color is blue"
"Set reminder for 10 minutes"
"What are my notes?"
"Forget about the meeting"
```

---

## 🔗 Context Examples

### Pronouns
```
"Open Spotify" → "Close it" ✅
"Weather in Paris" → "Tomorrow there?" ✅
"Play jazz" → "Another one" ✅
```

### References
```
"Search restaurants in Seattle" → "Show me more" ✅
"Open Chrome" → "Make it fullscreen" ✅
```

---

## ⚙️ Settings

| Setting | Location | Default |
|---------|----------|---------|
| Continuous Mode | ⚙️ button → Toggle | OFF |
| TTS Engine | `.env` → `TTS_ENGINE` | auto |
| Wake Word | Optional install | Not installed |

---

## 🎯 Pro Tips

1. **Be specific initially**, then use context:
   - ✅ "Weather in Tokyo" → "Tomorrow?"
   - ❌ "Weather" → "Tomorrow?" (which city?)

2. **Enable continuous mode** for hands-free:
   - No button presses between questions
   - Like talking to Alexa

3. **Speak naturally**:
   - ✅ "What's the weather?"
   - ❌ "Computer, please tell me the weather"

4. **Mix voice & text**:
   - Use whatever's convenient
   - Both work the same

5. **Interrupt anytime**:
   - Click "Stop" to cancel
   - Start new command immediately

---

## 🐛 Troubleshooting

### Genie doesn't auto-listen
- Check continuous mode is ON (⚙️ button)
- Look for "CONTINUOUS" badge
- Verify audio finished playing

### Context not working
- Be more specific initially
- Context resets after 20 turns
- Try rephrasing if misunderstood

### Too slow
- Check internet connection
- Use `TTS_ENGINE=elevenlabs` in `.env`
- Close other heavy apps

### Background noise triggers recording
- Disable continuous mode
- Use push-to-talk (hold mic)
- Adjust mic sensitivity in OS

---

## 📱 Mobile Access

1. Look for URL in status bar (📱 icon)
2. Copy URL to phone browser
3. Enter PIN when prompted
4. Use same features as desktop

---

## ⌨️ Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Focus text input | Click input field |
| Start recording | Hold mic button |
| Stop Genie | Click "Stop" |
| Toggle continuous | Click 🔄 |
| Settings | Click ⚙️ |

---

## 🎨 Visual Indicators

### Orb Colors
- 🟢 **Green/Idle** - Ready for input
- 🔵 **Blue/Listening** - Recording voice
- 🟣 **Purple/Thinking** - Processing
- 🌸 **Pink/Speaking** - Playing audio

### Status Bar
- **Connected** - Green dot
- **Connecting** - Yellow dot (pulsing)
- **Error** - Red dot
- **CONTINUOUS** - Badge when mode active

---

## 📖 Documentation

| File | Purpose |
|------|---------|
| `ALEXA_MODE_GUIDE.md` | Full user guide |
| `EXAMPLES.md` | Conversation examples |
| `UPGRADE_SUMMARY.md` | What's new |
| `README.md` | Main documentation |

---

## 🎓 Learning Path

1. **Start here** → Try basic commands
2. **Enable continuous mode** → Experience hands-free
3. **Test context** → "Weather in Tokyo" → "Tomorrow?"
4. **Read examples** → See `EXAMPLES.md`
5. **Customize** → Edit `system_prompt.md`

---

## 🌟 Common Workflows

### Morning Routine
```
"Good morning"
"Morning briefing"
"Set volume to 30"
"Play focus music"
```

### Work Session
```
"Open VS Code"
"Open Chrome"
"Play lo-fi music"
"Volume to 20"
```

### Quick Info
```
"What time is it?"
"Weather?"
"Set timer 5 minutes"
"Remind me to stretch"
```

### Evening Wind-Down
```
"Turn on night light"
"Play relaxing music"
"Volume to 15"
"Set alarm 7 AM"
```

---

## 💡 Remember

- **Speak naturally** - Genie understands casual language
- **Use context** - Say "it", "there", "another" freely
- **Enable continuous** - For best Alexa-like experience
- **Interrupt anytime** - Click "Stop" if needed
- **Privacy first** - Everything runs locally

---

**Quick Start:** Enable continuous mode (⚙️), say "What time is it?", and keep talking!

🎙️ **Enjoy your AI assistant!** ✨

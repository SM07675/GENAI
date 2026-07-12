# 🔧 Wake Word Troubleshooting

## Quick Checklist

If wake word is not working, follow these steps:

### ✅ Step 1: Check Browser
- [ ] Using Chrome, Edge, or Brave? (Required!)
- [ ] NOT using Firefox or Safari? (Not supported)

### ✅ Step 2: Enable Wake Word Mode
- [ ] Settings opened (⚙️ icon)?
- [ ] "Wake Word Mode (Auto-Listen)" toggled ON?
- [ ] Green indicator shows in settings?

### ✅ Step 3: Microphone Permissions
- [ ] Browser asked for microphone permission?
- [ ] Clicked "Allow"?
- [ ] Check 🎤 icon in address bar (should show as allowed)

### ✅ Step 4: Check Console Logs
1. Press **F12** to open Developer Tools
2. Click **Console** tab
3. Look for these messages:

**Expected (Good):**
```
✅ Wake word mode enabled - Say "Hey Genie" or "Okay Genie"
🎙️ Starting wake word detection...
✅ Wake word detector started - listening for: hey genie, okay genie, hi genie, genie
```

**Problem Indicators:**
```
❌ Speech Recognition API not supported in this browser
→ Solution: Use Chrome, Edge, or Brave

🚫 Microphone permission denied!
→ Solution: Allow microphone in browser settings

❌ Wake word detection error: not-allowed
→ Solution: Grant microphone permissions
```

### ✅ Step 5: Test Wake Word
1. Speak clearly: **"Hey Genie"**
2. Check console for: `🎤 Heard: hey genie`
3. Should see: `🎯 Wake word detected: "hey genie"`
4. Orb should turn blue (recording starts)

### ✅ Step 6: Speak Command
1. Say your command: "What time is it?"
2. Wait 2 seconds (silence detection)
3. Recording should auto-end
4. Genie should process and respond

---

## Common Issues & Solutions

### Issue 1: "Speech Recognition not supported"

**Problem:** Browser doesn't support Web Speech API

**Solution:**
```
1. Switch to Chrome, Edge, or Brave
2. Update browser to latest version
3. Restart browser after update
```

### Issue 2: Microphone Permission Denied

**Problem:** Browser blocked microphone access

**Solution:**
```
1. Click 🎤 icon in address bar (left of URL)
2. Select "Always allow http://localhost to access your microphone"
3. Click "Done"
4. Refresh page (F5)
5. Toggle wake word mode OFF then ON again
```

**Alternative (Reset Permissions):**
```
Chrome:
1. Settings → Privacy and security → Site settings
2. Microphone → Look for localhost:5173
3. Remove and re-allow

Edge: Same as Chrome
Brave: Same as Chrome
```

### Issue 3: Console Shows No Logs

**Problem:** Wake word detector not starting

**Check:**
```javascript
// Open Console (F12) and type:
console.log(window.SpeechRecognition || window.webkitSpeechRecognition);

// Should show: function SpeechRecognition() { [native code] }
// If shows: undefined → Browser not supported
```

**Solution:**
1. Verify you're using Chrome/Edge/Brave
2. Check browser version (must be recent)
3. Try incognito/private mode
4. Disable browser extensions (may interfere)

### Issue 4: Detects Wrong Words

**Problem:** Console shows `🎤 Heard: [something else]`

**This is normal!** The detector hears everything but only triggers on keywords.

**Check:**
```
🎤 Heard: hello there           ← Ignored (not a keyword)
🎤 Heard: hey genie            ← Triggers! ✅
🎯 Wake word detected: "hey genie"
```

**If it never hears "hey genie":**
- Speak louder
- Speak more clearly
- Move closer to microphone
- Reduce background noise
- Try "Okay Genie" instead

### Issue 5: Starts Recording But No Response

**Problem:** Wake word works, but command not processed

**Check Console:**
```
✅ Wake word detector started
🎤 Heard: hey genie
🎯 Wake word detected: "hey genie"
🔄 Starting recording...          ← Should see this

If missing → Check VoiceBar beginRecording function
```

**Solutions:**
1. Check WebSocket connection (Status: "Ready"?)
2. Check backend is running (port 8765)
3. Check audio recorder permissions
4. Try disabling then re-enabling wake word mode

### Issue 6: Auto-End Not Working

**Problem:** Recording doesn't stop after silence

**Check:**
- Are you in wake word mode? (required for auto-end)
- Wait full 2 seconds of silence
- Try speaking then staying completely quiet

**Adjust timeout if needed:**
```javascript
// In VoiceBar.jsx
silenceThreshold: 3000, // Change from 2000 to 3000 (3 seconds)
```

### Issue 7: False Triggers

**Problem:** Starts recording randomly

**Cause:** Detecting similar-sounding words in background

**Solutions:**
1. Reduce background noise (TV, music)
2. Disable wake word when not actively using
3. Use stricter keywords:

```javascript
// In VoiceBar.jsx, change to:
keywords: ["hey genie", "okay genie"], // Remove "hi genie" and "genie"
```

---

## Debug Commands

### Check Speech Recognition Support
```javascript
// Open Console (F12)
console.log('Speech Recognition:', 
  window.SpeechRecognition || window.webkitSpeechRecognition ? 'Supported ✅' : 'Not Supported ❌'
);
```

### Check Microphone Permissions
```javascript
// Open Console (F12)
navigator.permissions.query({ name: 'microphone' }).then(result => {
  console.log('Microphone Permission:', result.state);
  // Expected: "granted" ✅
  // Problem: "denied" ❌ or "prompt" ⚠️
});
```

### Test Speech Recognition Manually
```javascript
// Open Console (F12)
const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
recognition.onresult = (e) => console.log('Heard:', e.results[0][0].transcript);
recognition.start();
// Now speak and watch console!
```

---

## Working Example

When everything works correctly, you should see:

```
Console Log:
-----------
✅ Wake word mode enabled - Say "Hey Genie" or "Okay Genie"
🎙️ Starting wake word detection...
✅ Wake word detector started - listening for: hey genie, okay genie, hi genie, genie

[You say: "Hey Genie"]

🎤 Heard: hey genie
🎯 Wake word detected: "hey genie" (matched: hey genie)
🔵 Orb: Blue (recording starts)

[You say: "What time is it?"]

🎤 Recording audio...
⏰ Silence detected - auto-ending recording
🟣 Orb: Purple (processing)

[Genie responds: "It's 3:45 PM"]

🌸 Orb: Pink (speaking)
🔄 Restarting wake word detector...
✅ Wake word detector started - listening for: hey genie, okay genie, hi genie, genie

[Ready for next command!]
```

---

## Still Not Working?

### Nuclear Option: Full Reset

```bash
# 1. Close Genie completely
# 2. Clear browser data for localhost
Chrome: Settings → Privacy → Clear browsing data → Cookies and site data → localhost

# 3. Reset microphone permissions
Chrome: Settings → Privacy → Site settings → Microphone → Remove localhost

# 4. Restart browser completely

# 5. Start Genie fresh
npm run electron:dev

# 6. Grant microphone permission (fresh)
# 7. Enable wake word mode
# 8. Test with "Hey Genie"
```

### Report Issue

If still not working after all troubleshooting:

1. **Browser:** Chrome/Edge/Brave version?
2. **OS:** Windows/Mac/Linux?
3. **Console errors:** Copy full error messages
4. **Mic test:** Does mic work in other apps?
5. **Logs:** Share console output

Post in issues with this info!

---

## Success Indicators

When wake word is working:

✅ Settings show "Wake Word Mode: ON"  
✅ Console shows "Wake word detector started"  
✅ Mic button pulses pink/violet  
✅ Status text: "🎙️ Listening for 'Hey Genie'..."  
✅ Console logs each thing you say  
✅ Detects "hey genie" correctly  
✅ Orb turns blue on detection  
✅ Recording starts automatically  
✅ Auto-ends after 2 seconds silence  
✅ Returns to listening after response  

**All green? You're good to go!** 🎉

---

## Quick Test

```
1. F12 → Console tab
2. Enable wake word mode
3. Look for: "✅ Wake word detector started"
4. Say: "Hey Genie"
5. Look for: "🎯 Wake word detected"
6. Orb turns blue
7. Say: "What time is it?"
8. Wait 2 seconds
9. Genie responds
10. Returns to listening

If all 10 steps work → Success! ✅
If any step fails → See troubleshooting above
```

---

**Good luck!** 🎙️✨

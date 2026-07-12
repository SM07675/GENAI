# 🚀 Quick Start Guide - Genie AI Voice Assistant

## ⚠️ IMPORTANT: Start Backend First!

Genie requires **TWO** processes running:
1. **Backend Server** (FastAPI + WebSocket)
2. **Frontend App** (Electron + React)

---

## 📋 Step-by-Step Startup

### Step 1: Install Dependencies (First Time Only)

#### Backend
```bash
cd backend
pip install -r requirements.txt
```

#### Frontend
```bash
cd frontend
npm install
```

---

### Step 2: Configure Backend (First Time Only)

1. Copy the example environment file:
```bash
cd backend
cp .env.example .env
```

2. Edit `backend/.env` and add your API keys:
```bash
# Required
GEMINI_API_KEY=your_gemini_api_key_here

# Optional (for enhanced features)
ELEVENLABS_API_KEY=your_key_here
NEWS_API_KEY=your_key_here
```

Get your Gemini API key: https://aistudio.google.com/app/apikey

---

### Step 3: Start Backend Server

Open Terminal/Command Prompt #1:

```bash
cd backend
python run.py
```

**Wait for this message:**
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8765
```

✅ Backend is ready when you see "Application startup complete"

---

### Step 4: Start Frontend App

Open Terminal/Command Prompt #2 (keep backend running):

```bash
cd frontend
npm run electron:dev
```

**Expected output:**
```
[0] VITE v5.4.21 ready in 253 ms
[0] ➜  Local:   http://localhost:5173/
[1] Electron app should open automatically
```

---

## 🎯 What You Should See

1. **Electron window opens** with Genie UI
2. **PIN gate appears** - Enter your 4-digit PIN (default: check backend logs)
3. **Genie interface loads** with Siri-style orb
4. **You can now talk to Genie!**

---

## 🐛 Troubleshooting

### Issue: "Connection refused" or "Cannot connect to backend"

**Cause:** Backend server isn't running

**Fix:**
```bash
# In Terminal 1, start backend
cd backend
python run.py
```

### Issue: "Electron exited with code 0"

**Cause:** This is actually normal! It means Electron tried to start but didn't stay open.

**Possible reasons:**
1. Backend not running (most common)
2. Port 8765 already in use
3. React error in browser

**Fix:**
1. Make sure backend is running first
2. Check backend terminal for errors
3. Try restarting both backend and frontend

### Issue: "Module not found" errors

**Cause:** Dependencies not installed

**Fix:**
```bash
# Backend
cd backend
pip install -r requirements.txt

# Frontend
cd frontend
npm install
```

### Issue: "Port 5173 already in use"

**Fix:**
```bash
# Kill the process using port 5173
# Windows:
netstat -ano | findstr :5173
taskkill /PID <process_id> /F

# Linux/Mac:
lsof -ti:5173 | xargs kill -9
```

### Issue: Frontend opens but shows blank screen

**Cause:** Backend not running or connection failed

**Fix:**
1. Check backend is running on port 8765
2. Check browser console (Ctrl+Shift+I) for errors
3. Verify `.env` file has correct settings

---

## 📝 Quick Checklist

Before asking "why isn't it working?", check:

- [ ] Backend dependencies installed (`pip install -r requirements.txt`)
- [ ] Frontend dependencies installed (`npm install`)
- [ ] Backend `.env` file exists with API keys
- [ ] Backend server is running (Terminal 1)
- [ ] Backend shows "Application startup complete"
- [ ] Frontend started AFTER backend (Terminal 2)
- [ ] No port conflicts (8765, 5173)

---

## 🎉 Once Running

### Enable Features

Click the ⚙️ Settings icon (top-right) to enable:

1. **Wake Word Mode** - Say "Hey Genie" or "Okay Genie" to activate
2. **Continuous Mode** - Genie auto-listens after responding (like Alexa)

### Test Wake Word Detection

1. Enable Wake Word Mode in settings
2. Open browser console (Ctrl+Shift+I)
3. Say "Hey Genie"
4. Watch console for: `🎯 Wake word detected`

### Test Voice Commands

1. Hold the microphone button
2. Speak your command
3. Release to send
4. Genie responds!

---

## 🔧 Development Tips

### Backend Logs
Watch backend terminal for:
- Request logs
- Tool execution
- Rate limiter stats
- Errors

### Frontend Logs
Press `Ctrl+Shift+I` in Electron window to open DevTools

### Hot Reload
- **Backend**: Auto-reloads on file changes (uvicorn)
- **Frontend**: Auto-reloads on file changes (Vite)

---

## 📚 More Documentation

| Document | Purpose |
|----------|---------|
| `PROJECT_STATUS.md` | Feature completion status |
| `ALEXA_MODE_GUIDE.md` | Natural conversation features |
| `WAKE_WORD_TEST_GUIDE.md` | Wake word testing |
| `OPTIMIZATION_GUIDE.md` | Rate limiting & caching |
| `NEW_SIRI_DESIGN.md` | UI design details |
| `QUICK_REFERENCE.md` | Command reference |

---

## 🎯 Summary

**The correct startup sequence:**

```bash
# Terminal 1 - Backend
cd backend
python run.py
# Wait for "Application startup complete"

# Terminal 2 - Frontend (in new terminal)
cd frontend
npm run electron:dev
# Electron window opens
```

**Both must be running simultaneously!**

---

## 💡 Pro Tips

1. Keep both terminals visible so you can see errors
2. Backend logs show what Genie is thinking
3. Use Ctrl+C to stop each process gracefully
4. Restart both if you update dependencies
5. Check backend terminal if frontend can't connect

---

**Ready to start? Open two terminals and follow Step 3 & 4!** 🚀

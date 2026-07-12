# Genie — Personal AI Assistant

> A **local, offline-first** AI assistant that lives on your PC (Electron desktop) and on your phone (via ngrok). Built with Gemini for reasoning, faster-whisper for speech-to-text, and Edge TTS for voice — with zero cloud STT/TTS costs by default.

## 🆕 New: Alexa/Google Assistant-Style Communication!

Genie now features **natural conversation mode** with:
- ✅ **Continuous conversation** - Automatically listens after responding (hands-free!)
- ✅ **Context awareness** - Understands follow-ups like "what about tomorrow?" and "close it"
- ✅ **Natural responses** - Speaks like Alexa/Google, not a robot
- ✅ **Ultra-low latency** - Starts speaking in 500ms (4-6x faster)
- ✅ **Optional wake word** - Say "Hey Genie" for hands-free activation
- ✅ **Smart rate limiting** - Prevents "too many requests" errors (40-70% fewer API calls)
- ✅ **Response caching** - Instant replies for repeated queries

👉 **[Quick Start Guide for Alexa Mode](./ALEXA_MODE_GUIDE.md)**  
📖 **[Full Technical Documentation](./COMMUNICATION_IMPROVEMENTS.md)**  
🚀 **[Optimization Guide (Rate Limits & Wake Word)](./OPTIMIZATION_GUIDE.md)**

---

## What Genie Can Do

| Voice / Text Command | What Happens |
|---|---|
| "Open Chrome" | Launches Chrome desktop app |
| "Open Ajay's Instagram chat" | Opens the DM thread in browser |
| "Launch Palworld" | Fires up Steam game |
| "Play sad songs" | Opens curated YouTube playlist |
| "Play Arijit Singh on YouTube Music" | Uses YouTube Data API metadata when configured, then opens YouTube Music |
| "Give me AI news" | Fetches live news from NewsAPI, GNews, TheNewsAPI, RSS, or DuckDuckGo fallback |
| "Give me a morning briefing" | Builds a multi-topic news briefing |
| "Set volume to 50" | Sets Windows master volume |
| "Toggle night light" | Flips Windows Night Light |
| "Sleep the PC" | Puts computer to sleep |
| "Type a leave letter in Notepad" | Ghost-types the full letter |
| "What's on my screen?" | Gemini vision reads the display |

---

## Architecture

```
┌─────────────┐     WebSocket /ws     ┌──────────────────────┐
│  Frontend   │ ◄──────────────────── │   FastAPI Backend    │
│ Electron+   │                        │                      │
│   React     │  binary audio frames  │  faster-whisper STT  │
│  (Vite)     │ ──────────────────── ►│  Gemini (ReAct)      │
│             │  text deltas / audio  │  Edge TTS            │
│             │ ◄──────────────────── │  Tool executor       │
└─────────────┘                        └──────────────────────┘
        ▲                                        │
        │        ngrok HTTPS tunnel              │
        └─────── Mobile browser ────────────────┘
```

**One WebSocket** carries the entire conversation. No polling.

### Message Protocol

| Direction | Type | Purpose |
|---|---|---|
| client→server | `hello` | PIN authentication |
| client→server | `text` | Typed command |
| client→server | `audio_end` | End of audio stream → trigger STT |
| client→server | `cancel` | Cancel in-flight turn |
| server→client | `auth_ok/fail` | Auth result |
| server→client | `public_url` | Ngrok URL for mobile pairing |
| server→client | `transcript` | Whisper transcription |
| server→client | `assistant_text` | Streaming text deltas |
| server→client | `assistant_audio` | Base64 MP3 (Edge TTS / ElevenLabs) |
| server→client | `tool_start/end` | Tool execution events |
| server→client | `orb_state` | UI state: idle/listening/thinking/speaking |

---

## Directory Structure

```
D:\GENAI\
├── README.md
├── SETUP.md              ← step-by-step run guide
├── .gitignore
├── backend/
│   ├── requirements.txt
│   ├── .env.example      ← copy to .env and fill in your keys
│   ├── run.py            ← python run.py to start
│   └── app/
│       ├── main.py       ← FastAPI + WebSocket endpoint
│       ├── config.py     ← pydantic-settings
│       ├── auth.py       ← PIN + session tokens
│       ├── orchestrator.py ← Gemini ReAct loop
│       ├── llm_client.py ← AsyncOpenAI → Gemini
│       ├── stt.py        ← faster-whisper (local, offline)
│       ├── tts.py        ← Edge TTS + ElevenLabs fallback
│       ├── ngrok_tunnel.py
│       ├── schemas.py    ← Pydantic models
│       ├── services/     ← API manager, cache, retries, provider health
│       ├── api/          ← REST routes for external APIs and YouTube Music
│       ├── prompts/
│       │   └── system_prompt.md
│       └── tools/
│           ├── registry.py   ← @tool decorator + dispatch
│           ├── apps.py       ← open_app, close_app, launch_steam_game
│           ├── web.py        ← open_url, WhatsApp/Instagram DM
│           ├── media.py      ← YouTube search + playlists
│           ├── system_control.py ← volume, night light, sleep
│           ├── ghost_type.py
│           └── screen_vision.py
└── frontend/             ← Electron + React + Vite + Tailwind
    ├── package.json
    ├── electron/main.js  ← frameless window
    └── src/
        ├── App.jsx       ← PIN gate → WS → orb + chat
        ├── components/   ← GlowOrb, ChatPanel, VoiceBar, …
        ├── hooks/        ← useWebSocket, useAudioRecorder, useAudioPlayer
        ├── store/        ← Zustand store
        └── lib/          ← api.js, audio.js helpers
```

---

## Tech Stack

| Layer | Tech |
|---|---|
| LLM | Gemini (OpenAI-compatible) |
| STT | faster-whisper (local, CUDA/CPU, no API key) |
| TTS | Edge TTS, ElevenLabs, or Gemini Live native audio |
| Backend | FastAPI + uvicorn + WebSockets |
| Frontend | React 18 + Framer Motion + Zustand |
| Desktop | Electron 33 (frameless, transparent) |
| Styling | Tailwind CSS v3 (custom futuristic palette) |
| Tunnel | pyngrok (ngrok v3) |

### API Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/apis/status` | Provider config/health/circuit status |
| `GET /api/v1/apis/search?q=...` | Web search via Google CSE or DuckDuckGo |
| `GET /api/v1/apis/news?topic=...` | News via NewsAPI, GNews, TheNewsAPI, RSS, or DuckDuckGo |
| `GET /api/v1/music/search?q=...` | YouTube Music search via optional `ytmusicapi` |
| `GET /api/v1/music/charts` | YouTube Music charts |
| `GET /api/v1/music/lyrics/{browse_id}` | Lyrics lookup when a browse ID is available |

---

See **[SETUP.md](./SETUP.md)** for step-by-step installation and run instructions.

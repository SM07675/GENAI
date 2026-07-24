# Genie — Setup Guide

Follow these steps in order. The whole setup takes about 5–10 minutes on a normal PC.

---

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.11+ | [python.org](https://python.org) |
| Node.js | 18+ | [nodejs.org](https://nodejs.org) |
| Git | any | for cloning |
| CUDA (optional) | 11.8+ | faster-whisper GPU acceleration |

---

## Step 1 — Get your API keys

1. Choose a cloud LLM key: Google AI Studio for Gemini, or the xAI Console for Grok.
2. Optionally get a **YouTube Data API key** from Google Cloud Console. Genie uses it for official YouTube Music metadata, then opens playback on `music.youtube.com`.
3. Optionally set up **Google Custom Search JSON API** plus a Programmable Search Engine CX ID for official web search.
4. Optionally get **NewsAPI**, **GNews**, and/or **TheNewsAPI** keys for official news providers. Genie falls back to RSS/DuckDuckGo if you leave these blank.
5. Optionally get a **free ngrok authtoken** from [dashboard.ngrok.com](https://dashboard.ngrok.com/get-started/your-authtoken) (stable tunnels for mobile).
6. Optionally get an **ElevenLabs API key** from [elevenlabs.io](https://elevenlabs.io) (higher-quality voice).

---

## Step 2 — Configure the backend

```powershell
cd D:\GENAI\backend
copy .env.example .env
```

Open `backend\.env` in any editor and fill in:

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-gemini-key-here
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
GEMINI_MODEL=gemini-2.5-flash

# To use Grok instead:
# LLM_PROVIDER=grok
# XAI_API_KEY=your-xai-key-here
# GROK_MODEL=grok-4.5

# Optional but strongly recommended:
NGROK_AUTHTOKEN=your-ngrok-token-here

# Optional official APIs:
YOUTUBE_DATA_API_KEY=your-youtube-data-api-key
GOOGLE_CSE_API_KEY=your-google-cse-key
GOOGLE_CSE_CX=your-programmable-search-engine-id
NEWS_API_KEY=your-newsapi-key
GNEWS_API_KEY=your-gnews-key
THENEWSAPI_KEY=your-thenewsapi-key

# Optional most natural voice mode:
# TTS_ENGINE=gemini_live
# GEMINI_LIVE_VOICE_NAME=Aoede

# Optional – set a fixed PIN instead of auto-generated:
# GENIE_PIN=1234
```

Everything else has sensible defaults — you don't need to touch it.

---

## Step 3 — Install Python dependencies

> **Why `py -3.11`?** Windows creates a fake `python` stub that opens the Microsoft Store. Use the `py` launcher with an explicit version instead.

```powershell
cd D:\GENAI\backend
py -3.11 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

> **GPU acceleration (optional):** If you have an NVIDIA GPU, install the CUDA build of faster-whisper's backend:
> ```powershell
> .venv\Scripts\pip install faster-whisper[cuda]
> ```
> Then set `STT_DEVICE=cuda` and `STT_COMPUTE_TYPE=float16` in `.env`.

---

## Step 4 — Start the backend

```powershell
cd D:\GENAI\backend
.venv\Scripts\python run.py
```

> **No need to activate the venv** — just call `.venv\Scripts\python` directly.

You'll see:
```
============================================================
  Genie backend starting
  Local:  http://127.0.0.1:8765
  PIN:    4291   (share this with your phone)
============================================================
```

The **PIN** is what your phone needs to connect. It auto-generates fresh each start unless you set `GENIE_PIN` in `.env`.

Health check (in a browser or curl):
```
http://127.0.0.1:8765/health
```

---

## Step 5 — Install frontend dependencies

Open a **new** PowerShell window (keep the backend running):

```powershell
cd D:\GENAI\frontend
npm install
```

---

## Step 6 — Start the frontend

### Option A: Electron desktop app (recommended)
```powershell
cd D:\GENAI\frontend
npm run electron:dev
```
A frameless dark window appears. Enter the PIN shown in the backend console.

### Option B: Browser only (dev)
```powershell
cd D:\GENAI\frontend
npm run dev
```
Then open [http://localhost:5173](http://localhost:5173).

---

## Step 7 — Connect from your phone (optional)

1. Make sure `NGROK_AUTHTOKEN` is set in `.env` and the backend is running.
2. The StatusBar in the Electron window shows the **ngrok URL** (e.g. `https://abc123.ngrok-free.app`).
3. Open that URL on your phone's browser.
4. Enter the same PIN → you're in.

> **Note:** Mobile and desktop share the same session — they see the same chat and the same orb state.

---

## Adding a New Tool

1. Create or open any file under `backend/app/tools/`.
2. Import the registry decorator: `from .registry import tool`
3. Write your function and decorate it:

```python
@tool
def my_new_tool(param: str) -> ToolResult:
    """One-line description for GLM to know when to call this.

    :param param: What this parameter does.
    """
    # ... do something ...
    return ToolResult(status="ok", message="Done.", data={"result": "..."})
```

4. Import your module in `backend/app/tools/__init__.py`.
5. Restart the backend — the tool appears in `/health` and GLM can call it immediately.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Cloud LLM key is not set | Fill in `GEMINI_API_KEY`, or set `LLM_PROVIDER=grok` with `XAI_API_KEY` |
| `faster-whisper` model not found | It auto-downloads on first run; wait for the download |
| Volume control error | Run the backend as Administrator (pycaw needs COM access) |
| `pyngrok` tunnel failed | Check your `NGROK_AUTHTOKEN` in `.env` |
| Frontend can't connect to WS | Make sure backend is running on port 8765 |
| Electron window is blank | Check that Vite dev server is on 5173 (`npm run dev` in another terminal) |
| Ghost typing types in wrong window | Click the target app first, then give the command |

---

## Environment Variables Reference

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `gemini` | Cloud model provider: `gemini`, `grok`/`xai`, or `groq` |
| `GEMINI_API_KEY` | *(required for Gemini)* | Your Gemini API key from Google AI Studio |
| `GEMINI_BASE_URL` | `https://generativelanguage.googleapis.com/v1beta/openai/` | Gemini OpenAI-compatible endpoint |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Model name |
| `XAI_API_KEY` | *(required for Grok)* | xAI API key for Grok |
| `GROK_API_KEY` | *(empty)* | Optional alias for `XAI_API_KEY` |
| `GROK_BASE_URL` | `https://api.x.ai/v1` | xAI OpenAI-compatible endpoint |
| `GROK_MODEL` | `grok-4.5` | Grok model name |
| `GROQ_API_KEY` | *(required for Groq Cloud)* | Groq Cloud API key if `LLM_PROVIDER=groq` |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq Cloud model name |

Note the spelling: `grok` is xAI/Grok, while `groq` is Groq Cloud.

| `STT_ENGINE` | `faster_whisper` | `faster_whisper` or `whisper_api` |
| `WHISPER_MODEL_SIZE` | `small` | `tiny/base/small/medium/large-v3` |
| `STT_DEVICE` | `auto` | `auto/cuda/cpu` |
| `TTS_ENGINE` | `edge` | `edge`, `elevenlabs`, or `gemini_live` |
| `EDGE_VOICE` | `en-US-AriaNeural` | Any Edge TTS voice name |
| `ELEVENLABS_API_KEY` | *(empty)* | ElevenLabs key (enables ElevenLabs) |
| `GEMINI_LIVE_MODEL` | `gemini-3.1-flash-live-preview` | Gemini Live native-audio model used when `TTS_ENGINE=gemini_live` |
| `GEMINI_LIVE_VOICE_NAME` | `Aoede` | Gemini Live voice name |
| `GEMINI_LIVE_STYLE` | *(natural voice prompt)* | Spoken style instruction for Gemini Live |
| `NGROK_ENABLED` | `true` | Set `false` to disable tunnel |
| `NGROK_AUTHTOKEN` | *(empty)* | ngrok authtoken (recommended) |
| `YOUTUBE_DATA_API_KEY` | *(empty)* | Official YouTube Data API key for YouTube Music metadata |
| `YOUTUBE_REGION_CODE` | `IN` | Region used for YouTube search results |
| `YOUTUBE_MUSIC_PROVIDER` | `auto` | `auto`, `youtube_data`, `ytmusicapi`, or `browser` |
| `GOOGLE_CSE_API_KEY` | *(empty)* | Google Custom Search JSON API key |
| `GOOGLE_CSE_CX` | *(empty)* | Google Programmable Search Engine CX ID |
| `NEWS_API_KEY` | *(empty)* | NewsAPI.org key for official news results |
| `GNEWS_API_KEY` | *(empty)* | GNews.io key for official news results |
| `THENEWSAPI_KEY` | *(empty)* | TheNewsAPI.com key for official news results |
| `SPOTIFY_CLIENT_ID` | *(empty)* | Optional Spotify client ID for future media integrations |
| `SPOTIFY_CLIENT_SECRET` | *(empty)* | Optional Spotify client secret |
| `NEWS_DEFAULT_COUNTRY` | `in` | Default 2-letter news country |
| `NEWS_DEFAULT_LANGUAGE` | `en` | Default 2-letter news language |
| `API_TIMEOUT_SECONDS` | `10` | External API request timeout |
| `API_CACHE_TTL_SECONDS` | `300` | In-memory cache time for API responses |
| `API_RATE_LIMIT_PER_MINUTE` | `45` | Local per-provider rate limit |
| `API_CIRCUIT_FAILURE_THRESHOLD` | `3` | Failed calls before a provider circuit opens |
| `API_CIRCUIT_COOLDOWN_SECONDS` | `60` | Seconds before probing a failed provider again |
| `GENIE_PIN` | *(auto)* | 4-digit PIN; auto-generated if blank |
| `PORT` | `8765` | Backend listen port |

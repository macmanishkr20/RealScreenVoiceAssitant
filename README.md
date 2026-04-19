# Realtime Assistant — Screen + Voice + Text

Real-time multimodal assistant: share your screen, speak, and get answers grounded in what you're looking at, streamed back as voice.

- **Backend**: FastAPI + aiortc (WebRTC) + Microsoft Agent Framework
- **Frontend**: React + Vite + Framer Motion + React Three Fiber (Apple-style UI)
- **Model**: Azure OpenAI GPT-5 / GPT-5-mini (tiered) via Azure Speech for STT/TTS
- **Memory**: Azure Cosmos DB (NoSQL + vector)
- **Transport**: WebRTC for media, WebSocket for control
- **Latency target**: 800 ms p50 speak→first-audio, 1.5 s p95

## Current milestone — M3: Ask it anything, grounded on your screen

M3 closes the first answer loop. Speak a question, and GPT-5-mini replies
grounded on the most recent frame of your screen share, streamed back
through Azure TTS.

- [x] Frame sampler on inbound video: ≤1 fps, downscaled JPEG (512 px, q70),
      dropped if perceptual hash is within FRAME_DIFF_THRESHOLD of the
      last stored frame. Latest JPEG lives on the Session.
- [x] STT finalized transcripts push onto a per-session utterance queue.
- [x] Agent loop: dequeue utterance + attach latest frame (`detail: low`) →
      Azure OpenAI GPT-5-mini chat completion (streaming, minimal reasoning,
      200 max completion tokens) → reply piped into the TTS track.
- [x] UI: single "Conversation" panel with alternating **You** / **Assistant**
      turns; assistant partials stream live, final locks in.
- [x] Soft deps throughout: backend boots with Speech _and_ OpenAI keys
      missing; each layer just logs and no-ops.

Upcoming: M4 (Agent Framework for multi-step routing + tools), M5 (browser tool),
M6 (Cosmos memory + prompt caching), M7 (UI polish), M8 (telemetry).

## Run it

You only edit **two `.env` files**. That's the whole surface.

### 1. Backend

```bash
cd backend
cp .env.example .env     # M1 runs even without filling the keys in
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt   # or: pip install -e .  (uses pyproject.toml)
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Health check: open `http://127.0.0.1:8000/health` → `{"status":"ok","milestone":"M3"}`.

For M2 speech, fill in `backend/.env`:

```env
AZURE_SPEECH_KEY=<from Azure portal → Speech resource → Keys and Endpoint>
AZURE_SPEECH_REGION=eastus
```

For M3 vision, fill in `backend/.env`:

```env
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com
AZURE_OPENAI_API_KEY=<from Azure portal → Azure OpenAI resource → Keys and Endpoint>
AZURE_OPENAI_DEPLOYMENT_GPT5_MINI=gpt-5-mini
```

Then restart uvicorn. If any key is empty, the backend still runs; STT / TTS / agent just log a warning and no-op.

### 2. Frontend

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Then open `http://localhost:5173`.

### What to expect in M3

1. Landing page with the animated 3D orb hero.
2. Click **Start a session** → on the next page click **Grant screen + mic**.
3. Your shared window appears on the left with a live mic waveform below it.
4. **Speak a question about what's on screen** — partials stream in grey
   italics under _You_, then finalize.
5. GPT-5-mini answers in one or two short sentences; _Assistant_ text
   streams in sky-blue, and a moment later Azure TTS speaks it back
   through the page.
6. Status pills: `RTC: connected`, `Control: open`, `TTS speaking/idle`.
7. The bottom **Speak** box is still there for direct TTS (skips the agent).

If transcripts appear but the assistant stays silent, check the backend log
for `GPT call failed` or `AZURE_OPENAI_* missing`. If nothing shows, check
for `STT disabled` / `TTS unavailable` (Azure Speech key/region not set).

## `.env` — only places you edit

- `backend/.env` — Azure keys + endpoints (6 values total once M2+ land). M1 uses none of them.
- `frontend/.env` — backend URL + session token. Safe defaults already work.

## Project layout

```
realtime-assistant/
├── backend/
│   ├── .env.example
│   ├── pyproject.toml
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── session.py
│       ├── ws/{signaling,control}.py
│       ├── rtc/{peer,audio_pipeline,tts_track}.py
│       ├── speech/{stt,tts}.py
│       ├── agents/        # M4
│       ├── memory/        # M6
│       └── telemetry/     # M8
└── frontend/
    ├── .env.example
    ├── package.json
    └── src/
        ├── App.tsx
        ├── app/{Landing,Session}.tsx
        ├── rtc/usePeer.ts
        ├── ws/useControl.ts
        ├── ui/{Orb,MagneticCTA,Waveform}.tsx
        └── styles/global.css
```

# Realtime Assistant — Screen + Voice + Text

Real-time multimodal assistant: share your screen, speak, and get answers grounded in what you're looking at, streamed back as voice.

- **Backend**: FastAPI + aiortc (WebRTC) + Microsoft Agent Framework
- **Frontend**: React + Vite + Framer Motion + React Three Fiber (Apple-style UI)
- **Model**: Azure OpenAI GPT-5 / GPT-5-mini (tiered) via Azure Speech for STT/TTS
- **Memory**: Azure Cosmos DB (NoSQL + vector)
- **Transport**: WebRTC for media, WebSocket for control
- **Latency target**: 800 ms p50 speak→first-audio, 1.5 s p95

## Current milestone — M2: Voice in, voice out

M2 adds Azure Speech on both ends. No GPT yet.

- [x] Session registry (shared state across signaling + control WS)
- [x] Inbound audio → Azure Speech streaming STT → transcript events on control WS
- [x] TTS audio track attached to the PC; type text → hear it back through WebRTC
- [x] Session UI: live transcript panel with partial→final collapsing + Speak form
- [x] Speech is a soft dep: backend still boots with keys missing (logs a warning)

Upcoming: M3 (single-shot GPT-5-mini grounded on screen frame), M4 (Agent Framework), M5 (browser tool), M6 (Cosmos memory + prompt caching), M7 (UI polish), M8 (telemetry).

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

Health check: open `http://127.0.0.1:8000/health` → `{"status":"ok","milestone":"M1"}`.

For M2 speech, fill in `backend/.env`:

```env
AZURE_SPEECH_KEY=<from Azure portal → Speech resource → Keys and Endpoint>
AZURE_SPEECH_REGION=eastus
```

Then restart uvicorn. If the key is empty, the backend still runs; STT/TTS just log a warning and no-op.

### 2. Frontend

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Then open `http://localhost:5173`.

### What to expect in M2

1. Landing page with the animated 3D orb hero.
2. Click **Start a session** → on the next page click **Grant screen + mic**.
3. Your shared window appears on the left with a live mic waveform below it.
4. **Speak** — the right panel streams partials in grey italics, finalized text in white.
5. Type in the **Speak** box at the bottom and hit enter — Azure TTS synthesizes it and you hear the reply through the page (audio element is auto-played from the WebRTC track).
6. Status pills show `RTC: connected`, `Control: open`, and `TTS speaking/idle`.

If speech panels stay empty, check the backend log for `STT disabled` or `TTS unavailable` — that means the Azure key/region isn't set.

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

# Realtime Assistant — Screen + Voice + Text

Real-time multimodal assistant: share your screen, speak, and get answers grounded in what you're looking at, streamed back as voice.

- **Backend**: FastAPI + aiortc (WebRTC) + Microsoft Agent Framework
- **Frontend**: React + Vite + Framer Motion + React Three Fiber (Apple-style UI)
- **Model**: Azure OpenAI GPT-5 / GPT-5-mini (tiered) via Azure Speech for STT/TTS
- **Memory**: Azure Cosmos DB (NoSQL + vector)
- **Transport**: WebRTC for media, WebSocket for control
- **Latency target**: 800 ms p50 speak→first-audio, 1.5 s p95

## Current milestone — M1: Pipes alive

M1 proves the transport end-to-end. No AI yet.

- [x] FastAPI + signaling WS + control WS
- [x] aiortc PeerConnection that echoes screen + mic back to the client
- [x] React client with Apple-style landing hero (3D orb, magnetic CTA, shimmer headline)
- [x] Session view: side-by-side `your screen` / `echo from server` + mic waveform + control echo

Upcoming: M2 (VAD+STT), M3 (single-shot GPT-5-mini), M4 (Agent Framework), M5 (browser tool), M6 (Cosmos memory + prompt caching), M7 (UI polish), M8 (telemetry).

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

### 2. Frontend

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Then open `http://localhost:5173`.

### What to expect in M1

1. Landing page with the animated 3D orb hero.
2. Click **Start a session** → browser asks for screen share + mic.
3. Session view shows your screen on the left and the **echoed-back** screen from the server on the right. Speak into your mic — if you hear yourself, audio echo works.
4. Type into the control channel box → server echoes JSON back.

If all three round-trips work, M1 is green and we unlock M2.

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
│       ├── ws/{signaling,control}.py
│       ├── rtc/peer.py
│       ├── agents/        # M4
│       ├── memory/        # M6
│       ├── speech/        # M2
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

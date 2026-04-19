"""Control-plane WebSocket.

Bidirectional event bus for a single Session:
- server -> client: STT transcripts, TTS state, later agent events.
- client -> server: `speak` (enqueue text for TTS), `text` (echo for now,
  routed to the agent in M4).

Background reader task owns outbound pumping from session.events.
"""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings
from app.session import get_or_create

log = logging.getLogger("app.ws.control")
router = APIRouter()


@router.websocket("/ws/control")
async def control(ws: WebSocket):
    await ws.accept()
    token = ws.query_params.get("token")
    if token != settings.SESSION_TOKEN:
        await ws.close(code=4401)
        return

    session = get_or_create(ws.query_params.get("sessionId"))
    await ws.send_text(
        json.dumps({"type": "hello", "milestone": "M2", "sessionId": session.id})
    )

    async def pump_events():
        while True:
            evt = await session.events.get()
            await ws.send_text(json.dumps(evt))

    pump_task = asyncio.create_task(pump_events(), name=f"ctrl-pump-{session.id}")

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            kind = msg.get("type")

            if kind == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
            elif kind == "speak":
                text = (msg.get("text") or "").strip()
                if text:
                    await session.request_speak(text)
            elif kind == "text":
                # Placeholder until M4 routes this to the agent.
                await ws.send_text(
                    json.dumps({"type": "echo", "text": msg.get("text", "")})
                )
            else:
                log.info("control: type=%s", kind)
    except WebSocketDisconnect:
        log.info("control disconnected session=%s", session.id)
    finally:
        pump_task.cancel()

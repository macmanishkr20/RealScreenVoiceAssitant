"""Control-plane WebSocket.

Bidirectional event bus for a single Session:
- server -> client: user/assistant transcripts, TTS speaking state, errors.
- client -> server: `speak` / `text` — both inject a typed user turn into
  the Realtime session and force a response.

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
        json.dumps(
            {"type": "hello", "milestone": "realtime", "sessionId": session.id}
        )
    )

    async def pump_events():
        while True:
            evt = await session.events.get()
            try:
                await ws.send_text(json.dumps(evt))
            except Exception:
                log.exception("pump_events: send failed for evt=%s", evt.get("type"))
                return
            log.info("ctrl-out type=%s", evt.get("type"))

    pump_task = asyncio.create_task(pump_events(), name=f"ctrl-pump-{session.id}")

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            kind = msg.get("type")

            if kind == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
            elif kind in ("speak", "text"):
                text = (msg.get("text") or "").strip()
                if not text:
                    continue
                if session.realtime is None:
                    await ws.send_text(
                        json.dumps(
                            {
                                "type": "error",
                                "message": "Realtime session not ready.",
                            }
                        )
                    )
                    continue
                # Reflect the typed turn in the UI immediately so the user sees
                # their own message before the model's audio lands.
                await session.emit(type="transcript", text=text, final=True)
                await session.realtime.send_user_text(text)
            else:
                log.info("control: type=%s", kind)
    except WebSocketDisconnect:
        log.info("control disconnected session=%s", session.id)
    finally:
        pump_task.cancel()

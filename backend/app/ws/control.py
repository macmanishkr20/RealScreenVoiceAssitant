"""Control-plane WebSocket.

In M1 this is an echo + heartbeat channel. Later milestones bolt the
agent event bus onto the same socket (transcripts, tool calls, token
counters, TTS progress) — no new protocol surface required.
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings

log = logging.getLogger("app.ws.control")
router = APIRouter()


@router.websocket("/ws/control")
async def control(ws: WebSocket):
    await ws.accept()
    token = ws.query_params.get("token")
    if token != settings.SESSION_TOKEN:
        await ws.close(code=4401)
        return

    await ws.send_text(json.dumps({"type": "hello", "milestone": "M1"}))
    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            kind = msg.get("type")

            if kind == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
            elif kind == "text":
                await ws.send_text(json.dumps({
                    "type": "echo",
                    "text": msg.get("text", ""),
                }))
            else:
                log.info("control: type=%s", kind)
    except WebSocketDisconnect:
        log.info("control disconnected")

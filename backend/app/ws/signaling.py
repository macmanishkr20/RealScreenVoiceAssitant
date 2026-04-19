"""WebRTC signaling over WebSocket.

The client passes `sessionId` as a query param so both signaling and
control WSes bind to the same Session. Offer/answer exchange is
single-shot; ICE trickle works implicitly on localhost.
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings
from app.rtc.peer import create_peer
from app.session import get_or_create

log = logging.getLogger("app.ws.signaling")
router = APIRouter()


@router.websocket("/ws/signaling")
async def signaling(ws: WebSocket):
    await ws.accept()
    token = ws.query_params.get("token")
    if token != settings.SESSION_TOKEN:
        await ws.close(code=4401)
        log.warning("signaling rejected: bad token")
        return

    session = get_or_create(ws.query_params.get("sessionId"))
    await ws.send_text(json.dumps({"type": "ready", "sessionId": session.id}))

    pc_id: str | None = None
    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            kind = msg.get("type")

            if kind == "offer":
                pc_id, answer = await create_peer(session, msg["sdp"], msg["sdpType"])
                await ws.send_text(json.dumps({
                    "type": "answer",
                    "pcId": pc_id,
                    "sdp": answer.sdp,
                    "sdpType": answer.type,
                }))
            elif kind == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
            else:
                log.warning("signaling: unknown message type=%s", kind)
    except WebSocketDisconnect:
        log.info("signaling disconnected pc=%s session=%s", pc_id, session.id)

"""WebRTC signaling over WebSocket.

Single-shot offer/answer exchange. The client sends an SDP offer, the
server creates a PeerConnection and sends back the SDP answer, then the
socket may stay open for ICE trickle (not strictly required on localhost).
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings
from app.rtc.peer import create_peer

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

    pc_id: str | None = None
    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            kind = msg.get("type")

            if kind == "offer":
                pc_id, answer = await create_peer(msg["sdp"], msg["sdpType"])
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
        log.info("signaling disconnected pc=%s", pc_id)

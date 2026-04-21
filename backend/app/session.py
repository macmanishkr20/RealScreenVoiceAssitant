"""Per-session state shared across signaling and control WebSockets.

Each browser session is identified by `session_id`. The signaling WS
creates the Session, brings up a RealtimeClient, and wires both into a
PeerConnection. The control WS attaches and pumps transcript events out /
typed user input in.

Single-user mode: a handful of sessions live in-memory, no DB.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.realtime.client import RealtimeClient

log = logging.getLogger("app.session")


@dataclass
class Session:
    id: str
    pc_id: Optional[str] = None
    events: asyncio.Queue = field(default_factory=asyncio.Queue)  # server -> control WS
    latest_frame_jpeg: Optional[bytes] = None
    latest_frame_hash: Optional[int] = None
    realtime: Optional["RealtimeClient"] = None

    async def emit(self, **event) -> None:
        await self.events.put(event)


_sessions: dict[str, Session] = {}


def get_or_create(session_id: str | None) -> Session:
    sid = session_id or uuid.uuid4().hex[:10]
    sess = _sessions.get(sid)
    if sess is None:
        sess = Session(id=sid)
        _sessions[sid] = sess
        log.info("session created id=%s (total=%d)", sid, len(_sessions))
    return sess


def get(session_id: str) -> Session | None:
    return _sessions.get(session_id)


def drop(session_id: str) -> None:
    if _sessions.pop(session_id, None) is not None:
        log.info("session dropped id=%s (remaining=%d)", session_id, len(_sessions))

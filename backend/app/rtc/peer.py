"""aiortc PeerConnection wiring (M2).

Inbound audio -> AudioPipeline -> Azure STT -> transcript events on
session bus. Inbound video is accepted (frame sampling arrives in M3).
Outbound: a single send-only TTSAudioTrack backed by Azure TTS streams,
driven by text pushed onto `session.speak_queue` from the control WS.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Dict

from aiortc import RTCPeerConnection, RTCSessionDescription

from app.rtc.audio_pipeline import AudioPipeline
from app.rtc.tts_track import TTSAudioTrack
from app.session import Session
from app.speech.tts import synthesize

log = logging.getLogger("app.rtc")

_peers: Dict[str, RTCPeerConnection] = {}


async def create_peer(
    session: Session, offer_sdp: str, offer_type: str
) -> tuple[str, RTCSessionDescription]:
    pc = RTCPeerConnection()
    pc_id = uuid.uuid4().hex[:8]
    _peers[pc_id] = pc
    session.pc_id = pc_id
    log.info("[%s] peer created session=%s (total=%d)", pc_id, session.id, len(_peers))

    tts_track = TTSAudioTrack()
    pc.addTrack(tts_track)

    speak_task = asyncio.create_task(
        _speak_loop(session, tts_track), name=f"speak-{session.id}"
    )

    pipelines: list[AudioPipeline] = []

    @pc.on("connectionstatechange")
    async def _on_state():
        log.info("[%s] connectionState=%s", pc_id, pc.connectionState)
        if pc.connectionState in ("failed", "closed", "disconnected"):
            speak_task.cancel()
            for p in pipelines:
                p.stop()
            await _drop(pc_id)

    @pc.on("track")
    def _on_track(track):
        log.info("[%s] inbound track kind=%s id=%s", pc_id, track.kind, track.id)
        if track.kind == "audio":
            p = AudioPipeline(session, track)
            p.start()
            pipelines.append(p)
        # Video is accepted here; frame sampler wires in M3.

        @track.on("ended")
        async def _on_end():
            log.info("[%s] track ended kind=%s", pc_id, track.kind)

    offer = RTCSessionDescription(sdp=offer_sdp, type=offer_type)
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    return pc_id, pc.localDescription


async def _speak_loop(session: Session, track: TTSAudioTrack) -> None:
    """Drain session.speak_queue; synthesize each text and push PCM into the track."""
    try:
        while True:
            text = await session.speak_queue.get()
            await session.emit(type="speaking", text=text, state="start")
            async for chunk in synthesize(text):
                await track.push(chunk)
            await session.emit(type="speaking", text=text, state="end")
    except asyncio.CancelledError:
        pass
    except Exception:
        log.exception("speak loop crashed session=%s", session.id)


async def _drop(pc_id: str) -> None:
    pc = _peers.pop(pc_id, None)
    if pc is None:
        return
    try:
        await pc.close()
    finally:
        log.info("[%s] peer closed (remaining=%d)", pc_id, len(_peers))


async def close_all_peers() -> None:
    for pc_id in list(_peers.keys()):
        await _drop(pc_id)

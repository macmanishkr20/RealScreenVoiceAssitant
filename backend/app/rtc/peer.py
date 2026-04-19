"""aiortc PeerConnection wiring (M3).

Inbound audio -> AudioPipeline -> Azure STT -> transcript events on
session bus, with finalized utterances also pushed onto the utterance
queue for the agent loop. Inbound video -> FrameSampler keeps the most
recent JPEG on the session for vision grounding. Outbound: a single
send-only TTSAudioTrack backed by Azure TTS streams. Two loops consume
text: `_speak_loop` (direct "speak this" commands from the control WS)
and `_agent_loop` (STT finals -> GPT -> TTS).
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Dict

from aiortc import RTCPeerConnection, RTCSessionDescription

from app.agents.gpt import answer as gpt_answer
from app.rtc.audio_pipeline import AudioPipeline
from app.rtc.frame_sampler import FrameSampler
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
    agent_task = asyncio.create_task(
        _agent_loop(session, tts_track), name=f"agent-{session.id}"
    )

    pipelines: list[AudioPipeline] = []
    samplers: list[FrameSampler] = []

    @pc.on("connectionstatechange")
    async def _on_state():
        log.info("[%s] connectionState=%s", pc_id, pc.connectionState)
        if pc.connectionState in ("failed", "closed", "disconnected"):
            speak_task.cancel()
            agent_task.cancel()
            for p in pipelines:
                p.stop()
            for s in samplers:
                s.stop()
            await _drop(pc_id)

    @pc.on("track")
    def _on_track(track):
        log.info("[%s] inbound track kind=%s id=%s", pc_id, track.kind, track.id)
        if track.kind == "audio":
            p = AudioPipeline(session, track)
            p.start()
            pipelines.append(p)
        elif track.kind == "video":
            s = FrameSampler(session, track)
            s.start()
            samplers.append(s)

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
            await _speak(session, track, text)
    except asyncio.CancelledError:
        pass
    except Exception:
        log.exception("speak loop crashed session=%s", session.id)


async def _agent_loop(session: Session, track: TTSAudioTrack) -> None:
    """Drain STT final utterances; ask GPT grounded on the latest frame; speak the reply."""
    try:
        while True:
            transcript = await session.utterance_queue.get()
            if len(transcript.split()) < 2:
                log.info("agent: skipping trivial utterance %r", transcript)
                continue
            frame = session.latest_frame_jpeg
            log.info(
                "agent turn session=%s transcript=%r frame=%s",
                session.id,
                transcript[:80],
                f"{len(frame)}B" if frame else "none",
            )
            reply = ""
            async for text_chunk in gpt_answer(transcript, frame):
                reply += text_chunk
                await session.emit(type="assistant", text=reply, final=False)
            reply = reply.strip()
            if not reply:
                log.warning("agent: empty reply for %r", transcript[:60])
                continue
            await session.emit(type="assistant", text=reply, final=True)
            await _speak(session, track, reply)
    except asyncio.CancelledError:
        pass
    except Exception:
        log.exception("agent loop crashed session=%s", session.id)


async def _speak(session: Session, track: TTSAudioTrack, text: str) -> None:
    await session.emit(type="speaking", text=text, state="start")
    async for chunk in synthesize(text):
        await track.push(chunk)
    await session.emit(type="speaking", text=text, state="end")


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

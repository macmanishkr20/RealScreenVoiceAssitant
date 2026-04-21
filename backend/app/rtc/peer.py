"""aiortc PeerConnection wired to the Azure OpenAI Realtime socket.

Inbound audio  ->  AudioPipeline  ->  RealtimeClient.push_audio (24 kHz PCM)
Inbound video  ->  FrameSampler   ->  session.latest_frame_jpeg
                                      (pushed to Realtime on speech_started)
Realtime audio ->  resampled 24 k -> 48 k  ->  outbound TTSAudioTrack
Realtime events -> session.events queue -> control WS -> UI

Server VAD handles turn-taking; there is no separate STT or TTS stage.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Dict, List, Optional

from aiortc import RTCPeerConnection, RTCSessionDescription

from app.realtime.client import RealtimeClient
from app.rtc.audio_pipeline import AudioPipeline
from app.rtc.frame_sampler import FrameSampler
from app.rtc.tts_track import TTSAudioTrack
from app.session import Session

log = logging.getLogger("app.rtc")

_peers: Dict[str, RTCPeerConnection] = {}


async def create_peer(
    session: Session, offer_sdp: str, offer_type: str
) -> tuple[str, RTCSessionDescription]:
    # If the same browser session is making a fresh offer (e.g. user clicked
    # "Grant screen + mic" again to re-pick the share) the previous peer is
    # still alive and happily pushing audio. Tear it down first — otherwise
    # you hear two models talking at once.
    if session.pc_id is not None:
        log.info(
            "session=%s already had pc=%s — dropping before creating a new one",
            session.id,
            session.pc_id,
        )
        await _drop(session.pc_id)
        if session.realtime is not None:
            await session.realtime.close()
            session.realtime = None
        session.pc_id = None

    pc = RTCPeerConnection()
    pc_id = uuid.uuid4().hex[:8]
    _peers[pc_id] = pc
    session.pc_id = pc_id
    log.info("[%s] peer created session=%s (total=%d)", pc_id, session.id, len(_peers))

    out_track = TTSAudioTrack()
    pc.addTrack(out_track)

    client: Optional[RealtimeClient] = RealtimeClient()
    try:
        await client.connect()
    except Exception:
        log.exception("realtime connect failed; session will have no voice replies")
        client = None
    session.realtime = client

    pipelines: List[AudioPipeline] = []
    samplers: List[FrameSampler] = []
    bg_tasks: List[asyncio.Task] = []

    if client is not None:
        bg_tasks.append(
            asyncio.create_task(
                _audio_out_loop(session, out_track, client),
                name=f"rt-audio-out-{session.id}",
            )
        )
        bg_tasks.append(
            asyncio.create_task(
                _events_loop(session, client),
                name=f"rt-events-{session.id}",
            )
        )
    else:
        await session.emit(
            type="error",
            message="Realtime backend unavailable — check AZURE_OPENAI_* settings.",
        )

    @pc.on("connectionstatechange")
    async def _on_state():
        log.info("[%s] connectionState=%s", pc_id, pc.connectionState)
        if pc.connectionState in ("failed", "closed", "disconnected"):
            for t in bg_tasks:
                t.cancel()
            for p in pipelines:
                p.stop()
            for s in samplers:
                s.stop()
            if session.realtime is not None:
                await session.realtime.close()
                session.realtime = None
            await _drop(pc_id)

    @pc.on("track")
    def _on_track(track):
        log.info("[%s] inbound track kind=%s id=%s", pc_id, track.kind, track.id)
        if track.kind == "audio" and client is not None:
            p = AudioPipeline(session, track, client)
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


async def _audio_out_loop(
    session: Session, track: TTSAudioTrack, client: RealtimeClient
) -> None:
    """Feed the browser-bound 24 kHz track directly from the Realtime stream.
    Skipping a manual 24→48 kHz resampler removes micro-gaps at chunk
    boundaries — aiortc's Opus encoder handles the upsample."""
    try:
        async for chunk in client.iter_audio():
            if chunk:
                await track.push(chunk)
    except asyncio.CancelledError:
        pass
    except Exception:
        log.exception("realtime audio-out loop crashed session=%s", session.id)


async def _events_loop(session: Session, client: RealtimeClient) -> None:
    """Translate Realtime events into frontend control-WS events, and push a
    fresh screen frame when the user starts speaking so the model has context
    for the reply."""
    assistant_text = ""
    last_image_hash: Optional[int] = None
    try:
        async for evt in client.iter_events():
            t = evt.get("type", "")

            if t == "input_audio_buffer.speech_started":
                # User began talking. Drop any stale TTS state, and if we have
                # a fresh screen frame, attach it as visual context for this turn.
                await session.emit(type="speaking", text="", state="end")
                h = session.latest_frame_hash
                jpeg = session.latest_frame_jpeg
                if jpeg and h is not None and h != last_image_hash:
                    await client.push_image(jpeg)
                    last_image_hash = h
                    log.info(
                        "realtime: attached frame (%d B) on speech_started", len(jpeg)
                    )

            elif t == "conversation.item.input_audio_transcription.completed":
                text = (evt.get("transcript") or "").strip()
                if text:
                    await session.emit(type="transcript", text=text, final=True)

            elif t == "response.created":
                assistant_text = ""
                await session.emit(type="speaking", text="", state="start")

            elif t == "response.audio_transcript.delta":
                delta = evt.get("delta") or ""
                if delta:
                    assistant_text += delta
                    await session.emit(
                        type="assistant", text=assistant_text, final=False
                    )

            elif t == "response.audio_transcript.done":
                final_text = (evt.get("transcript") or assistant_text).strip()
                if final_text:
                    await session.emit(type="assistant", text=final_text, final=True)

            elif t == "response.done":
                await session.emit(type="speaking", text="", state="end")
                assistant_text = ""

            elif t == "error":
                err = evt.get("error") or {}
                await session.emit(type="error", message=str(err))

    except asyncio.CancelledError:
        pass
    except Exception:
        log.exception("realtime events loop crashed session=%s", session.id)


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

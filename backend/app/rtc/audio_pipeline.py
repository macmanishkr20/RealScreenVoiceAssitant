"""Inbound audio track -> Azure STT.

aiortc hands us decoded `av.AudioFrame`s at 48 kHz. Azure STT wants
16 kHz / 16-bit / mono PCM. We resample each frame and push raw bytes
into the SttSession. All work happens on the event loop.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

import av
from aiortc.mediastreams import MediaStreamError, MediaStreamTrack

from app.session import Session
from app.speech.stt import SttSession, start_stt

log = logging.getLogger("app.rtc.audio")


class AudioPipeline:
    """Pump a single inbound audio track through Azure STT."""

    def __init__(self, session: Session, track: MediaStreamTrack):
        self._session = session
        self._track = track
        self._task: Optional[asyncio.Task] = None
        self._stt: Optional[SttSession] = None
        self._resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)

    def start(self) -> None:
        loop = asyncio.get_running_loop()
        self._stt = start_stt(self._session, loop)
        self._task = asyncio.create_task(self._run(), name=f"audio-pipeline-{self._session.id}")

    async def _run(self) -> None:
        try:
            while True:
                frame = await self._track.recv()
                if self._stt is None:
                    continue
                for resampled in self._resampler.resample(frame):
                    pcm = bytes(resampled.planes[0])
                    self._stt.push(pcm)
        except MediaStreamError:
            log.info("audio track ended session=%s", self._session.id)
        except Exception:
            log.exception("audio pipeline crashed")
        finally:
            if self._stt is not None:
                self._stt.stop()

    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
        if self._stt is not None:
            self._stt.stop()

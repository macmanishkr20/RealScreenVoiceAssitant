"""Inbound audio track -> Azure OpenAI Realtime.

aiortc decodes Opus to `av.AudioFrame`s at 48 kHz. The Realtime API wants
24 kHz / 16-bit / mono PCM. We resample each frame and `push_audio` the
raw bytes into the session's RealtimeClient.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

import av
from aiortc.mediastreams import MediaStreamError, MediaStreamTrack

from app.realtime.client import RealtimeClient
from app.session import Session

log = logging.getLogger("app.rtc.audio")


class AudioPipeline:
    """Pump a single inbound audio track into the Realtime socket."""

    def __init__(
        self, session: Session, track: MediaStreamTrack, client: RealtimeClient
    ) -> None:
        self._session = session
        self._track = track
        self._client = client
        self._task: Optional[asyncio.Task] = None
        self._resampler = av.AudioResampler(format="s16", layout="mono", rate=24000)

    def start(self) -> None:
        self._task = asyncio.create_task(
            self._run(), name=f"audio-pipeline-{self._session.id}"
        )

    async def _run(self) -> None:
        try:
            while True:
                frame = await self._track.recv()
                for resampled in self._resampler.resample(frame):
                    pcm = bytes(resampled.planes[0])
                    if pcm:
                        await self._client.push_audio(pcm)
        except MediaStreamError:
            log.info("audio track ended session=%s", self._session.id)
        except asyncio.CancelledError:
            pass
        except Exception:
            log.exception("audio pipeline crashed session=%s", self._session.id)

    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()

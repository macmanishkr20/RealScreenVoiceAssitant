"""Outbound WebRTC audio track fed by Azure TTS.

aiortc's encoder wants a steady stream of AudioFrames at the track's
declared sample rate. We declare 48 kHz mono and `recv()` emits one
20 ms frame every 20 ms: either spoken audio pulled off the byte queue
or silence if nothing is queued. Keeping the cadence constant is what
lets the Opus encoder (and the browser's jitter buffer) stay sane.
"""
from __future__ import annotations

import asyncio
import fractions
import logging
from typing import AsyncIterator, Awaitable, Callable

import av
import numpy as np
from aiortc.mediastreams import MediaStreamTrack

log = logging.getLogger("app.rtc.tts")

_SAMPLE_RATE = 48000
_FRAME_MS = 20
_SAMPLES_PER_FRAME = _SAMPLE_RATE * _FRAME_MS // 1000  # 960
_BYTES_PER_FRAME = _SAMPLES_PER_FRAME * 2              # 16-bit


class TTSAudioTrack(MediaStreamTrack):
    """A send-only audio track backed by a byte queue of 48 k / 16-bit PCM."""

    kind = "audio"

    def __init__(self) -> None:
        super().__init__()
        self._buf = bytearray()
        self._cv = asyncio.Condition()
        self._samples_sent = 0
        self._silence = np.zeros(_SAMPLES_PER_FRAME, dtype=np.int16).tobytes()

    async def push(self, pcm: bytes) -> None:
        async with self._cv:
            self._buf.extend(pcm)
            self._cv.notify_all()

    async def stream_from(
        self,
        iterator_factory: Callable[[], AsyncIterator[bytes]],
    ) -> None:
        """Consume an async byte iterator and push all chunks into the buffer."""
        async for chunk in iterator_factory():
            await self.push(chunk)

    async def recv(self) -> av.AudioFrame:
        # Paced by a sleep so we emit ~50 fps regardless of buffer state.
        # Next frame = 20 ms after the last one, based on sample count.
        target = self._samples_sent + _SAMPLES_PER_FRAME
        await asyncio.sleep(_FRAME_MS / 1000)

        async with self._cv:
            if len(self._buf) >= _BYTES_PER_FRAME:
                chunk = bytes(self._buf[:_BYTES_PER_FRAME])
                del self._buf[:_BYTES_PER_FRAME]
            else:
                chunk = self._silence

        frame = av.AudioFrame(format="s16", layout="mono", samples=_SAMPLES_PER_FRAME)
        frame.planes[0].update(chunk)
        frame.sample_rate = _SAMPLE_RATE
        frame.pts = self._samples_sent
        frame.time_base = fractions.Fraction(1, _SAMPLE_RATE)
        self._samples_sent = target
        return frame

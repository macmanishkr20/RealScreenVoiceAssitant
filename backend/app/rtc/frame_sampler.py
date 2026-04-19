"""Inbound video track -> throttled JPEG buffer on the session.

We decode video lazily: aiortc hands us `av.VideoFrame`s when we pull
them. For token thrift we cap to FRAME_FPS_MAX, downscale to
FRAME_MAX_SIDE_PX, and skip near-duplicates via a tiny aHash. The
latest JPEG sits on `session.latest_frame_jpeg` so the agent can attach
it to the next GPT call without re-encoding.
"""
from __future__ import annotations

import asyncio
import io
import logging
import time
from typing import Optional

import imagehash
from aiortc.mediastreams import MediaStreamError, MediaStreamTrack
from PIL import Image

from app.config import settings
from app.session import Session

log = logging.getLogger("app.rtc.frames")


class FrameSampler:
    """Pump a single inbound video track into `session.latest_frame_jpeg`."""

    def __init__(self, session: Session, track: MediaStreamTrack):
        self._session = session
        self._track = track
        self._task: Optional[asyncio.Task] = None
        self._min_gap = 1.0 / max(0.1, settings.FRAME_FPS_MAX)
        self._last_emit_t = 0.0
        self._frames_seen = 0
        self._frames_stored = 0

    def start(self) -> None:
        self._task = asyncio.create_task(
            self._run(), name=f"frame-sampler-{self._session.id}"
        )

    async def _run(self) -> None:
        try:
            while True:
                frame = await self._track.recv()
                self._frames_seen += 1
                now = time.monotonic()
                if now - self._last_emit_t < self._min_gap:
                    continue
                if not self._process_frame(frame):
                    continue
                self._last_emit_t = now
        except MediaStreamError:
            log.info(
                "video track ended session=%s seen=%d stored=%d",
                self._session.id,
                self._frames_seen,
                self._frames_stored,
            )
        except Exception:
            log.exception("frame sampler crashed session=%s", self._session.id)

    def _process_frame(self, frame) -> bool:
        try:
            img = frame.to_image()  # av -> PIL (RGB)
        except Exception:
            log.exception("frame decode failed")
            return False

        img.thumbnail(
            (settings.FRAME_MAX_SIDE_PX, settings.FRAME_MAX_SIDE_PX),
            Image.LANCZOS,
        )
        h = int(str(imagehash.average_hash(img, hash_size=16)), 16)
        prev = self._session.latest_frame_hash
        if prev is not None:
            diff_bits = bin(h ^ prev).count("1") / 256.0
            if diff_bits < settings.FRAME_DIFF_THRESHOLD:
                return False

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=settings.FRAME_JPEG_QUALITY)
        self._session.latest_frame_jpeg = buf.getvalue()
        self._session.latest_frame_hash = h
        self._frames_stored += 1
        if self._frames_stored <= 3 or self._frames_stored % 20 == 0:
            log.info(
                "frame stored session=%s size=%s bytes (seen=%d stored=%d)",
                self._session.id,
                len(self._session.latest_frame_jpeg),
                self._frames_seen,
                self._frames_stored,
            )
        return True

    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()

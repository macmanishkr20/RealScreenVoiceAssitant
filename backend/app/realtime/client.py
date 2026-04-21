"""Azure OpenAI Realtime WebSocket client.

One instance per browser session. Replaces the old Azure STT + GPT text
+ Azure TTS cascade with a single bidirectional socket to
`gpt-4o-realtime-preview`:

  push_audio(pcm24k)   ─────▶ model (server-VAD handles turn-taking)
  push_image(jpeg)     ─────▶ model (vision context for the next turn)
  send_user_text(text) ─────▶ model (typed input; also forces response.create)

  iter_audio()         ◀───── PCM16 24 kHz mono chunks from the model voice
  iter_events()        ◀───── parsed event dicts (transcripts, VAD, errors)

The caller is responsible for resampling audio to/from the browser's 48 kHz
track and for surfacing transcripts on the control WS.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import AsyncIterator, Optional
from urllib.parse import urlencode

from websockets.asyncio.client import ClientConnection, connect as ws_connect
from websockets.exceptions import ConnectionClosed, InvalidStatus

from app.config import settings

log = logging.getLogger("app.realtime")

SYSTEM_PROMPT = (
    "You are a thoughtful voice assistant embedded on the user's desktop. "
    "You can see their screen, but the screen is context — not the subject. "
    "Answer spoken questions directly in 1-3 short sentences of natural, "
    "conversational English. Refer to what's on screen only when the "
    "question actually requires it. Never use markdown, headings, bullets, "
    "or code fences. "
    "When the user asks about specific numbers, labels, or text visible on "
    "screen, read them literally from the image — do NOT guess or round. If "
    "a value isn't clearly legible, say so instead of inventing one."
)

_AUDIO_SENTINEL: Optional[bytes] = None  # pushed on close() to unblock iter_audio


class RealtimeClient:
    def __init__(
        self,
        *,
        instructions: str = SYSTEM_PROMPT,
        voice: Optional[str] = None,
    ) -> None:
        self.instructions = instructions
        self.voice = voice or settings.AZURE_OPENAI_REALTIME_VOICE
        self._ws: Optional[ClientConnection] = None
        self._audio_out: asyncio.Queue[Optional[bytes]] = asyncio.Queue()
        self._events: asyncio.Queue[Optional[dict]] = asyncio.Queue()
        self._recv_task: Optional[asyncio.Task] = None
        self._closed = False

    # --- lifecycle -----------------------------------------------------

    async def connect(self) -> None:
        # Realtime may live in a different region/resource than the chat
        # deployments (e.g. Sweden Central). Prefer the realtime-specific
        # pair, fall back to the shared Azure OpenAI pair.
        endpoint = (
            settings.AZURE_OPENAI_REALTIME_ENDPOINT or settings.AZURE_OPENAI_ENDPOINT
        ).strip().rstrip("/")
        api_key = (
            settings.AZURE_OPENAI_REALTIME_API_KEY or settings.AZURE_OPENAI_API_KEY
        ).strip()
        if not endpoint or not api_key:
            raise RuntimeError(
                "AZURE_OPENAI_REALTIME_ENDPOINT/API_KEY (or the shared "
                "AZURE_OPENAI_ENDPOINT/API_KEY) must be set"
            )
        host = endpoint.replace("https://", "").replace("http://", "")
        params = urlencode(
            {
                "api-version": settings.AZURE_OPENAI_REALTIME_API_VERSION,
                "deployment": settings.AZURE_OPENAI_REALTIME_DEPLOYMENT,
            }
        )
        url = f"wss://{host}/openai/realtime?{params}"
        log.info(
            "realtime connect host=%s deployment=%s api-version=%s",
            host,
            settings.AZURE_OPENAI_REALTIME_DEPLOYMENT,
            settings.AZURE_OPENAI_REALTIME_API_VERSION,
        )
        try:
            self._ws = await ws_connect(
                url,
                additional_headers={"api-key": api_key},
                max_size=None,
                open_timeout=10,
            )
        except InvalidStatus as e:
            body = ""
            try:
                body = (e.response.body or b"").decode("utf-8", errors="replace")
            except Exception:
                pass
            log.error(
                "realtime handshake rejected status=%d body=%s",
                e.response.status_code,
                body[:500] or "<empty>",
            )
            raise
        await self._send(
            {
                "type": "session.update",
                "session": {
                    "modalities": ["text", "audio"],
                    "instructions": self.instructions,
                    "voice": self.voice,
                    "input_audio_format": "pcm16",
                    "output_audio_format": "pcm16",
                    "input_audio_transcription": {"model": "whisper-1"},
                    # Higher threshold so room echo / speaker bleed doesn't
                    # trip VAD — this is the biggest lever against "the model
                    # hears itself" feedback when the user isn't on headphones.
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.8,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 500,
                        "create_response": True,
                    },
                    "input_audio_noise_reduction": {"type": "near_field"},
                    "temperature": 0.7,
                },
            }
        )
        self._recv_task = asyncio.create_task(self._recv_loop(), name="realtime-recv")
        log.info("realtime session configured voice=%s", self.voice)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._recv_task:
            self._recv_task.cancel()
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
        # Unblock any readers.
        await self._audio_out.put(_AUDIO_SENTINEL)
        await self._events.put(None)

    # --- producers (caller → model) ------------------------------------

    async def push_audio(self, pcm24k: bytes) -> None:
        """Append a chunk of 24 kHz PCM16 mono audio to the input buffer."""
        if not pcm24k or self._ws is None or self._closed:
            return
        await self._send(
            {
                "type": "input_audio_buffer.append",
                "audio": base64.b64encode(pcm24k).decode("ascii"),
            }
        )

    async def push_image(self, jpeg: bytes) -> None:
        """Add a user-message with a single screen frame for visual context."""
        if not jpeg or self._ws is None or self._closed:
            return
        b64 = base64.b64encode(jpeg).decode("ascii")
        await self._send(
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {
                            "type": "input_image",
                            "image_url": f"data:image/jpeg;base64,{b64}",
                        }
                    ],
                },
            }
        )

    async def send_user_text(self, text: str) -> None:
        """Inject a typed user turn and force a response."""
        if not text or self._ws is None or self._closed:
            return
        await self._send(
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": text}],
                },
            }
        )
        await self._send({"type": "response.create"})

    async def cancel_response(self) -> None:
        """Best-effort: stop the current in-flight response (for barge-in)."""
        if self._ws is None or self._closed:
            return
        await self._send({"type": "response.cancel"})

    # --- consumers (model → caller) ------------------------------------

    async def iter_audio(self) -> AsyncIterator[bytes]:
        while True:
            chunk = await self._audio_out.get()
            if chunk is _AUDIO_SENTINEL:
                return
            if chunk:
                yield chunk

    async def iter_events(self) -> AsyncIterator[dict]:
        while True:
            evt = await self._events.get()
            if evt is None:
                return
            yield evt

    # --- internals -----------------------------------------------------

    async def _send(self, payload: dict) -> None:
        if self._ws is None:
            return
        try:
            await self._ws.send(json.dumps(payload))
        except Exception:
            log.exception("realtime send failed type=%s", payload.get("type"))

    async def _recv_loop(self) -> None:
        assert self._ws is not None
        try:
            async for msg in self._ws:
                try:
                    data = json.loads(msg)
                except Exception:
                    continue
                t = data.get("type", "")
                if t == "response.audio.delta":
                    b64 = data.get("delta") or ""
                    if b64:
                        await self._audio_out.put(base64.b64decode(b64))
                else:
                    if t == "error":
                        log.error("realtime error: %s", data.get("error"))
                    await self._events.put(data)
        except ConnectionClosed:
            log.info("realtime socket closed")
        except asyncio.CancelledError:
            pass
        except Exception:
            log.exception("realtime recv loop crashed")
        finally:
            await self._audio_out.put(_AUDIO_SENTINEL)
            await self._events.put(None)

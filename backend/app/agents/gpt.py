"""Single-shot Azure OpenAI GPT-5-mini vision call.

Streams short voice-friendly answers grounded on the most recent
screen frame. Token-thrifty defaults: `detail: low` on the image,
small max_completion_tokens, minimal reasoning effort.
"""
from __future__ import annotations

import base64
import logging
from typing import AsyncIterator, Optional

from app.config import settings

log = logging.getLogger("app.agents.gpt")

try:
    from openai import AsyncAzureOpenAI
    _SDK_OK = True
except ImportError:
    _SDK_OK = False

SYSTEM_PROMPT = (
    "You are a concise voice assistant embedded on the user's desktop. "
    "You can see their screen. Answer in one or two short sentences "
    "that read well when spoken out loud. Prefer specifics that are "
    "visible on screen. Never use markdown or lists."
)


def _client() -> Optional["AsyncAzureOpenAI"]:
    if not _SDK_OK:
        log.warning("openai SDK not installed; agent disabled")
        return None
    if not settings.AZURE_OPENAI_API_KEY or not settings.AZURE_OPENAI_ENDPOINT:
        log.warning("AZURE_OPENAI_* missing; agent disabled")
        return None
    return AsyncAzureOpenAI(
        api_key=settings.AZURE_OPENAI_API_KEY,
        api_version=settings.AZURE_OPENAI_API_VERSION,
        azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
    )


async def answer(
    transcript: str,
    frame_jpeg: Optional[bytes],
) -> AsyncIterator[str]:
    """Yield response text chunks for `transcript` grounded on `frame_jpeg`."""
    client = _client()
    if client is None:
        return

    content: list[dict] = [{"type": "text", "text": transcript}]
    if frame_jpeg:
        b64 = base64.b64encode(frame_jpeg).decode()
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{b64}",
                    "detail": "low",
                },
            }
        )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]

    try:
        stream = await client.chat.completions.create(
            model=settings.AZURE_OPENAI_DEPLOYMENT_GPT5_MINI,
            messages=messages,
            stream=True,
            max_completion_tokens=200,
            reasoning_effort="minimal",
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            text = getattr(delta, "content", None)
            if text:
                yield text
    except Exception:
        log.exception("GPT call failed transcript=%r", transcript[:60])
    finally:
        await client.close()
